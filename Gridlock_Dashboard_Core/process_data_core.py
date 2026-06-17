import csv
import json
import math
from collections import defaultdict, Counter

INPUT_FILE = '../jan to may police violation_anonymized791b166.csv'
OUTPUT_DIR = 'data'

def process():
    print("Starting data processing for Dashboard Core...")
    
    total_violations = 0
    filtered_violations = 0
    
    grid_cells = defaultdict(lambda: {
        'count': 0,
        'violations': Counter(),
        'vehicles': Counter(),
        'dates': set(),
        'junctions': Counter(),
        'stations': Counter(),
        'locations': Counter(),
    })
    
    violation_totals = Counter()
    station_totals = Counter()
    
    with open(INPUT_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            total_violations += 1
            if i % 50000 == 0:
                print(f"Processed {i} rows...")
                
            if row['validation_status'] in ('rejected', 'duplicate'):
                continue
                
            filtered_violations += 1
            
            lat_str = row['latitude']
            lng_str = row['longitude']
            if not lat_str or not lng_str or lat_str == 'NULL' or lng_str == 'NULL':
                continue
            
            lat = float(lat_str)
            lng = float(lng_str)
            
            # 0.001 deg ~ 111m grid
            grid_lat = round(lat, 3)
            grid_lng = round(lng, 3)
            
            try:
                v_types = json.loads(row['violation_type']) if row['violation_type'] != 'NULL' else []
            except:
                v_types = []
                
            v_veh = row['vehicle_type'] if row['vehicle_type'] != 'NULL' else 'UNKNOWN'
            
            dt = row['created_datetime']
            date_only = dt.split(' ')[0] if dt and dt != 'NULL' else None
            
            cell = grid_cells[(grid_lat, grid_lng)]
            cell['count'] += 1
            for vt in v_types:
                cell['violations'][vt] += 1
                violation_totals[vt] += 1
            cell['vehicles'][v_veh] += 1
            if date_only:
                cell['dates'].add(date_only)
            
            junc = row['junction_name']
            if junc and junc != 'No Junction':
                cell['junctions'][junc] += 1
                
            station = row['police_station']
            if station:
                cell['stations'][station] += 1
                station_totals[station] += 1
                
            loc = row['location']
            if loc:
                cell['locations'][loc] += 1
                
    print(f"Finished reading. Total: {total_violations}, Kept: {filtered_violations}")
    
    # Heatmap
    print("Generating heatmap.json...")
    heatmap_data = []
    max_count = max((c['count'] for c in grid_cells.values()), default=1)
    for (lat, lng), data in grid_cells.items():
        heatmap_data.append([lat, lng, data['count'] / max_count])
    
    with open(f'{OUTPUT_DIR}/heatmap.json', 'w') as f:
        json.dump(heatmap_data, f)
        
    # Hotspots & CIS
    print("Generating hotspots.json...")
    hotspots = []
    
    severity_weights = {
        'PARKING IN A MAIN ROAD': 3,
        'DOUBLE PARKING': 3,
        'PARKING ON FOOTPATH': 2.5,
        'NO PARKING': 2,
        'WRONG PARKING': 1.5,
        'PARKING NEAR BUSTOP/SCHOOL/HOSPITAL ETC': 2.5,
        'PARKING NEAR ROAD CROSSING': 2.5
    }
    
    vehicle_weights = {
        'HGV': 3, 'LORRY/GOODS VEHICLE': 3, 'BUS (BMTC/KSRTC)': 3,
        'MAXI-CAB': 2.5, 'PRIVATE BUS': 2.5, 'TEMPO': 2.5,
        'CAR': 2, 'JEEP': 2, 'VAN': 2,
        'PASSENGER AUTO': 1.5, 'GOODS AUTO': 1.5,
        'SCOOTER': 1, 'MOTOR CYCLE': 1, 'MOPED': 1
    }
    
    all_dates_len = 152 # Approx Nov to Apr
    
    raw_cis_values = []
    
    for (lat, lng), data in grid_cells.items():
        if data['count'] < 10:
            continue
            
        sev_score = sum(data['violations'][vt] * severity_weights.get(vt, 1) for vt in data['violations'])
        veh_score = sum(data['vehicles'][vt] * vehicle_weights.get(vt, 1) for vt in data['vehicles'])
        
        has_junction = len(data['junctions']) > 0
        junc_mult = 1.5 if has_junction else 1.0
        
        persistence = len(data['dates']) / all_dates_len
        
        c = data['count']
        raw_cis = (math.log(1 + c) * 5) + (sev_score / c * 15) + (veh_score / c * 10) + (persistence * 20) + (junc_mult * 10)
        raw_cis_values.append(raw_cis)
        
        junc = data['junctions'].most_common(1)[0][0] if data['junctions'] else 'No Junction'
        station = data['stations'].most_common(1)[0][0] if data['stations'] else 'Unknown'
        loc = data['locations'].most_common(1)[0][0] if data['locations'] else ''
        
        hotspots.append({
            'id': f"zone_{lat}_{lng}",
            'lat': lat,
            'lng': lng,
            'total_violations': c,
            'raw_cis': raw_cis,
            'violation_types': dict(data['violations'].most_common(3)),
            'vehicle_types': dict(data['vehicles'].most_common(3)),
            'junction': junc,
            'police_station': station,
            'label': loc[:60] + ('...' if len(loc) > 60 else '')
        })
        
    if raw_cis_values:
        min_cis = min(raw_cis_values)
        max_cis = max(raw_cis_values)
        range_cis = max_cis - min_cis if max_cis > min_cis else 1
        
        for h in hotspots:
            # Normalize to 0-100
            h['cis'] = round(((h['raw_cis'] - min_cis) / range_cis) * 100, 1)
            del h['raw_cis']
            
    hotspots.sort(key=lambda x: x['cis'], reverse=True)
    hotspots = hotspots[:150] # Top 150
    
    with open(f'{OUTPUT_DIR}/hotspots.json', 'w') as f:
        json.dump(hotspots, f)
        
    # Summary
    print("Generating summary.json...")
    summary = {
        "total_violations": total_violations,
        "filtered_violations": filtered_violations,
        "critical_hotspots": len([h for h in hotspots if h['cis'] >= 75]),
        "avg_daily": int(filtered_violations / all_dates_len),
        "top_violation": violation_totals.most_common(1)[0][0] if violation_totals else "",
        "top_station": station_totals.most_common(1)[0][0] if station_totals else "",
        "violation_breakdown": dict(violation_totals.most_common(6)),
        "top_stations": [{"name": k, "count": v} for k, v in station_totals.most_common(10)]
    }
    
    with open(f'{OUTPUT_DIR}/summary.json', 'w') as f:
        json.dump(summary, f)
        
    print("Done!")

if __name__ == '__main__':
    process()
