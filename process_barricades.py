#!/usr/bin/env python3
"""
Gridlock 2.1 — Barricade Placement Recommender
Algorithmically determines optimal barricade positions near event venues
and high-CIS hotspots using spatial proximity scoring.

Uses ONLY Python standard library. No external dependencies.
"""

import json
import math
import os
from datetime import datetime, timedelta
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# ─── Barricade Types & Specs ──────────────────────────────────────────────────
BARRICADE_TYPES = {
    "crowd_control": {
        "name": "Crowd Control Barrier",
        "description": "Interlocking steel barriers for pedestrian crowd management",
        "icon": "🚧",
        "color": "#ff1744",
        "width_m": 1.2,
        "personnel_needed": 2,
        "setup_time_min": 15,
        "use_case": "Pedestrian overflow, event entry/exit points",
        "max_crowd_density": 5,  # people/m²
    },
    "traffic_diversion": {
        "name": "Traffic Diversion Barrier",
        "description": "Road-width water-filled plastic barriers with reflective strips",
        "icon": "🔶",
        "color": "#ff9100",
        "width_m": 2.5,
        "personnel_needed": 3,
        "setup_time_min": 20,
        "use_case": "Lane closure, road diversion",
        "max_crowd_density": 0,
    },
    "vip_security": {
        "name": "VIP Security Cordon",
        "description": "Heavy concrete jersey barriers + armed personnel",
        "icon": "🛡️",
        "color": "#d50000",
        "width_m": 1.8,
        "personnel_needed": 6,
        "setup_time_min": 45,
        "use_case": "VIP movements, diplomatic visits",
        "max_crowd_density": 0,
    },
    "soft_closure": {
        "name": "Soft Closure (Cones + Tape)",
        "description": "Traffic cones with reflective tape for minor diversions",
        "icon": "🔺",
        "color": "#ffab00",
        "width_m": 0.8,
        "personnel_needed": 1,
        "setup_time_min": 5,
        "use_case": "Minor congestion management, no-parking zones",
        "max_crowd_density": 2,
    },
    "entry_checkpoint": {
        "name": "Entry Checkpoint",
        "description": "Manned entry gate with queue management system",
        "icon": "⛩️",
        "color": "#6200ea",
        "width_m": 4.0,
        "personnel_needed": 4,
        "setup_time_min": 30,
        "use_case": "Ticketed events, controlled access zones",
        "max_crowd_density": 10,
    },
}

# ─── Key Road Intersections / Choke Points in Bengaluru ──────────────────────
# These are known bottlenecks where barricades have maximum impact
KNOWN_CHOKE_POINTS = [
    {"id": "CP-001", "name": "Silk Board Junction", "lat": 12.9172, "lng": 77.6231, "type": "junction", "severity": 10},
    {"id": "CP-002", "name": "KR Puram Junction", "lat": 13.0088, "lng": 77.6968, "type": "junction", "severity": 9},
    {"id": "CP-003", "name": "Marathahalli Bridge", "lat": 12.9591, "lng": 77.7012, "type": "bridge", "severity": 9},
    {"id": "CP-004", "name": "Hebbal Flyover", "lat": 13.0369, "lng": 77.5962, "type": "flyover", "severity": 8},
    {"id": "CP-005", "name": "Trinity Circle", "lat": 12.9761, "lng": 77.6048, "type": "junction", "severity": 8},
    {"id": "CP-006", "name": "Indiranagar 100ft Road", "lat": 12.9783, "lng": 77.6408, "type": "arterial", "severity": 7},
    {"id": "CP-007", "name": "Cauvery Junction", "lat": 12.9752, "lng": 77.5698, "type": "junction", "severity": 7},
    {"id": "CP-008", "name": "Mekhri Circle", "lat": 13.0061, "lng": 77.5821, "type": "junction", "severity": 8},
    {"id": "CP-009", "name": "Mysore Road Flyover", "lat": 12.9598, "lng": 77.5312, "type": "flyover", "severity": 7},
    {"id": "CP-010", "name": "Bannerghatta Road-ORR Junction", "lat": 12.9127, "lng": 77.6023, "type": "junction", "severity": 8},
    {"id": "CP-011", "name": "Bellary Road - Hebbal", "lat": 13.0431, "lng": 77.5902, "type": "arterial", "severity": 7},
    {"id": "CP-012", "name": "Electronic City Toll", "lat": 12.8412, "lng": 77.6681, "type": "toll", "severity": 9},
    {"id": "CP-013", "name": "Yeshwanthpur Circle", "lat": 13.0289, "lng": 77.5489, "type": "junction", "severity": 7},
    {"id": "CP-014", "name": "MG Road - Brigade Road Junction", "lat": 12.9749, "lng": 77.6075, "type": "junction", "severity": 8},
    {"id": "CP-015", "name": "Koramangala 80ft Road", "lat": 12.9352, "lng": 77.6245, "type": "arterial", "severity": 7},
    {"id": "CP-016", "name": "Nagavara Junction", "lat": 13.0498, "lng": 77.6312, "type": "junction", "severity": 7},
    {"id": "CP-017", "name": "Domlur Flyover", "lat": 12.9612, "lng": 77.6389, "type": "flyover", "severity": 7},
    {"id": "CP-018", "name": "Chalukya Circle", "lat": 12.9712, "lng": 77.5801, "type": "junction", "severity": 6},
    {"id": "CP-019", "name": "Rajajinagar Junction", "lat": 13.0019, "lng": 77.5523, "type": "junction", "severity": 7},
    {"id": "CP-020", "name": "Whitefield Main Road", "lat": 12.9812, "lng": 77.7480, "type": "arterial", "severity": 7},
]


def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def determine_barricade_type(event_type, crowd_size, choke_point_type):
    """Rule-based barricade type selection."""
    if event_type == "vip":
        return "vip_security"
    if choke_point_type in ("junction", "flyover", "toll"):
        if crowd_size > 30000:
            return "traffic_diversion"
        return "soft_closure"
    if event_type in ("concert", "sports") and crowd_size > 20000:
        if choke_point_type == "arterial":
            return "traffic_diversion"
        return "entry_checkpoint"
    if event_type == "marathon":
        return "traffic_diversion"
    if crowd_size > 10000:
        return "crowd_control"
    return "soft_closure"


def compute_barricade_score(event, choke_point, distance_km):
    """
    Score formula:
      score = (crowd_density × event_type_weight × choke_severity) / (distance_km + 0.5)
    Higher = more urgent barricade need.
    """
    crowd_density = event["crowd_size"] / (math.pi * event["radius_km"] ** 2)

    type_weights = {
        "vip": 3.0, "marathon": 2.5, "government": 2.2,
        "concert": 2.0, "sports": 1.8, "festival": 1.9,
        "tech": 1.4, "exhibition": 1.3,
    }
    type_w = type_weights.get(event["type"], 1.2)

    choke_sev = choke_point["severity"] / 10.0

    score = (math.log1p(crowd_density) * type_w * choke_sev * 10) / (distance_km + 0.5)
    return round(score, 2)


def compute_deployment_window(event_date_str, event_type, crowd_size):
    """
    Returns setup_start (hours before event) and teardown_end (hours after event).
    """
    try:
        ev_date = datetime.strptime(event_date_str, "%Y-%m-%d")
    except ValueError:
        ev_date = datetime.now()

    # Setup window: earlier for larger events
    if crowd_size > 50000 or event_type == "vip":
        setup_hours_before = 4
        teardown_hours_after = 3
    elif crowd_size > 20000:
        setup_hours_before = 3
        teardown_hours_after = 2
    elif crowd_size > 5000:
        setup_hours_before = 2
        teardown_hours_after = 1.5
    else:
        setup_hours_before = 1
        teardown_hours_after = 1

    # Default event time: 6 PM for concerts/sports, 8 AM for marathons
    if event_type == "marathon":
        event_hour = 6
    elif event_type in ("government", "vip"):
        event_hour = 10
    else:
        event_hour = 18

    event_start = ev_date.replace(hour=event_hour, minute=0)
    setup_start = event_start - timedelta(hours=setup_hours_before)
    event_end = event_start + timedelta(hours=3)
    teardown_end = event_end + timedelta(hours=teardown_hours_after)

    return {
        "setup_start": setup_start.strftime("%Y-%m-%d %H:%M"),
        "event_start": event_start.strftime("%Y-%m-%d %H:%M"),
        "event_end": event_end.strftime("%Y-%m-%d %H:%M"),
        "teardown_end": teardown_end.strftime("%Y-%m-%d %H:%M"),
        "total_deployment_hours": round(setup_hours_before + 3 + teardown_hours_after, 1),
    }


def load_events():
    path = os.path.join(DATA_DIR, "events.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def load_hotspots():
    path = os.path.join(DATA_DIR, "hotspots.json")
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
    print("║  Gridlock 2.1 — Barricade Placement Recommender        ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    os.makedirs(DATA_DIR, exist_ok=True)

    events = load_events()
    hotspots = load_hotspots()

    if not events:
        print("  ⚠ No events.json found. Run process_events.py first.")
        return

    barricade_plans = []
    all_barricade_points = []
    barricade_id_counter = 1

    # ── STEP 1: Event-Driven Barricade Plans ────────────────────────
    print("STEP 1: Computing event-driven barricade placements...")

    for event in events:
        ev_lat, ev_lng = event["lat"], event["lng"]
        ev_radius = event["radius_km"]
        ev_crowd = event["crowd_size"]
        ev_type = event["type"]

        # Find choke points within impact radius * 1.5
        nearby_chokes = []
        for cp in KNOWN_CHOKE_POINTS:
            dist = haversine(ev_lat, ev_lng, cp["lat"], cp["lng"])
            if dist <= ev_radius * 1.5:
                score = compute_barricade_score(event, cp, dist)
                nearby_chokes.append({**cp, "distance_km": round(dist, 2), "barricade_score": score})

        nearby_chokes.sort(key=lambda x: x["barricade_score"], reverse=True)
        top_chokes = nearby_chokes[:5]

        # Build barricade recommendations for each choke point
        recommendations = []
        for cp in top_chokes:
            b_type_key = determine_barricade_type(ev_type, ev_crowd, cp["type"])
            b_type = BARRICADE_TYPES[b_type_key]
            deployment = compute_deployment_window(event["date"], ev_type, ev_crowd)

            # Number of barricade units needed
            units_needed = max(1, int(ev_crowd / 15000) + (1 if cp["severity"] >= 9 else 0))

            rec = {
                "barricade_id": f"BAR-{barricade_id_counter:04d}",
                "choke_point_id": cp["id"],
                "location_name": cp["name"],
                "lat": cp["lat"],
                "lng": cp["lng"],
                "barricade_type": b_type_key,
                "barricade_name": b_type["name"],
                "barricade_icon": b_type["icon"],
                "barricade_color": b_type["color"],
                "units_needed": units_needed,
                "personnel_required": b_type["personnel_needed"] * units_needed,
                "setup_time_min": b_type["setup_time_min"],
                "deployment": deployment,
                "barricade_score": cp["barricade_score"],
                "distance_from_event_km": cp["distance_km"],
                "choke_severity": cp["severity"],
                "use_case": b_type["use_case"],
                "priority": "CRITICAL" if cp["barricade_score"] > 15 else "HIGH" if cp["barricade_score"] > 8 else "MEDIUM",
            }
            recommendations.append(rec)
            all_barricade_points.append({
                "barricade_id": rec["barricade_id"],
                "lat": cp["lat"],
                "lng": cp["lng"],
                "type": b_type_key,
                "color": b_type["color"],
                "icon": b_type["icon"],
                "event_name": event["name"],
                "event_date": event["date"],
                "priority": rec["priority"],
                "personnel_required": rec["personnel_required"],
                "units_needed": units_needed,
                "setup_time_min": b_type["setup_time_min"],
                "location_name": cp["name"],
                "deployment": deployment,
            })
            barricade_id_counter += 1

        # Manpower summary
        total_personnel = sum(r["personnel_required"] for r in recommendations)
        total_units = sum(r["units_needed"] for r in recommendations)

        # Also compute direct entry-point barricades at event venue
        venue_barricade_type = "entry_checkpoint" if ev_crowd > 10000 else "crowd_control"
        vb = BARRICADE_TYPES[venue_barricade_type]
        venue_entries = max(2, int(ev_crowd / 8000))

        barricade_plans.append({
            "event_id": event["id"],
            "event_name": event["name"],
            "event_date": event["date"],
            "event_type": ev_type,
            "venue": event["venue"],
            "lat": ev_lat,
            "lng": ev_lng,
            "crowd_size": ev_crowd,
            "risk_level": event["risk_level"],
            "choke_points_found": len(nearby_chokes),
            "barricade_recommendations": recommendations,
            "venue_entry_barricades": {
                "type": venue_barricade_type,
                "count": venue_entries,
                "personnel": vb["personnel_needed"] * venue_entries,
                "setup_time_min": vb["setup_time_min"],
            },
            "total_personnel_required": total_personnel + vb["personnel_needed"] * venue_entries,
            "total_barricade_units": total_units + venue_entries,
            "deployment_window": compute_deployment_window(event["date"], ev_type, ev_crowd),
        })

    print(f"  ✓ {len(barricade_plans)} event barricade plans generated")
    print(f"  ✓ {len(all_barricade_points)} individual barricade points")

    # ── STEP 2: Hotspot-Based Standing Barricades ────────────────────
    print("\nSTEP 2: Computing hotspot standing barricade recommendations...")

    hotspot_barricades = []
    top_hotspots = sorted(hotspots, key=lambda h: h["cis"], reverse=True)[:20]

    for hs in top_hotspots:
        # Find nearest choke point
        nearest_cp = min(KNOWN_CHOKE_POINTS,
                         key=lambda cp: haversine(hs["lat"], hs["lng"], cp["lat"], cp["lng"]))
        dist = haversine(hs["lat"], hs["lng"], nearest_cp["lat"], nearest_cp["lng"])

        # Permanent soft closure for high-CIS hotspots
        if hs["cis"] >= 80:
            b_type_key = "traffic_diversion"
        elif hs["cis"] >= 60:
            b_type_key = "soft_closure"
        else:
            b_type_key = "soft_closure"

        b_type = BARRICADE_TYPES[b_type_key]
        units = max(1, int(hs["cis"] / 35))

        hotspot_barricades.append({
            "hotspot_id": hs["id"],
            "label": hs["label"],
            "lat": hs["lat"],
            "lng": hs["lng"],
            "cis": hs["cis"],
            "total_violations": hs["total_violations"],
            "barricade_type": b_type_key,
            "barricade_name": b_type["name"],
            "barricade_icon": b_type["icon"],
            "barricade_color": b_type["color"],
            "units_needed": units,
            "personnel_required": b_type["personnel_needed"] * units,
            "peak_hours": hs.get("peak_hours", []),
            "nearest_choke": nearest_cp["name"],
            "nearest_choke_distance_km": round(dist, 2),
        })

    print(f"  ✓ {len(hotspot_barricades)} hotspot standing barricades mapped")

    # ── STEP 3: City-Wide Summary ────────────────────────────────────
    print("\nSTEP 3: Generating city-wide operational summary...")

    type_counts = defaultdict(int)
    for bp in all_barricade_points:
        type_counts[bp["type"]] += 1

    total_officers_events = sum(p["total_personnel_required"] for p in barricade_plans)
    total_officers_hotspots = sum(h["personnel_required"] for h in hotspot_barricades)

    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_events": len(events),
            "total_barricade_plans": len(barricade_plans),
            "total_barricade_points": len(all_barricade_points),
            "total_hotspot_barricades": len(hotspot_barricades),
        },
        "barricade_types": BARRICADE_TYPES,
        "event_plans": barricade_plans,
        "all_barricade_points": all_barricade_points,
        "hotspot_barricades": hotspot_barricades,
        "city_summary": {
            "total_officers_for_events": total_officers_events,
            "total_officers_for_hotspots": total_officers_hotspots,
            "barricade_type_breakdown": dict(type_counts),
            "critical_count": sum(1 for b in all_barricade_points if b["priority"] == "CRITICAL"),
            "high_count": sum(1 for b in all_barricade_points if b["priority"] == "HIGH"),
        },
    }

    save_json("barricades.json", output)

    print(f"\n  ✅ Barricade Placement Recommender complete!")
    print(f"     Event plans:         {len(barricade_plans)}")
    print(f"     Barricade points:    {len(all_barricade_points)}")
    print(f"     Hotspot barricades:  {len(hotspot_barricades)}")
    print(f"     Officers (events):   {total_officers_events}")
    print(f"     Officers (hotspots): {total_officers_hotspots}")


if __name__ == "__main__":
    main()
