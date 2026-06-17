import csv
import json
import math
from collections import defaultdict, Counter

INPUT_FILE = 'jan to may police violation_anonymized791b166.csv'
OUTPUT_FILE = 'data/bias.json'

import datetime
from datetime import timedelta

def parse_datetime(dt_str):
    if not dt_str or dt_str == "NULL":
        return None
    try:
        clean = dt_str.strip()
        for suffix in ["+00:00", "+0000", "+00"]:
            if clean.endswith(suffix):
                clean = clean[:-len(suffix)]
                break
        utc_dt = datetime.datetime.strptime(clean.strip(), "%Y-%m-%d %H:%M:%S")
        return utc_dt + timedelta(hours=5, minutes=30)
    except (ValueError, AttributeError):
        try:
            parts = clean.split("+")[0].split("-00")[0].strip()
            utc_dt = datetime.datetime.strptime(parts, "%Y-%m-%d %H:%M:%S.%f")
            return utc_dt + timedelta(hours=5, minutes=30)
        except (ValueError, AttributeError):
            return None

def is_low_severity(veh, vtypes):
    if veh in ('SCOOTER', 'MOPED', 'MOTOR CYCLE'):
        # If it's just wrong parking or no parking, it's low severity.
        # But if it's main road or footpath, it's higher.
        if "PARKING IN A MAIN ROAD" not in vtypes and "DOUBLE PARKING" not in vtypes and "PARKING ON FOOTPATH" not in vtypes:
            return True
    return False

def is_high_severity(veh, vtypes):
    if veh in ('HGV', 'LORRY/GOODS VEHICLE', 'BUS (BMTC/KSRTC)', 'MAXI-CAB', 'PRIVATE BUS', 'TEMPO'):
        return True
    if "PARKING IN A MAIN ROAD" in vtypes or "DOUBLE PARKING" in vtypes or "PARKING ON FOOTPATH" in vtypes:
        return True
    return False

def process_bias():
    print("Starting bias detection...")
    
    city_vehicles = Counter()
    station_vehicles = defaultdict(Counter)
    
    station_severity = defaultdict(lambda: {'low': 0, 'high': 0, 'total': 0})
    
    # Month tracking for quota hunting (day of month)
    city_day_of_month = Counter()
    
    total_valid = 0
    
    with open(INPUT_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i % 50000 == 0:
                print(f"Processed {i} rows...")
                
            if row['validation_status'] in ('rejected', 'duplicate'):
                continue
                
            veh = row['vehicle_type']
            if not veh or veh == 'NULL':
                continue
                
            station = row['police_station']
            if not station or station == 'NULL':
                continue
                
            try:
                vtypes = json.loads(row['violation_type']) if row['violation_type'] != 'NULL' else []
            except:
                vtypes = []
                
            dt = row['created_datetime']
            day_of_month = -1
            dt_obj = parse_datetime(dt)
            if dt_obj:
                day_of_month = dt_obj.day
                    
            total_valid += 1
            city_vehicles[veh] += 1
            station_vehicles[station][veh] += 1
            station_severity[station]['total'] += 1
            
            if is_low_severity(veh, vtypes):
                station_severity[station]['low'] += 1
            elif is_high_severity(veh, vtypes):
                station_severity[station]['high'] += 1
                
            if day_of_month > 0:
                city_day_of_month[day_of_month] += 1

    print("Data read complete. Calculating metrics...")
    
    # 1. City baseline percentages
    city_veh_pct = {k: v / total_valid for k, v in city_vehicles.items()}
    
    # Calculate daily average for first 25 days vs last 5 days
    first_25 = sum(city_day_of_month[d] for d in range(1, 26))
    last_rest = sum(city_day_of_month[d] for d in range(26, 32))
    
    avg_first_25 = first_25 / 25
    avg_last_rest = last_rest / 5.5 # Approx 5.5 days on avg depending on month length
    
    quota_spike_pct = ((avg_last_rest - avg_first_25) / avg_first_25 * 100) if avg_first_25 > 0 else 0

    # 2. Station Bias Scoring
    station_metrics = []
    
    for station, s_data in station_severity.items():
        if s_data['total'] < 1000: # Ignore stations with too few tickets for statistical significance
            continue
            
        low_count = s_data['low']
        high_count = s_data['high']
        # Smooth ratio to avoid div by zero
        easy_target_ratio = low_count / (high_count + 1)
        
        # Vehicle deviation
        s_total = sum(station_vehicles[station].values())
        veh_deviation = 0
        for veh, city_pct in city_veh_pct.items():
            if city_pct > 0.05: # Only compare against major vehicle types (>5%)
                s_pct = station_vehicles[station].get(veh, 0) / s_total
                veh_deviation += abs(s_pct - city_pct)
        
        # Apply shrinkage factor so small stations don't dominate the top
        shrinkage = s_total / (s_total + 1000)
        normalized_bias = veh_deviation * shrinkage
        
        station_metrics.append({
            'station': station,
            'total_tickets': s_data['total'],
            'easy_target_ratio': round(easy_target_ratio, 2),
            'bias_score': round(normalized_bias * 100, 2),
            'vehicle_distribution': {veh: round(station_vehicles[station].get(veh, 0)/s_total*100, 1) for veh in city_veh_pct if city_veh_pct[veh] > 0.05}
        })
        
    # Sort to find most biased
    station_metrics.sort(key=lambda x: x['bias_score'], reverse=True)
    
    # Calculate city-wide easy target ratio for KPI
    city_low = sum(s['low'] for s in station_severity.values())
    city_high = sum(s['high'] for s in station_severity.values())
    city_easy_ratio = city_low / (city_high + 1)
    
    # Daily temporal data for area chart
    temporal_chart = []
    for d in range(1, 32):
        temporal_chart.append({'day': d, 'count': city_day_of_month.get(d, 0)})
        
    output_data = {
        'city_easy_target_ratio': round(city_easy_ratio, 2),
        'quota_spike_pct': round(quota_spike_pct, 1),
        'most_biased_station': station_metrics[0]['station'] if station_metrics else 'N/A',
        'temporal_distribution': temporal_chart,
        'station_metrics': station_metrics,
        'city_baseline': {veh: round(pct*100, 1) for veh, pct in city_veh_pct.items() if pct > 0.05}
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output_data, f)
        
    print(f"Bias detection complete! Saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    process_bias()
