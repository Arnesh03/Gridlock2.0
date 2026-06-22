#!/usr/bin/env python3
"""
Gridlock 2.1 — Event Calendar Engine + Holt-Winters Forecasting
Generates event-aware traffic impact forecasts for Bengaluru.

Uses ONLY Python standard library. No external dependencies.
"""

import json
import math
import os
from datetime import datetime, timedelta, date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# ─── Bengaluru Event Calendar ─────────────────────────────────────────────────
# Each event: name, venue, lat, lng, date, crowd_size, radius_km, type, color
RAW_EVENTS = [
    # Sports
    {"name": "RCB vs MI - IPL 2025", "venue": "M. Chinnaswamy Stadium", "lat": 12.9787, "lng": 77.5984,
     "date": "2025-04-15", "crowd": 35000, "radius_km": 2.0, "type": "sports", "color": "#e53e3e"},
    {"name": "RCB vs CSK - IPL 2025", "venue": "M. Chinnaswamy Stadium", "lat": 12.9787, "lng": 77.5984,
     "date": "2025-04-28", "crowd": 38000, "radius_km": 2.0, "type": "sports", "color": "#e53e3e"},
    {"name": "Bengaluru FC - ISL Match", "venue": "Sree Kanteerava Stadium", "lat": 12.9781, "lng": 77.5970,
     "date": "2025-05-10", "crowd": 18000, "radius_km": 1.5, "type": "sports", "color": "#e53e3e"},
    {"name": "Bengaluru FC - ISL Final", "venue": "Sree Kanteerava Stadium", "lat": 12.9781, "lng": 77.5970,
     "date": "2025-05-24", "crowd": 22000, "radius_km": 1.5, "type": "sports", "color": "#e53e3e"},

    # Concerts
    {"name": "Arijit Singh Live Concert", "venue": "Palace Grounds", "lat": 13.0022, "lng": 77.5862,
     "date": "2025-04-19", "crowd": 50000, "radius_km": 2.5, "type": "concert", "color": "#805ad5"},
    {"name": "AR Rahman - Harmony Tour", "venue": "Palace Grounds", "lat": 13.0022, "lng": 77.5862,
     "date": "2025-05-03", "crowd": 55000, "radius_km": 2.5, "type": "concert", "color": "#805ad5"},
    {"name": "Diljit Dosanjh Live", "venue": "Kanteerava Indoor Stadium", "lat": 12.9775, "lng": 77.5956,
     "date": "2025-05-17", "crowd": 12000, "radius_km": 1.2, "type": "concert", "color": "#805ad5"},
    {"name": "EDM Night - Sunburn Arena", "venue": "Bangalore International Exhibition Centre",
     "lat": 13.0662, "lng": 77.4695, "date": "2025-04-26", "crowd": 30000, "radius_km": 2.0, "type": "concert", "color": "#805ad5"},

    # Marathons & Runs
    {"name": "TCS World 10K Bengaluru", "venue": "Cubbon Park / MG Road", "lat": 12.9765, "lng": 77.5997,
     "date": "2025-05-18", "crowd": 25000, "radius_km": 3.5, "type": "marathon", "color": "#38a169"},
    {"name": "Bengaluru Half Marathon", "venue": "Freedom Park", "lat": 12.9720, "lng": 77.5720,
     "date": "2025-04-06", "crowd": 8000, "radius_km": 2.0, "type": "marathon", "color": "#38a169"},

    # Political & Government
    {"name": "Karnataka State Formation Day", "venue": "Vidhana Soudha / MG Road", "lat": 12.9791, "lng": 77.5913,
     "date": "2025-11-01", "crowd": 100000, "radius_km": 4.0, "type": "government", "color": "#d69e2e"},
    {"name": "Republic Day Parade - Bengaluru", "venue": "Manekshaw Parade Ground", "lat": 12.9611, "lng": 77.5909,
     "date": "2025-01-26", "crowd": 20000, "radius_km": 2.0, "type": "government", "color": "#d69e2e"},
    {"name": "Independence Day - Bengaluru", "venue": "Sree Kanteerava Stadium", "lat": 12.9781, "lng": 77.5970,
     "date": "2025-08-15", "crowd": 15000, "radius_km": 2.0, "type": "government", "color": "#d69e2e"},

    # Festivals
    {"name": "Bengaluru Tech Summit 2025", "venue": "Bangalore International Exhibition Centre",
     "lat": 13.0662, "lng": 77.4695, "date": "2025-11-19", "crowd": 40000, "radius_km": 2.0, "type": "tech", "color": "#00e5ff"},
    {"name": "Bengaluru Tech Summit 2025 - Day 2", "venue": "Bangalore International Exhibition Centre",
     "lat": 13.0662, "lng": 77.4695, "date": "2025-11-20", "crowd": 35000, "radius_km": 2.0, "type": "tech", "color": "#00e5ff"},
    {"name": "Dasara Procession - Bengaluru", "venue": "Cubbon Park to Vidhana Soudha", "lat": 12.9831, "lng": 77.5833,
     "date": "2025-10-02", "crowd": 80000, "radius_km": 3.0, "type": "festival", "color": "#ff6d00"},
    {"name": "Ugadi Shobhayatra", "venue": "Basavanagudi to Lalbagh", "lat": 12.9493, "lng": 77.5848,
     "date": "2025-03-30", "crowd": 30000, "radius_km": 2.5, "type": "festival", "color": "#ff6d00"},
    {"name": "Ganesh Chaturthi Procession", "venue": "Balepet to Ulsoor Lake", "lat": 12.9819, "lng": 77.6143,
     "date": "2025-08-27", "crowd": 60000, "radius_km": 3.5, "type": "festival", "color": "#ff6d00"},
    {"name": "Diwali Celebrations - Commercial Street", "venue": "Commercial Street", "lat": 12.9826, "lng": 77.6095,
     "date": "2025-10-20", "crowd": 50000, "radius_km": 2.0, "type": "festival", "color": "#ff6d00"},

    # VIP Movements
    {"name": "PM Visit - Bengaluru", "venue": "HAL Airport / Vidhana Soudha Corridor", "lat": 12.9791, "lng": 77.5913,
     "date": "2025-06-10", "crowd": 5000, "radius_km": 5.0, "type": "vip", "color": "#ff1744"},
    {"name": "G20 Sherpa Meeting - Bengaluru", "venue": "ITC Windsor Hotel", "lat": 12.9681, "lng": 77.5910,
     "date": "2025-07-14", "crowd": 3000, "radius_km": 3.0, "type": "vip", "color": "#ff1744"},

    # Exhibition / Trade
    {"name": "Auto Expo - BIEC", "venue": "Bangalore International Exhibition Centre",
     "lat": 13.0662, "lng": 77.4695, "date": "2025-09-12", "crowd": 45000, "radius_km": 2.0, "type": "exhibition", "color": "#00bcd4"},
    {"name": "India International Jewellery Show", "venue": "BIEC", "lat": 13.0662, "lng": 77.4695,
     "date": "2025-09-19", "crowd": 20000, "radius_km": 1.5, "type": "exhibition", "color": "#00bcd4"},
]

# ─── Holt-Winters Triple Exponential Smoothing ─────────────────────────────────
def holt_winters(y, alpha=0.3, beta=0.1, gamma=0.2, period=4, forecast_steps=4):
    """
    Triple Exponential Smoothing (Holt-Winters additive method).
    Handles trend + seasonality — far more accurate than Moving Average for traffic data.
    
    Args:
        y: Historical time series (list of numbers)
        alpha: Level smoothing factor (0–1)
        beta:  Trend smoothing factor (0–1)
        gamma: Seasonal smoothing factor (0–1)
        period: Season length (4 = quarterly weeks)
        forecast_steps: How many future steps to forecast
    
    Returns:
        fitted: In-sample fitted values
        forecast: Out-of-sample predictions with bounds
    """
    n = len(y)
    if n < period * 2:
        # Fallback to simple exponential smoothing
        level = y[0]
        fitted = []
        for val in y:
            fitted.append(level)
            level = alpha * val + (1 - alpha) * level
        avg = level
        return fitted, [{"predicted": round(avg), "lower": round(avg * 0.85), "upper": round(avg * 1.15)}] * forecast_steps

    # Initialize level, trend, and seasonal components
    # Level: average of first season
    level = sum(y[:period]) / period
    # Trend: average change between first and second seasons
    trend = (sum(y[period:2*period]) - sum(y[:period])) / (period ** 2)
    # Seasonal: deviation of each period point from its season average
    seasons = []
    season_avgs = []
    for i in range(0, min(n, period * 2), period):
        season_avgs.append(sum(y[i:i+period]) / period)
    for i in range(period):
        season_avg = sum(y[i::period][:2]) / 2
        seasons.append(y[i] - season_avg if season_avg > 0 else 0)

    # Smooth through history
    fitted = []
    seasonals = list(seasons)  # rolling seasonal buffer

    for i in range(n):
        m = i % period
        prev_level = level
        prev_trend = trend

        if i == 0:
            fitted.append(level + trend + seasonals[m])
            continue

        val = y[i]
        fitted_val = level + trend + seasonals[m]
        fitted.append(fitted_val)

        # Update level
        level = alpha * (val - seasonals[m]) + (1 - alpha) * (prev_level + prev_trend)
        # Update trend
        trend = beta * (level - prev_level) + (1 - beta) * prev_trend
        # Update seasonal
        seasonals[m] = gamma * (val - level) + (1 - gamma) * seasonals[m]

    # Forecast
    forecast = []
    for h in range(1, forecast_steps + 1):
        m = (n + h - 1) % period
        pred = level + h * trend + seasonals[m]
        pred = max(0, pred)
        uncertainty = 0.1 * h  # grows with horizon
        forecast.append({
            "predicted": round(pred),
            "lower": round(max(0, pred * (1 - uncertainty))),
            "upper": round(pred * (1 + uncertainty)),
        })

    return fitted, forecast


def compute_impact_multiplier(crowd_size, radius_km, event_type):
    """Compute how much an event amplifies local violation rates."""
    # Base: crowd per sq km
    area = math.pi * radius_km ** 2
    density = crowd_size / area

    # Density factor (log-scale, capped)
    density_factor = min(3.0, 1.0 + math.log1p(density / 1000))

    # Type factor
    type_factors = {
        "vip": 2.5,      # Road closures, motorcades
        "marathon": 2.0, # Route blocked
        "government": 1.8,
        "concert": 1.6,
        "sports": 1.5,
        "festival": 1.7,
        "tech": 1.3,
        "exhibition": 1.2,
    }
    type_factor = type_factors.get(event_type, 1.2)

    return round(density_factor * type_factor, 2)


def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def load_hotspots():
    """Load hotspots for spatial overlap computation."""
    path = os.path.join(DATA_DIR, "hotspots.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def load_time_series():
    """Load existing time series for Holt-Winters upgrade."""
    path = os.path.join(DATA_DIR, "time_series.json")
    if not os.path.exists(path):
        return {}
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
    print("║  Gridlock 2.1 — Event Calendar Engine                  ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    os.makedirs(DATA_DIR, exist_ok=True)

    hotspots = load_hotspots()
    ts = load_time_series()
    weekly = ts.get("weekly", [])

    # ── STEP 1: Process Event Calendar ──────────────────────────────
    print("STEP 1: Processing event calendar...")
    events_out = []
    today = date.today()

    for ev in RAW_EVENTS:
        try:
            ev_date = datetime.strptime(ev["date"], "%Y-%m-%d").date()
        except ValueError:
            continue

        multiplier = compute_impact_multiplier(ev["crowd"], ev["radius_km"], ev["type"])
        days_from_today = (ev_date - today).days

        # Find overlapping hotspots
        overlapping = []
        for hs in hotspots:
            dist = haversine(ev["lat"], ev["lng"], hs["lat"], hs["lng"])
            if dist <= ev["radius_km"]:
                overlapping.append({
                    "id": hs["id"],
                    "label": hs["label"],
                    "cis": hs["cis"],
                    "distance_km": round(dist, 2),
                })

        # Risk level
        risk_score = multiplier * (1 + len(overlapping) * 0.2)
        if risk_score >= 4.0:
            risk = "CRITICAL"
        elif risk_score >= 2.5:
            risk = "HIGH"
        elif risk_score >= 1.5:
            risk = "MODERATE"
        else:
            risk = "LOW"

        # Recommended manpower
        base_officers = max(5, int(ev["crowd"] / 1000))
        adj_officers = int(base_officers * multiplier)

        events_out.append({
            "id": f"EVT-{len(events_out)+1:03d}",
            "name": ev["name"],
            "venue": ev["venue"],
            "lat": ev["lat"],
            "lng": ev["lng"],
            "date": ev["date"],
            "crowd_size": ev["crowd"],
            "radius_km": ev["radius_km"],
            "type": ev["type"],
            "color": ev["color"],
            "impact_multiplier": multiplier,
            "risk_level": risk,
            "days_from_today": days_from_today,
            "overlapping_hotspots": overlapping,
            "hotspot_count": len(overlapping),
            "recommended_officers": adj_officers,
        })

    events_out.sort(key=lambda e: e["date"])
    save_json("events.json", events_out)
    print(f"  ✓ {len(events_out)} events processed")

    # ── STEP 2: Holt-Winters Enhanced Forecast ───────────────────────
    print("\nSTEP 2: Running Holt-Winters triple exponential smoothing...")
    
    if len(weekly) >= 8:
        y = [w["count"] for w in weekly]
        fitted, hw_forecast = holt_winters(y, alpha=0.3, beta=0.1, gamma=0.2, period=4, forecast_steps=12)

        # Extend forecast dates
        last_date = datetime.strptime(weekly[-1]["week_start"], "%Y-%m-%d").date()
        forecast_series = []
        for i, f in enumerate(hw_forecast, 1):
            week_start = last_date + timedelta(weeks=i)
            
            # Check for events in this week
            week_end = week_start + timedelta(days=6)
            events_this_week = [
                ev for ev in events_out
                if week_start <= datetime.strptime(ev["date"], "%Y-%m-%d").date() <= week_end
            ]
            
            event_boost = 1.0
            event_names = []
            for ev in events_this_week:
                event_boost = max(event_boost, ev["impact_multiplier"] * 0.3 + 1.0)
                event_names.append(ev["name"])
            
            event_adjusted = round(f["predicted"] * event_boost)
            forecast_series.append({
                "week_start": week_start.isoformat(),
                "predicted": f["predicted"],
                "event_adjusted": event_adjusted,
                "lower": f["lower"],
                "upper": f["upper"],
                "has_event": len(events_this_week) > 0,
                "event_names": event_names,
                "event_boost": round(event_boost, 2),
            })

        # Backtest accuracy (Holt-Winters)
        if len(y) >= 12:
            train = y[:-4]
            test = y[-4:]
            _, test_forecast = holt_winters(train, forecast_steps=4)
            errors = []
            for actual, pred_obj in zip(test, test_forecast):
                pred = pred_obj["predicted"]
                if actual > 0:
                    errors.append(abs(actual - pred) / actual)
            if errors:
                mape = sum(errors) / len(errors) * 100
                accuracy = max(0, 100 - mape)
                print(f"  ✓ Holt-Winters Backtest Accuracy: {accuracy:.1f}% (MAPE: {mape:.1f}%)")
                try:
                    with open(os.path.join(SCRIPT_DIR, "accuracy.log"), "a") as logf:
                        ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        logf.write(f"[{ts_str}] Model: Holt-Winters Triple ES | Accuracy: {accuracy:.1f}% | MAPE: {mape:.1f}%\n")
                except Exception:
                    pass
    else:
        forecast_series = []
        print("  ⚠ Insufficient weekly data for Holt-Winters (need ≥8 weeks). Skipped.")

    # ── STEP 3: Event Forecast JSON ──────────────────────────────────
    print("\nSTEP 3: Building event forecast output...")

    # Monthly event impact summary
    monthly_impact = {}
    for ev in events_out:
        month = ev["date"][:7]
        if month not in monthly_impact:
            monthly_impact[month] = {"event_count": 0, "total_crowd": 0, "max_risk": "LOW", "events": []}
        monthly_impact[month]["event_count"] += 1
        monthly_impact[month]["total_crowd"] += ev["crowd_size"]
        monthly_impact[month]["events"].append(ev["name"])
        # Keep worst risk
        risk_order = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
        if risk_order.get(ev["risk_level"], 0) > risk_order.get(monthly_impact[month]["max_risk"], 0):
            monthly_impact[month]["max_risk"] = ev["risk_level"]

    event_forecast_out = {
        "model": "Holt-Winters Triple Exponential Smoothing",
        "historical_weekly": [{"week_start": w["week_start"], "count": w["count"]} for w in weekly],
        "forecast": forecast_series,
        "monthly_impact": [
            {"month": k, **v} for k, v in sorted(monthly_impact.items())
        ],
        "upcoming_critical": [
            ev for ev in events_out if ev["risk_level"] in ("CRITICAL", "HIGH") and ev["days_from_today"] >= 0
        ][:10],
        "total_events": len(events_out),
        "generated_at": datetime.now().isoformat(),
    }

    save_json("event_forecast.json", event_forecast_out)
    print(f"  ✓ Event-aware forecast: {len(forecast_series)} weeks ahead")
    print(f"  ✓ Upcoming critical events: {len(event_forecast_out['upcoming_critical'])}")
    print(f"\n  ✅ Event Calendar Engine complete!")


if __name__ == "__main__":
    main()
