#!/usr/bin/env python3
"""
Gridlock 2.1 — Live Data Simulator + SSE Server
Streams simulated real-time violation events using historical hotspot
distributions. Dashboard connects via EventSource (Server-Sent Events).

Also serves the static dashboard files with CORS headers.
Run: python live_server.py
Then open: http://localhost:8765
"""

import json
import math
import os
import random
import threading
import time
import queue
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
PORT = 8765

# ─── Simulation Config ─────────────────────────────────────────────────────────
EMIT_INTERVAL_SECONDS = 2.0       # How often to emit a live event
BATCH_SIZE_RANGE = (1, 3)         # Events per emission
HOTSPOT_BIAS = 0.70               # 70% of events come from hotspots
MAX_CLIENTS = 50

VIOLATION_TYPES = [
    "PARKING IN A MAIN ROAD",
    "DOUBLE PARKING",
    "PARKING ON FOOTPATH",
    "NO PARKING",
    "WRONG PARKING",
    "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL",
    "PARKING NEAR ROAD CROSSING",
]

VEHICLE_TYPES = [
    "CAR", "MOTOR CYCLE", "SCOOTER", "AUTO RICKSHAW",
    "BUS", "LORRY", "VAN", "TEMPO", "JEEP",
]

SEVERITY_MAP = {
    "PARKING IN A MAIN ROAD": "HIGH",
    "DOUBLE PARKING": "HIGH",
    "PARKING ON FOOTPATH": "MEDIUM",
    "NO PARKING": "MEDIUM",
    "WRONG PARKING": "LOW",
    "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL": "HIGH",
    "PARKING NEAR ROAD CROSSING": "MEDIUM",
}

SEVERITY_COLORS = {
    "HIGH": "#ff1744",
    "MEDIUM": "#ffab00",
    "LOW": "#00e676",
}

# Fallback hotspots if JSON not loaded
FALLBACK_HOTSPOTS = [
    {"lat": 12.9787, "lng": 77.5984, "label": "MG Road", "cis": 95},
    {"lat": 12.9352, "lng": 77.6245, "label": "Koramangala", "cis": 88},
    {"lat": 12.9172, "lng": 77.6231, "label": "Silk Board", "cis": 82},
    {"lat": 13.0369, "lng": 77.5962, "label": "Hebbal", "cis": 76},
    {"lat": 12.9493, "lng": 77.5848, "label": "Basavanagudi", "cis": 71},
    {"lat": 12.9612, "lng": 77.6389, "label": "Domlur", "cis": 68},
    {"lat": 12.9827, "lng": 77.6623, "label": "Whitefield", "cis": 74},
    {"lat": 13.0234, "lng": 77.6378, "label": "Hennur", "cis": 63},
]

# Key Road Intersections / Choke Points in Bengaluru
KNOWN_CHOKE_POINTS = [
    {"id": "CP-001", "name": "Silk Board Junction", "lat": 12.9172, "lng": 77.6231},
    {"id": "CP-002", "name": "KR Puram Junction", "lat": 13.0088, "lng": 77.6968},
    {"id": "CP-003", "name": "Marathahalli Bridge", "lat": 12.9591, "lng": 77.7012},
    {"id": "CP-004", "name": "Hebbal Flyover", "lat": 13.0369, "lng": 77.5962},
    {"id": "CP-005", "name": "Trinity Circle", "lat": 12.9761, "lng": 77.6048},
    {"id": "CP-006", "name": "Indiranagar 100ft Road", "lat": 12.9783, "lng": 77.6408},
    {"id": "CP-007", "name": "Cauvery Junction", "lat": 12.9752, "lng": 77.5698},
    {"id": "CP-008", "name": "Mekhri Circle", "lat": 13.0061, "lng": 77.5821},
    {"id": "CP-009", "name": "Mysore Road Flyover", "lat": 12.9598, "lng": 77.5312},
    {"id": "CP-010", "name": "Bannerghatta Road-ORR", "lat": 12.9127, "lng": 77.6023},
    {"id": "CP-011", "name": "Bellary Road - Hebbal", "lat": 13.0431, "lng": 77.5902},
    {"id": "CP-012", "name": "Electronic City Toll", "lat": 12.8412, "lng": 77.6681},
    {"id": "CP-013", "name": "Yeshwanthpur Circle", "lat": 13.0289, "lng": 77.5489},
    {"id": "CP-014", "name": "MG Road - Brigade", "lat": 12.9749, "lng": 77.6075},
    {"id": "CP-015", "name": "Koramangala 80ft Road", "lat": 12.9352, "lng": 77.6245},
    {"id": "CP-016", "name": "Nagavara Junction", "lat": 13.0498, "lng": 77.6312},
    {"id": "CP-017", "name": "Domlur Flyover", "lat": 12.9612, "lng": 77.6389},
    {"id": "CP-018", "name": "Chalukya Circle", "lat": 12.9712, "lng": 77.5801},
    {"id": "CP-019", "name": "Rajajinagar Junction", "lat": 13.0019, "lng": 77.5523},
    {"id": "CP-020", "name": "Whitefield Main Road", "lat": 12.9812, "lng": 77.7480},
]


def load_hotspots():
    path = os.path.join(DATA_DIR, "hotspots.json")
    try:
        with open(path) as f:
            data = json.load(f)
            return data[:50] if len(data) > 50 else data
    except Exception:
        return FALLBACK_HOTSPOTS


def load_stations():
    path = os.path.join(DATA_DIR, "model_weights.json")
    try:
        with open(path) as f:
            data = json.load(f)
            return data.get("stations", [])[:20]
    except Exception:
        return ["Madiwala PS", "Koramangala PS", "Indiranagar PS", "HSR Layout PS"]


# ─── Event Generator ──────────────────────────────────────────────────────────
class LiveEventGenerator:
    def __init__(self):
        self.hotspots = load_hotspots()
        self.stations = load_stations()
        self.event_counter = 0
        self.stats = {
            "total_emitted": 0,
            "by_severity": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "by_hour": {str(h): 0 for h in range(24)},
            "active_hotspots": set(),
        }
        # Initialize congestion for choke points
        self.choke_points = []
        for cp in KNOWN_CHOKE_POINTS:
            self.choke_points.append({
                "id": cp["id"],
                "name": cp["name"],
                "lat": cp["lat"],
                "lng": cp["lng"],
                "congestion_level": random.uniform(20.0, 60.0),
                "trend": random.choice([-1, 1])
            })

    def simulate_congestion(self):
        """Update congestion levels for choke points using a random walk."""
        updates = []
        for cp in self.choke_points:
            # Change trend occasionally
            if random.random() < 0.1:
                cp["trend"] *= -1
            
            # Update congestion
            delta = random.uniform(0, 5.0) * cp["trend"]
            cp["congestion_level"] += delta
            
            # Keep within bounds (0 to 100)
            if cp["congestion_level"] > 100:
                cp["congestion_level"] = 100
                cp["trend"] = -1
            elif cp["congestion_level"] < 10:
                cp["congestion_level"] = 10
                cp["trend"] = 1
                
            updates.append({
                "id": cp["id"],
                "congestion_level": round(cp["congestion_level"], 1)
            })
        return updates

    def generate_event(self):
        """Generate a single simulated violation event."""
        self.event_counter += 1

        # Decide: hotspot-based or random
        if random.random() < HOTSPOT_BIAS and self.hotspots:
            # Weight hotspots by CIS score
            weights = [h.get("cis", 50) for h in self.hotspots]
            total_w = sum(weights)
            r = random.uniform(0, total_w)
            cumulative = 0
            chosen_hs = self.hotspots[-1]
            for i, w in enumerate(weights):
                cumulative += w
                if r <= cumulative:
                    chosen_hs = self.hotspots[i]
                    break

            # Jitter position within ~200m
            jitter = 0.002
            lat = chosen_hs["lat"] + random.uniform(-jitter, jitter)
            lng = chosen_hs["lng"] + random.uniform(-jitter, jitter)
            label = chosen_hs.get("label", "Unknown Zone")
        else:
            # Random Bengaluru position
            lat = random.uniform(12.85, 13.10)
            lng = random.uniform(77.47, 77.75)
            label = "Unclassified Zone"

        vtype = random.choice(VIOLATION_TYPES)
        severity = SEVERITY_MAP.get(vtype, "LOW")
        vehicle = random.choices(
            VEHICLE_TYPES,
            weights=[30, 25, 20, 10, 3, 3, 4, 3, 2],
            k=1
        )[0]

        station = random.choice(self.stations) if self.stations else "Unknown PS"
        now = datetime.now()

        # Update stats
        self.stats["total_emitted"] += 1
        self.stats["by_severity"][severity] += 1
        self.stats["by_hour"][str(now.hour)] += 1
        self.stats["active_hotspots"].add(label)

        return {
            "id": self.event_counter,
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "location": label,
            "violation_type": vtype,
            "vehicle_type": vehicle,
            "severity": severity,
            "color": SEVERITY_COLORS[severity],
            "police_station": station,
            "timestamp": now.isoformat(),
            "timestamp_display": now.strftime("%H:%M:%S"),
        }

    def get_stats_snapshot(self):
        """Return current stats as a snapshot dict."""
        return {
            "total_emitted": self.stats["total_emitted"],
            "by_severity": dict(self.stats["by_severity"]),
            "active_zones": len(self.stats["active_hotspots"]),
            "peak_hour": max(self.stats["by_hour"], key=self.stats["by_hour"].get),
            "timestamp": datetime.now().isoformat(),
        }


# ─── SSE Client Registry ──────────────────────────────────────────────────────
class ClientRegistry:
    def __init__(self):
        self._clients = {}
        self._lock = threading.Lock()

    def add(self, client_id, q):
        with self._lock:
            self._clients[client_id] = q

    def remove(self, client_id):
        with self._lock:
            self._clients.pop(client_id, None)

    def broadcast(self, event_type, data):
        msg = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        dead = []
        with self._lock:
            for cid, q in self._clients.items():
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead.append(cid)
        for cid in dead:
            self.remove(cid)

    def count(self):
        with self._lock:
            return len(self._clients)


registry = ClientRegistry()
generator = LiveEventGenerator()


# ─── Background Emitter Thread ────────────────────────────────────────────────
def emitter_thread():
    """Runs in background — generates events and broadcasts to all SSE clients."""
    print(f"  🟢 Live emitter started (interval: {EMIT_INTERVAL_SECONDS}s)")
    stats_ticker = 0
    while True:
        try:
            if registry.count() > 0:
                # 1. Generate Violations
                n = random.randint(*BATCH_SIZE_RANGE)
                for _ in range(n):
                    event = generator.generate_event()
                    registry.broadcast("violation", event)
                    
                # 2. Update and Broadcast Congestion
                congestion_updates = generator.simulate_congestion()
                registry.broadcast("congestion_update", congestion_updates)

                # 3. Stats Ticker
                stats_ticker += 1
                if stats_ticker >= 10:
                    stats = generator.get_stats_snapshot()
                    registry.broadcast("stats", stats)
                    stats_ticker = 0

        except Exception as e:
            print(f"  ⚠ Emitter error: {e}")
        time.sleep(EMIT_INTERVAL_SECONDS)


# ─── HTTP Request Handler ─────────────────────────────────────────────────────
class GridlockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress per-request logs to keep console clean
        pass

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # ── SSE endpoint ──
        if path == "/live":
            self._handle_sse()
            return

        # ── Stats endpoint ──
        if path == "/stats":
            stats = generator.get_stats_snapshot()
            stats["connected_clients"] = registry.count()
            body = json.dumps(stats).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        # ── Static file serving ──
        if path == "/" or path == "":
            path = "/index.html"

        # Security: only serve from SCRIPT_DIR
        safe_path = path.lstrip("/")
        full_path = os.path.normpath(os.path.join(SCRIPT_DIR, safe_path))

        if not full_path.startswith(SCRIPT_DIR):
            self.send_response(403)
            self.end_headers()
            return

        if not os.path.exists(full_path) or os.path.isdir(full_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        # Determine MIME type
        ext = os.path.splitext(full_path)[1].lower()
        mime = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".ico": "image/x-icon",
            ".svg": "image/svg+xml",
        }.get(ext, "application/octet-stream")

        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def _handle_sse(self):
        """Handle a Server-Sent Events connection."""
        import uuid
        client_id = str(uuid.uuid4())[:8]
        q = queue.Queue(maxsize=50)
        registry.add(client_id, q)
        print(f"  📡 Client connected: {client_id} (total: {registry.count()})")

        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.send_cors_headers()
            self.end_headers()

            # Send initial connection event
            init_msg = f"event: connected\ndata: {json.dumps({'client_id': client_id, 'message': 'Gridlock Live Feed Active'})}\n\n"
            self.wfile.write(init_msg.encode())
            self.wfile.flush()

            while True:
                try:
                    msg = q.get(timeout=30)  # 30s timeout for keepalive
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
                except queue.Empty:
                    # Send keepalive comment
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()

        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            pass
        finally:
            registry.remove(client_id)
            print(f"  🔴 Client disconnected: {client_id} (total: {registry.count()})")


def main():
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  Gridlock 2.1 — Live Data Simulator + SSE Server       ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    print(f"  Loaded {len(generator.hotspots)} hotspots for simulation")
    print(f"  Loaded {len(generator.stations)} stations for simulation")

    # Start background emitter
    t = threading.Thread(target=emitter_thread, daemon=True)
    t.start()

    # Start HTTP server
    server = HTTPServer(("0.0.0.0", PORT), GridlockHandler)
    print(f"\n  ✅ Server running at: http://localhost:{PORT}")
    print(f"  📡 SSE endpoint:      http://localhost:{PORT}/live")
    print(f"  📊 Stats endpoint:    http://localhost:{PORT}/stats")
    print(f"\n  Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  🛑 Server stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
