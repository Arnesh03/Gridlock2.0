#!/usr/bin/env python3
"""
Gridlock 2.1 — Parking Violation Data Processor
Reads the anonymized police violation CSV and outputs pre-computed JSON files
for the enforcement intelligence dashboard.

Uses ONLY Python standard library. No external dependencies.
"""

import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

# ─── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(SCRIPT_DIR, "jan to may police violation_anonymized791b166.csv")
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
GRID_PRECISION = 3  # 0.001° ≈ 111m

# Violation severity weights for CIS
SEVERITY_WEIGHTS = {
    "PARKING IN A MAIN ROAD": 3.0,
    "DOUBLE PARKING": 3.0,
    "PARKING ON FOOTPATH": 2.5,
    "NO PARKING": 2.0,
    "WRONG PARKING": 1.5,
    "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL": 2.5,
    "PARKING NEAR ROAD CROSSING": 2.5,
}
DEFAULT_SEVERITY = 1.0

# Vehicle congestion weights for CIS
VEHICLE_WEIGHTS = {
    "HGV": 3.0, "LORRY": 3.0, "BUS": 3.0,
    "MAXI-CAB": 2.5, "PRIVATE BUS": 2.5, "TEMPO": 2.5,
    "CAR": 2.0, "JEEP": 2.0, "VAN": 2.0,
    "PASSENGER AUTO": 1.5, "GOODS AUTO": 1.5,
    "SCOOTER": 1.0, "MOTOR CYCLE": 1.0, "MOPED": 1.0,
}
DEFAULT_VEHICLE_WEIGHT = 1.0

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def parse_datetime(dt_str):
    """Parse datetime string like '2023-11-20 00:28:46+00' and convert to IST (+5:30)."""
    if not dt_str or dt_str == "NULL":
        return None
    try:
        # Strip timezone offset for simplicity — all are +00
        clean = dt_str.strip()
        # Handle various timezone suffixes: +00, +00:00, +0000
        for suffix in ["+00:00", "+0000", "+00"]:
            if clean.endswith(suffix):
                clean = clean[:-len(suffix)]
                break
        utc_dt = datetime.strptime(clean.strip(), "%Y-%m-%d %H:%M:%S")
        return utc_dt + timedelta(hours=5, minutes=30)
    except (ValueError, AttributeError):
        # Try with fractional seconds
        try:
            # Remove timezone part
            parts = clean.split("+")[0].split("-00")[0].strip()
            # Try with microseconds
            utc_dt = datetime.strptime(parts, "%Y-%m-%d %H:%M:%S.%f")
            return utc_dt + timedelta(hours=5, minutes=30)
        except (ValueError, AttributeError):
            return None


def parse_violation_types(vt_str):
    """Parse violation_type JSON array string like '["WRONG PARKING","NO PARKING"]'."""
    if not vt_str or vt_str == "NULL":
        return []
    try:
        parsed = json.loads(vt_str)
        if isinstance(parsed, list):
            return [str(v).strip() for v in parsed if v]
        return [str(parsed).strip()]
    except (json.JSONDecodeError, TypeError):
        return []


def safe_float(val, default=0.0):
    """Safely convert to float."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def get_vehicle_weight(vehicle_type):
    """Get congestion weight for a vehicle type."""
    if not vehicle_type or vehicle_type == "NULL":
        return DEFAULT_VEHICLE_WEIGHT
    vt_upper = vehicle_type.upper().strip()
    for key, weight in VEHICLE_WEIGHTS.items():
        if key in vt_upper:
            return weight
    return DEFAULT_VEHICLE_WEIGHT


def haversine(lat1, lng1, lat2, lng2):
    """Compute haversine distance in km between two lat/lng points."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def holt_linear_forecast(y, alpha=0.5, beta=0.5, steps=4):
    """Holt's Linear Exponential Smoothing for forecasting."""
    n = len(y)
    if n < 2:
        return [y[0] if y else 0] * steps
    
    # Initialize level and trend
    level = y[0]
    trend = y[1] - y[0]
    
    for i in range(1, n):
        last_level = level
        level = alpha * y[i] + (1 - alpha) * (last_level + trend)
        trend = beta * (level - last_level) + (1 - beta) * trend
        
    # Extrapolate with a decay factor to simulate seasonal moderation
    decay = 0.9  
    forecasts = []
    current_trend = trend
    for i in range(1, steps + 1):
        current_trend *= decay
        forecasts.append(max(0, level + current_trend * i))
    return forecasts


def nearest_neighbor_route(points):
    """Solve TSP approximately using nearest-neighbor heuristic.
    Start from westernmost point. Points are dicts with 'lat' and 'lng'."""
    if not points:
        return [], 0.0
    # Start from westernmost
    remaining = list(range(len(points)))
    start_idx = min(remaining, key=lambda i: points[i]["lng"])
    route = [start_idx]
    remaining.remove(start_idx)
    total_dist = 0.0

    while remaining:
        current = route[-1]
        nearest = min(remaining, key=lambda i: haversine(
            points[current]["lat"], points[current]["lng"],
            points[i]["lat"], points[i]["lng"]
        ))
        total_dist += haversine(
            points[current]["lat"], points[current]["lng"],
            points[nearest]["lat"], points[nearest]["lng"]
        )
        route.append(nearest)
        remaining.remove(nearest)

    return route, total_dist


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1: Load & Clean Data
# ═════════════════════════════════════════════════════════════════════════════
def load_data():
    print("=" * 70)
    print("STEP 1: Loading and cleaning data...")
    print(f"  CSV: {CSV_FILE}")
    print("=" * 70)

    records = []
    total_rows = 0
    skipped_rejected = 0
    skipped_duplicate = 0
    skipped_bad_coords = 0

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            if total_rows % 50000 == 0:
                print(f"  ... processed {total_rows:,} rows ({len(records):,} kept)")

            # Filter rejected and duplicate
            vs = (row.get("validation_status") or "").strip().lower()
            if vs == "rejected":
                skipped_rejected += 1
                continue
            if vs == "duplicate":
                skipped_duplicate += 1
                continue

            # Parse coordinates
            lat = safe_float(row.get("latitude"))
            lng = safe_float(row.get("longitude"))
            if lat == 0.0 or lng == 0.0:
                skipped_bad_coords += 1
                continue

            # Parse datetime
            dt = parse_datetime(row.get("created_datetime"))
            if dt is None:
                continue

            # Parse violation types
            vtypes = parse_violation_types(row.get("violation_type"))

            record = {
                "lat": lat,
                "lng": lng,
                "rlat": round(lat, GRID_PRECISION),
                "rlng": round(lng, GRID_PRECISION),
                "location": (row.get("location") or "").strip(),
                "vehicle_type": (row.get("vehicle_type") or "NULL").strip(),
                "violation_types": vtypes,
                "datetime": dt,
                "date": dt.date(),
                "hour": dt.hour,
                "day_of_week": dt.weekday(),  # Monday=0
                "junction_name": (row.get("junction_name") or "No Junction").strip(),
                "police_station": (row.get("police_station") or "Unknown").strip(),
                "validation_status": vs,
            }
            records.append(record)

    print(f"\n  Total rows read:    {total_rows:,}")
    print(f"  Rejected:           {skipped_rejected:,}")
    print(f"  Duplicate:          {skipped_duplicate:,}")
    print(f"  Bad coordinates:    {skipped_bad_coords:,}")
    print(f"  ✓ Valid records:    {len(records):,}")
    return records, total_rows


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2: Spatial Clustering → hotspots.json
# ═════════════════════════════════════════════════════════════════════════════
def compute_hotspots(records):
    print("\n" + "=" * 70)
    print("STEP 2: Computing spatial hotspots...")
    print("=" * 70)

    # Compute dataset date range
    all_dates = set(r["date"] for r in records)
    min_date = min(all_dates)
    max_date = max(all_dates)
    total_days = (max_date - min_date).days + 1
    print(f"  Date range: {min_date} to {max_date} ({total_days} days)")

    # Group by grid cell
    grid = defaultdict(list)
    for r in records:
        key = (r["rlat"], r["rlng"])
        grid[key].append(r)

    print(f"  Total grid cells: {len(grid):,}")

    # Compute per-cell stats
    hotspots = []
    all_cells = []  # For heatmap (all cells regardless of threshold)

    for (rlat, rlng), cell_records in grid.items():
        count = len(cell_records)
        all_cells.append((rlat, rlng, count))

        if count < 10:
            continue

        # Violation type counts (flattened)
        vtype_counter = Counter()
        severity_sum = 0.0
        for r in cell_records:
            for vt in r["violation_types"]:
                vtype_counter[vt] += 1
                severity_sum += SEVERITY_WEIGHTS.get(vt, DEFAULT_SEVERITY)

        # Vehicle type counts
        vehicle_counter = Counter()
        vehicle_score_sum = 0.0
        for r in cell_records:
            vt = r["vehicle_type"]
            vehicle_counter[vt] += 1
            vehicle_score_sum += get_vehicle_weight(vt)

        # Peak hours
        hour_counter = Counter(r["hour"] for r in cell_records)
        peak_hours = [h for h, _ in hour_counter.most_common(4)]

        # Active days
        active_dates = set(r["date"] for r in cell_records)
        active_days = len(active_dates)

        # Junction — most common non-'No Junction'
        junction_counter = Counter()
        for r in cell_records:
            jn = r["junction_name"]
            if jn and jn != "No Junction":
                junction_counter[jn] += 1
        junction = junction_counter.most_common(1)[0][0] if junction_counter else "No Junction"

        # Police station — most common
        station_counter = Counter(r["police_station"] for r in cell_records)
        police_station = station_counter.most_common(1)[0][0]

        # Label — most common location, truncated
        location_counter = Counter(r["location"] for r in cell_records if r["location"])
        label = location_counter.most_common(1)[0][0][:60] if location_counter else "Unknown"

        # Junction multiplier
        junction_multiplier = 1.5 if junction != "No Junction" else 1.0

        # Persistence
        persistence = active_days / total_days if total_days > 0 else 0

        # Raw CIS
        raw_cis = (
            (math.log(1 + count) * 5) +
            (severity_sum / count * 15) +
            (vehicle_score_sum / count * 10) +
            (persistence * 20) +
            (junction_multiplier * 10)
        )

        hotspots.append({
            "rlat": rlat,
            "rlng": rlng,
            "total_violations": count,
            "violation_types": dict(vtype_counter.most_common()),
            "vehicle_types": dict(vehicle_counter.most_common()),
            "peak_hours": sorted(peak_hours),
            "active_days": active_days,
            "junction": junction,
            "police_station": police_station,
            "label": label,
            "raw_cis": raw_cis,
        })

    # Normalize CIS to 0-100
    if hotspots:
        min_cis = min(h["raw_cis"] for h in hotspots)
        max_cis = max(h["raw_cis"] for h in hotspots)
        cis_range = max_cis - min_cis if max_cis != min_cis else 1.0
        for h in hotspots:
            h["cis"] = round((h["raw_cis"] - min_cis) / cis_range * 100, 1)

    # Sort by CIS descending, take top 200
    hotspots.sort(key=lambda h: h["cis"], reverse=True)
    top_hotspots = hotspots[:200]

    # Format output
    output = []
    for i, h in enumerate(top_hotspots):
        output.append({
            "id": f"HS-{i+1:03d}",
            "lat": h["rlat"],
            "lng": h["rlng"],
            "total_violations": h["total_violations"],
            "cis": h["cis"],
            "violation_types": h["violation_types"],
            "vehicle_types": h["vehicle_types"],
            "peak_hours": h["peak_hours"],
            "active_days": h["active_days"],
            "junction": h["junction"],
            "police_station": h["police_station"],
            "label": h["label"],
        })

    save_json("hotspots.json", output)
    print(f"  ✓ {len(output)} hotspots saved (from {len(hotspots)} cells with ≥10 violations)")
    print(f"    Top CIS: {output[0]['cis']} at {output[0]['label']}")
    print(f"    Lowest in top-200: {output[-1]['cis']}")

    return hotspots, all_cells, total_days, min_date, max_date


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3: Heatmap Data → heatmap.json
# ═════════════════════════════════════════════════════════════════════════════
def compute_heatmap(all_cells):
    print("\n" + "=" * 70)
    print("STEP 3: Computing heatmap data...")
    print("=" * 70)

    max_count = max(c for _, _, c in all_cells) if all_cells else 1
    heatmap = []
    for rlat, rlng, count in all_cells:
        intensity = round(count / max_count, 4)
        heatmap.append([rlat, rlng, intensity])

    save_json("heatmap.json", heatmap)
    print(f"  ✓ {len(heatmap):,} grid cells saved")
    print(f"    Max count in cell: {max_count}")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4: Time Series → time_series.json
# ═════════════════════════════════════════════════════════════════════════════
def compute_time_series(records):
    print("\n" + "=" * 70)
    print("STEP 4: Computing time series data...")
    print("=" * 70)

    # Hourly distribution
    hour_counter = Counter(r["hour"] for r in records)
    hourly = [{"hour": h, "count": hour_counter.get(h, 0)} for h in range(24)]

    # Day of week distribution
    dow_counter = Counter(r["day_of_week"] for r in records)
    day_of_week = [
        {"day": DAY_NAMES[d], "count": dow_counter.get(d, 0), "day_num": d}
        for d in range(7)
    ]

    # Daily counts
    daily_counter = Counter(r["date"].isoformat() for r in records)
    all_dates_sorted = sorted(daily_counter.keys())
    daily = [{"date": d, "count": daily_counter[d]} for d in all_dates_sorted]

    # Weekly counts (ISO week)
    weekly_counter = defaultdict(int)
    for r in records:
        d = r["date"]
        # Get Monday of the ISO week
        iso_year, iso_week, _ = d.isocalendar()
        # Compute the Monday of that ISO week
        jan4 = datetime(iso_year, 1, 4).date()
        start_of_week = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=iso_week - 1)
        weekly_counter[start_of_week.isoformat()] += 1
    weekly_sorted = sorted(weekly_counter.keys())
    weekly = [{"week_start": w, "count": weekly_counter[w]} for w in weekly_sorted]

    # Monthly counts
    monthly_counter = defaultdict(int)
    for r in records:
        month_key = r["date"].strftime("%Y-%m")
        monthly_counter[month_key] += 1
    monthly_sorted = sorted(monthly_counter.keys())
    monthly = [{"month": m, "count": monthly_counter[m]} for m in monthly_sorted]

    # Forecast: Holt's linear exponential smoothing with trend decay
    forecast = []
    if len(weekly) >= 8:
        last_8 = weekly[-8:]
        y = [w["count"] for w in last_8]
        predicted_vals = holt_linear_forecast(y, alpha=0.6, beta=0.4, steps=4)

        last_week_date = datetime.strptime(last_8[-1]["week_start"], "%Y-%m-%d").date()
        for i, predicted in enumerate(predicted_vals, start=1):
            week_start = last_week_date + timedelta(weeks=i)
            forecast.append({
                "week_start": week_start.isoformat(),
                "predicted": round(predicted),
                "lower": round(max(0, predicted * 0.85)),
                "upper": round(predicted * 1.15),
            })

    # Hourly by day (for heatmap grid)
    hourly_by_day_data = defaultdict(lambda: Counter())
    for r in records:
        day_name = DAY_NAMES[r["day_of_week"]]
        hourly_by_day_data[day_name][r["hour"]] += 1

    hourly_by_day = {}
    for day_name in DAY_NAMES:
        hourly_by_day[day_name] = [
            {"hour": h, "count": hourly_by_day_data[day_name].get(h, 0)}
            for h in range(24)
        ]

    output = {
        "hourly": hourly,
        "day_of_week": day_of_week,
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "forecast": forecast,
        "hourly_by_day": hourly_by_day,
    }

    save_json("time_series.json", output)
    peak_hour = max(hourly, key=lambda x: x["count"])
    peak_day = max(day_of_week, key=lambda x: x["count"])
    print(f"  ✓ Time series saved")
    print(f"    Peak hour: {peak_hour['hour']}:00 ({peak_hour['count']:,} violations)")
    print(f"    Peak day:  {peak_day['day']} ({peak_day['count']:,} violations)")
    print(f"    Daily data points: {len(daily)}")
    print(f"    Weekly data points: {len(weekly)}")
    print(f"    Forecast: {len(forecast)} weeks ahead")

    return peak_hour, peak_day


# ═════════════════════════════════════════════════════════════════════════════
# STEP 5: Patrol Routes → patrol_routes.json
# ═════════════════════════════════════════════════════════════════════════════
def compute_patrol_routes(hotspots):
    print("\n" + "=" * 70)
    print("STEP 5: Computing patrol routes...")
    print("=" * 70)

    # Take top 15 hotspots by CIS (already sorted)
    top15 = hotspots[:15]

    # Split into latitude bands
    bands = {
        "south": {"points": [], "label": "South Bengaluru", "color": "#ff1744"},
        "central": {"points": [], "label": "Central Bengaluru", "color": "#ff9100"},
        "north": {"points": [], "label": "North Bengaluru", "color": "#2979ff"},
    }

    for h in top15:
        point = {
            "lat": h["rlat"],
            "lng": h["rlng"],
            "label": h["label"],
            "cis": h["cis"],
            "violations": h["total_violations"],
            "police_station": h["police_station"],
        }
        if h["rlat"] < 12.93:
            bands["south"]["points"].append(point)
        elif h["rlat"] < 12.97:
            bands["central"]["points"].append(point)
        else:
            bands["north"]["points"].append(point)

    routes = []
    for band_key in ["south", "central", "north"]:
        band = bands[band_key]
        points = band["points"]
        if not points:
            continue

        # Determine route name from police stations
        stations = list(set(p["police_station"] for p in points))
        area_name = " / ".join(stations[:3]) if stations else band["label"]

        # Nearest-neighbor TSP
        order, total_km = nearest_neighbor_route(points)
        waypoints = [points[i] for i in order]
        # Remove police_station from waypoints (not in schema)
        clean_waypoints = []
        for wp in waypoints:
            clean_waypoints.append({
                "lat": wp["lat"],
                "lng": wp["lng"],
                "label": wp["label"],
                "cis": wp["cis"],
                "violations": wp["violations"],
            })

        priority = "critical" if any(wp["cis"] >= 75 for wp in waypoints) else "high"

        routes.append({
            "name": f"{area_name} — Priority Route",
            "color": band["color"],
            "priority": priority,
            "waypoints": clean_waypoints,
            "total_km": round(total_km, 2),
            "hotspot_count": len(clean_waypoints),
        })

    output = {"routes": routes}
    save_json("patrol_routes.json", output)
    print(f"  ✓ {len(routes)} patrol routes saved")
    for route in routes:
        print(f"    {route['name']}: {route['hotspot_count']} stops, {route['total_km']} km")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 6: Enforcement Analysis → enforcement.json
# ═════════════════════════════════════════════════════════════════════════════
def compute_enforcement(records):
    print("\n" + "=" * 70)
    print("STEP 6: Computing enforcement analysis...")
    print("=" * 70)

    from datetime import date as date_type
    cutoff = date_type(2024, 2, 1)

    # Group by grid cell
    grid = defaultdict(lambda: {"before": 0, "after": 0, "records": []})
    for r in records:
        key = (r["rlat"], r["rlng"])
        if r["date"] < cutoff:
            grid[key]["before"] += 1
        else:
            grid[key]["after"] += 1
        grid[key]["records"].append(r)

    zones = []
    for (rlat, rlng), cell in grid.items():
        total = cell["before"] + cell["after"]
        if total < 20:
            continue

        before = cell["before"]
        after = cell["after"]

        if before > 0:
            change_pct = round((after - before) / before * 100, 1)
        else:
            change_pct = 100.0 if after > 0 else 0.0

        if change_pct < -15:
            trend = "improving"
        elif change_pct > 15:
            trend = "worsening"
        else:
            trend = "stable"

        # Get label and police station
        location_counter = Counter(r["location"] for r in cell["records"] if r["location"])
        label = location_counter.most_common(1)[0][0][:60] if location_counter else "Unknown"
        station_counter = Counter(r["police_station"] for r in cell["records"])
        police_station = station_counter.most_common(1)[0][0]

        zones.append({
            "lat": rlat,
            "lng": rlng,
            "label": label,
            "police_station": police_station,
            "before": before,
            "after": after,
            "change_pct": change_pct,
            "trend": trend,
        })

    # Summary
    improving = [z for z in zones if z["trend"] == "improving"]
    worsening = [z for z in zones if z["trend"] == "worsening"]
    stable = [z for z in zones if z["trend"] == "stable"]
    avg_change = round(sum(z["change_pct"] for z in zones) / len(zones), 1) if zones else 0.0

    # Top improvers (most negative change) and decliners (most positive change)
    top_improvers = sorted(improving, key=lambda z: z["change_pct"])[:5]
    top_decliners = sorted(worsening, key=lambda z: z["change_pct"], reverse=True)[:5]

    output = {
        "period_a": {
            "label": "Nov 2023 \u2013 Jan 2024",
            "start": "2023-11-09",
            "end": "2024-01-31",
        },
        "period_b": {
            "label": "Feb 2024 \u2013 Apr 2024",
            "start": "2024-02-01",
            "end": "2024-04-08",
        },
        "zones": zones,
        "summary": {
            "total_zones": len(zones),
            "improving": len(improving),
            "worsening": len(worsening),
            "stable": len(stable),
            "avg_change_pct": avg_change,
            "top_improvers": top_improvers,
            "top_decliners": top_decliners,
        },
    }

    save_json("enforcement.json", output)
    print(f"  ✓ Enforcement analysis saved")
    print(f"    Total zones (≥20 violations): {len(zones)}")
    print(f"    Improving: {len(improving)}, Stable: {len(stable)}, Worsening: {len(worsening)}")
    print(f"    Average change: {avg_change}%")

    return output


# ═════════════════════════════════════════════════════════════════════════════
# STEP 7: Summary Stats → summary.json
# ═════════════════════════════════════════════════════════════════════════════
def compute_summary(records, total_rows, hotspots, peak_hour, peak_day, min_date, max_date):
    print("\n" + "=" * 70)
    print("STEP 7: Computing summary statistics...")
    print("=" * 70)

    total_days = (max_date - min_date).days + 1

    # Violation breakdown
    vtype_counter = Counter()
    for r in records:
        for vt in r["violation_types"]:
            vtype_counter[vt] += 1

    # Vehicle breakdown
    vehicle_counter = Counter(r["vehicle_type"] for r in records)

    # Station breakdown
    station_counter = Counter(r["police_station"] for r in records)

    # CIS stats
    cis_values = [h["cis"] for h in hotspots]
    critical_hotspots = sum(1 for c in cis_values if c >= 75)
    avg_cis = round(sum(cis_values) / len(cis_values), 1) if cis_values else 0.0
    max_cis = max(cis_values) if cis_values else 0.0

    output = {
        "total_violations": total_rows,
        "filtered_violations": len(records),
        "total_hotspots": len(hotspots),
        "critical_hotspots": critical_hotspots,
        "avg_daily": round(len(records) / total_days) if total_days > 0 else 0,
        "peak_hour": peak_hour["hour"],
        "peak_day": peak_day["day"],
        "top_violation": vtype_counter.most_common(1)[0][0] if vtype_counter else "Unknown",
        "top_station": station_counter.most_common(1)[0][0] if station_counter else "Unknown",
        "date_range": [min_date.isoformat(), max_date.isoformat()],
        "top_stations": [
            {"name": name, "count": count}
            for name, count in station_counter.most_common(10)
        ],
        "violation_breakdown": dict(vtype_counter.most_common()),
        "vehicle_breakdown": dict(vehicle_counter.most_common()),
        "avg_cis": avg_cis,
        "max_cis": max_cis,
    }

    save_json("summary.json", output)
    print(f"  ✓ Summary saved")
    print(f"    Filtered violations: {len(records):,}")
    print(f"    Total hotspots: {len(hotspots)}")
    print(f"    Critical hotspots (CIS≥75): {critical_hotspots}")
    print(f"    Avg daily violations: {output['avg_daily']}")
    print(f"    Top violation: {output['top_violation']}")
    print(f"    Top station: {output['top_station']}")


# ─── Utilities ────────────────────────────────────────────────────────────────
def save_json(filename, data):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    size_kb = os.path.getsize(filepath) / 1024
    print(f"  → {filename}: {size_kb:.1f} KB")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  Gridlock 2.1 — Data Processing Pipeline                ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    # Create output directory
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Output directory: {DATA_DIR}\n")

    # Step 1: Load data
    records, total_rows = load_data()

    # Step 2: Hotspots
    hotspots, all_cells, total_days, min_date, max_date = compute_hotspots(records)

    # Step 3: Heatmap
    compute_heatmap(all_cells)

    # Step 4: Time Series
    peak_hour, peak_day = compute_time_series(records)

    # Step 5: Patrol Routes
    compute_patrol_routes(hotspots)

    # Step 6: Enforcement
    compute_enforcement(records)

    # Step 7: Summary
    compute_summary(records, total_rows, hotspots, peak_hour, peak_day, min_date, max_date)

    # Final report
    print("\n" + "=" * 70)
    print("✅ ALL PROCESSING COMPLETE")
    print("=" * 70)
    print(f"\nOutput files in {DATA_DIR}:")
    for fname in sorted(os.listdir(DATA_DIR)):
        fpath = os.path.join(DATA_DIR, fname)
        size_kb = os.path.getsize(fpath) / 1024
        print(f"  📄 {fname}: {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
