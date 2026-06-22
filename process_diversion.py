#!/usr/bin/env python3
"""
Gridlock 2.1 — Diversion Route Planner
Fetches Bengaluru road network via Overpass API and generates alternate
diversion routes around hotspot zones and event venues.

Uses ONLY Python standard library. No external dependencies.
"""

import json
import math
import os
import urllib.request
import urllib.parse
import urllib.error
import time
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bengaluru city bounding box
BBOX = (12.85, 77.47, 13.10, 77.75)  # south, west, north, east

# Key arterial roads and corridors in Bengaluru (predefined for reliability)
# Format: name, list of [lat,lng] waypoints, road_type, capacity_vehicles_per_hour
BENGALURU_CORRIDORS = [
    {
        "id": "COR-001",
        "name": "Outer Ring Road (ORR) - South",
        "type": "arterial",
        "capacity": 4500,
        "waypoints": [
            [12.9121, 77.6451], [12.9202, 77.6387], [12.9280, 77.6301],
            [12.9365, 77.6198], [12.9438, 77.6132], [12.9517, 77.6034]
        ]
    },
    {
        "id": "COR-002",
        "name": "Outer Ring Road (ORR) - North",
        "type": "arterial",
        "capacity": 4500,
        "waypoints": [
            [13.0445, 77.6098], [13.0362, 77.6185], [13.0274, 77.6245],
            [13.0180, 77.6283], [13.0082, 77.6271], [12.9987, 77.6234]
        ]
    },
    {
        "id": "COR-003",
        "name": "MG Road - Brigade Road Corridor",
        "type": "primary",
        "capacity": 2800,
        "waypoints": [
            [12.9715, 77.5952], [12.9740, 77.6012], [12.9762, 77.6055],
            [12.9784, 77.6094], [12.9801, 77.6143]
        ]
    },
    {
        "id": "COR-004",
        "name": "Hosur Road - Electronics City Corridor",
        "type": "arterial",
        "capacity": 3800,
        "waypoints": [
            [12.9341, 77.6101], [12.9127, 77.6255], [12.8967, 77.6361],
            [12.8812, 77.6458], [12.8651, 77.6539], [12.8489, 77.6613]
        ]
    },
    {
        "id": "COR-005",
        "name": "Old Airport Road - Indiranagar Corridor",
        "type": "primary",
        "capacity": 2600,
        "waypoints": [
            [12.9592, 77.6412], [12.9657, 77.6432], [12.9718, 77.6455],
            [12.9779, 77.6478], [12.9838, 77.6498]
        ]
    },
    {
        "id": "COR-006",
        "name": "Tumkur Road - Yeshwanthpur Bypass",
        "type": "arterial",
        "capacity": 3600,
        "waypoints": [
            [12.9910, 77.5312], [13.0012, 77.5254], [13.0124, 77.5197],
            [13.0234, 77.5141], [13.0342, 77.5091]
        ]
    },
    {
        "id": "COR-007",
        "name": "Bellary Road - NH44 Corridor",
        "type": "national_highway",
        "capacity": 5000,
        "waypoints": [
            [13.0022, 77.5862], [13.0187, 77.5831], [13.0348, 77.5805],
            [13.0521, 77.5776], [13.0688, 77.5748]
        ]
    },
    {
        "id": "COR-008",
        "name": "NICE Road - Peripheral Ring Road",
        "type": "expressway",
        "capacity": 6000,
        "waypoints": [
            [12.8512, 77.5234], [12.8620, 77.5012], [12.8748, 77.4834],
            [12.8913, 77.4701], [12.9098, 77.4612], [12.9289, 77.4589]
        ]
    },
    {
        "id": "COR-009",
        "name": "Bannerghatta Road - JP Nagar Corridor",
        "type": "arterial",
        "capacity": 3200,
        "waypoints": [
            [12.9102, 77.5958], [12.8967, 77.5982], [12.8843, 77.6003],
            [12.8712, 77.6024], [12.8581, 77.6043]
        ]
    },
    {
        "id": "COR-010",
        "name": "Mysore Road - Kengeri Bypass",
        "type": "national_highway",
        "capacity": 4800,
        "waypoints": [
            [12.9521, 77.5213], [12.9398, 77.5087], [12.9267, 77.4965],
            [12.9145, 77.4841], [12.9012, 77.4723]
        ]
    },
    {
        "id": "COR-011",
        "name": "Whitefield Road - ITPL Corridor",
        "type": "primary",
        "capacity": 3000,
        "waypoints": [
            [12.9827, 77.6623], [12.9843, 77.6789], [12.9861, 77.6943],
            [12.9878, 77.7089], [12.9895, 77.7215]
        ]
    },
    {
        "id": "COR-012",
        "name": "Hennur Main Road - Kalyan Nagar Link",
        "type": "primary",
        "capacity": 2400,
        "waypoints": [
            [13.0234, 77.6378], [13.0189, 77.6289], [13.0141, 77.6201],
            [13.0094, 77.6114], [13.0048, 77.6028]
        ]
    },
]

# Predefined diversion templates for major blocked zones
# When a hotspot/event blocks a zone, we route around it via these corridors
DIVERSION_TEMPLATES = {
    "chinnaswamy": {
        "blocked_zone": "M. Chinnaswamy Stadium / MG Road",
        "lat": 12.9787, "lng": 77.5984,
        "diversions": [
            {
                "id": "DIV-001A",
                "name": "Via Richmond Road → Hosur Road",
                "via": "Richmond Circle → St. John's Road → Hosur Road",
                "waypoints": [
                    [12.9715, 77.6012], [12.9631, 77.5968], [12.9548, 77.5972],
                    [12.9462, 77.6023], [12.9389, 77.6089]
                ],
                "distance_km": 5.2, "travel_time_min": 18, "capacity": 2400,
                "type": "primary", "color": "#00e676"
            },
            {
                "id": "DIV-001B",
                "name": "Via Residency Road → Church Street",
                "via": "Residency Road → Museum Road → Kasturba Road",
                "waypoints": [
                    [12.9760, 77.6018], [12.9698, 77.6043], [12.9621, 77.6071],
                    [12.9558, 77.6095], [12.9489, 77.6112]
                ],
                "distance_km": 4.8, "travel_time_min": 15, "capacity": 1800,
                "type": "secondary", "color": "#ffab00"
            }
        ]
    },
    "palace_grounds": {
        "blocked_zone": "Palace Grounds",
        "lat": 13.0022, "lng": 77.5862,
        "diversions": [
            {
                "id": "DIV-002A",
                "name": "Via Mehkri Circle → Bellary Road",
                "via": "HMT Main Road → Bellary Road NH44",
                "waypoints": [
                    [13.0089, 77.5798], [13.0156, 77.5741], [13.0223, 77.5718],
                    [13.0289, 77.5734], [13.0348, 77.5776]
                ],
                "distance_km": 6.1, "travel_time_min": 22, "capacity": 3200,
                "type": "arterial", "color": "#00e676"
            },
            {
                "id": "DIV-002B",
                "name": "Via Yeshwanthpur → Tumkur Road",
                "via": "Sankey Road → Yeshwanthpur Circle → Tumkur Road",
                "waypoints": [
                    [13.0011, 77.5789], [13.0045, 77.5645], [13.0078, 77.5512],
                    [13.0102, 77.5389], [13.0124, 77.5254]
                ],
                "distance_km": 7.3, "travel_time_min": 26, "capacity": 2800,
                "type": "arterial", "color": "#ffab00"
            }
        ]
    },
    "freedom_park": {
        "blocked_zone": "Freedom Park / Nrupatunga Road",
        "lat": 12.9720, "lng": 77.5720,
        "diversions": [
            {
                "id": "DIV-003A",
                "name": "Via Mysore Road → NICE Road",
                "via": "Chord Road → Peenya → Mysore Road",
                "waypoints": [
                    [12.9689, 77.5634], [12.9598, 77.5521], [12.9487, 77.5412],
                    [12.9378, 77.5308], [12.9267, 77.5198]
                ],
                "distance_km": 8.4, "travel_time_min": 28, "capacity": 3600,
                "type": "national_highway", "color": "#00e676"
            }
        ]
    },
    "vidhana_soudha": {
        "blocked_zone": "Vidhana Soudha / Cubbon Park",
        "lat": 12.9791, "lng": 77.5913,
        "diversions": [
            {
                "id": "DIV-004A",
                "name": "Via Queens Road → Millers Road",
                "via": "Queens Road → Shivajinagar → Millers Road",
                "waypoints": [
                    [12.9834, 77.5865], [12.9892, 77.5812], [12.9951, 77.5760],
                    [13.0009, 77.5712], [13.0064, 77.5668]
                ],
                "distance_km": 4.2, "travel_time_min": 14, "capacity": 2000,
                "type": "primary", "color": "#00e676"
            },
            {
                "id": "DIV-004B",
                "name": "Via K.R. Circle → Lalbagh Road",
                "via": "K.R. Circle → Lalbagh Road → Hosur Road",
                "waypoints": [
                    [12.9712, 77.5845], [12.9658, 77.5798], [12.9601, 77.5823],
                    [12.9543, 77.5871], [12.9487, 77.5912]
                ],
                "distance_km": 5.6, "travel_time_min": 19, "capacity": 2200,
                "type": "primary", "color": "#ffab00"
            }
        ]
    },
    "biec": {
        "blocked_zone": "Bangalore International Exhibition Centre",
        "lat": 13.0662, "lng": 77.4695,
        "diversions": [
            {
                "id": "DIV-005A",
                "name": "Via NICE Road → ORR West",
                "via": "Tumkur Road → NICE Interchange → ORR",
                "waypoints": [
                    [13.0578, 77.4812], [13.0489, 77.4934], [13.0401, 77.5056],
                    [13.0312, 77.5178], [13.0224, 77.5301]
                ],
                "distance_km": 11.2, "travel_time_min": 35, "capacity": 5200,
                "type": "expressway", "color": "#00e676"
            }
        ]
    },
    "generic_hotspot": {
        "blocked_zone": "High-CIS Hotspot Zone",
        "lat": None, "lng": None,
        "diversions": []  # Dynamically generated
    }
}


def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def find_nearest_corridor(lat, lng):
    """Find the 2 nearest road corridors to a point."""
    scored = []
    for cor in BENGALURU_CORRIDORS:
        min_dist = min(haversine(lat, lng, wp[0], wp[1]) for wp in cor["waypoints"])
        scored.append((min_dist, cor))
    scored.sort(key=lambda x: x[0])
    return [s[1] for s in scored[:3]]


def generate_dynamic_diversion(hotspot, index):
    """Generate a diversion route for a hotspot using nearby corridors."""
    lat, lng = hotspot["lat"], hotspot["lng"]
    corridors = find_nearest_corridor(lat, lng)
    diversions = []
    colors = ["#00e676", "#ffab00", "#00e5ff"]

    for i, cor in enumerate(corridors[:2]):
        # Find entry/exit points (closest waypoints)
        entry = min(cor["waypoints"], key=lambda wp: haversine(lat, lng, wp[0], wp[1]))
        exit_wp = max(cor["waypoints"], key=lambda wp: haversine(lat, lng, wp[0], wp[1]))

        div = {
            "id": f"DIV-HS{index:03d}{chr(65+i)}",
            "name": f"Via {cor['name']}",
            "via": cor["name"],
            "waypoints": cor["waypoints"],
            "distance_km": round(haversine(entry[0], entry[1], exit_wp[0], exit_wp[1]) * 1.4, 1),
            "travel_time_min": round(haversine(entry[0], entry[1], exit_wp[0], exit_wp[1]) * 1.4 / 30 * 60),
            "capacity": cor["capacity"],
            "type": cor["type"],
            "color": colors[i % len(colors)],
        }
        diversions.append(div)

    return diversions


def try_fetch_overpass(query, timeout=15):
    """Attempt to fetch data from Overpass API."""
    try:
        data = urllib.parse.urlencode({"data": query}).encode()
        req = urllib.request.Request(OVERPASS_URL, data=data)
        req.add_header("User-Agent", "GridlockAI/2.1 (traffic analysis tool)")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ⚠ Overpass API unavailable ({e}). Using predefined corridors.")
        return None


def load_hotspots():
    path = os.path.join(DATA_DIR, "hotspots.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def load_events():
    path = os.path.join(DATA_DIR, "events.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def save_json(filename, data):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    size_kb = os.path.getsize(filepath) / 1024
    print(f"  → {filename}: {size_kb:.1f} KB")


def main():
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  Gridlock 2.1 — Diversion Route Planner                ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    os.makedirs(DATA_DIR, exist_ok=True)

    hotspots = load_hotspots()
    events = load_events()

    # ── STEP 1: Try Overpass API for live road data ──
    print("STEP 1: Attempting Overpass API fetch for Bengaluru roads...")
    overpass_query = f"""
    [out:json][timeout:25];
    (
      way["highway"~"^(primary|secondary|trunk|motorway)$"]
         ({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
    );
    out geom;
    """
    
    osm_data = try_fetch_overpass(overpass_query, timeout=20)
    osm_roads_fetched = 0

    if osm_data and "elements" in osm_data:
        osm_roads_fetched = len(osm_data["elements"])
        print(f"  ✓ Fetched {osm_roads_fetched} road segments from OSM")
    else:
        print("  ✓ Using predefined Bengaluru corridor network (12 corridors)")

    # ── STEP 2: Build Diversion Plans for Event Venues ──
    print("\nSTEP 2: Building event venue diversion routes...")
    event_diversions = []

    venue_keys = {
        "chinnaswamy": ["chinnaswamy", "stadium", "mg road"],
        "palace_grounds": ["palace grounds", "palace"],
        "freedom_park": ["freedom park", "freedom"],
        "vidhana_soudha": ["vidhana", "cubbon", "lalbagh"],
        "biec": ["biec", "exhibition centre", "exhibition center"],
    }

    for ev in events:
        venue_lower = ev["venue"].lower()
        matched_template = None

        for key, keywords in venue_keys.items():
            if any(kw in venue_lower for kw in keywords):
                matched_template = DIVERSION_TEMPLATES.get(key)
                break

        if matched_template:
            divs = matched_template["diversions"]
        else:
            # Generate dynamic diversion using nearest corridors
            synthetic_hs = {"lat": ev["lat"], "lng": ev["lng"]}
            divs = generate_dynamic_diversion(synthetic_hs, len(event_diversions) + 100)

        event_diversions.append({
            "event_id": ev["id"],
            "event_name": ev["name"],
            "venue": ev["venue"],
            "lat": ev["lat"],
            "lng": ev["lng"],
            "date": ev["date"],
            "risk_level": ev["risk_level"],
            "blocked_radius_km": ev["radius_km"],
            "diversion_routes": divs,
        })

    print(f"  ✓ {len(event_diversions)} event diversion plans built")

    # ── STEP 3: Build Hotspot Diversion Plans ──
    print("\nSTEP 3: Building hotspot diversion routes...")
    hotspot_diversions = []
    top_hotspots = sorted(hotspots, key=lambda h: h["cis"], reverse=True)[:15]

    for i, hs in enumerate(top_hotspots):
        divs = generate_dynamic_diversion(hs, i + 1)
        hotspot_diversions.append({
            "hotspot_id": hs["id"],
            "label": hs["label"],
            "lat": hs["lat"],
            "lng": hs["lng"],
            "cis": hs["cis"],
            "total_violations": hs["total_violations"],
            "diversion_routes": divs,
        })

    print(f"  ✓ {len(hotspot_diversions)} hotspot diversion plans built")

    # ── STEP 4: Save Output ──
    output = {
        "metadata": {
            "osm_roads_fetched": osm_roads_fetched,
            "total_corridors": len(BENGALURU_CORRIDORS),
            "generated_at": __import__("datetime").datetime.now().isoformat(),
        },
        "corridors": BENGALURU_CORRIDORS,
        "event_diversions": event_diversions,
        "hotspot_diversions": hotspot_diversions,
    }

    save_json("diversion_routes.json", output)
    print(f"\n  ✅ Diversion Route Planner complete!")
    print(f"     Corridors: {len(BENGALURU_CORRIDORS)}")
    print(f"     Event plans: {len(event_diversions)}")
    print(f"     Hotspot plans: {len(hotspot_diversions)}")


if __name__ == "__main__":
    main()
