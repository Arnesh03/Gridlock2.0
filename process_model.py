import csv
import json
from collections import defaultdict, Counter
import datetime
from datetime import timedelta

INPUT_FILE = 'jan to may police violation_anonymized791b166.csv'
OUTPUT_FILE = 'data/model_weights.json'

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

def process_model():
    print("Extracting rigorous interaction matrix...")
    
    total_valid = 0
    # counts[station][weekday][hour]
    interaction_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
    # Track days for quota
    day_of_month_counts = Counter()
    
    # Track unique dates to compute true averages per weekday
    unique_dates = set()
    unique_weekdays = Counter()
    
    with open(INPUT_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i % 50000 == 0:
                print(f"Processed {i} rows...")
                
            if row['validation_status'] in ('rejected', 'duplicate'):
                continue
                
            dt_obj = parse_datetime(row['created_datetime'])
            if not dt_obj:
                continue
                
            weekday = dt_obj.strftime('%A')
            hour = dt_obj.hour
            day_of_month = dt_obj.day
            
            # Store date part for unique days
            unique_dates.add(dt_obj.date())
            
            station = row['police_station']
            if not station or station == 'NULL':
                station = 'Unknown'
                
            total_valid += 1
            interaction_counts[station][weekday][hour] += 1
            day_of_month_counts[day_of_month] += 1

    # Calculate actual number of occurrences for each weekday (e.g. 21 Mondays)
    for d in unique_dates:
        unique_weekdays[d.strftime('%A')] += 1
        
    num_days = len(unique_dates)
    if num_days == 0:
        num_days = 152
        
    print(f"Total valid rows: {total_valid}, Unique Days: {num_days}")
    
    # Build Interaction Matrix Averages
    # matrix[station][weekday] = [avg_hr_0, avg_hr_1, ..., avg_hr_23]
    interaction_matrix = {}
    
    for station, days in interaction_counts.items():
        interaction_matrix[station] = {}
        for weekday in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            num_specific_weekdays = unique_weekdays[weekday] if unique_weekdays[weekday] > 0 else 1
            
            hour_averages = []
            for h in range(24):
                total_h = days[weekday][h]
                avg_h = round(total_h / num_specific_weekdays, 3)
                hour_averages.append(avg_h)
            
            interaction_matrix[station][weekday] = hour_averages
            
    # Quota Multiplier (Global)
    first_25 = sum(day_of_month_counts[d] for d in range(1, 26))
    last_rest = sum(day_of_month_counts[d] for d in range(26, 32))
    
    avg_first_25 = first_25 / 25
    avg_last_rest = last_rest / 5.5 # Approx 5.5
    
    quota_mult = round(avg_last_rest / avg_first_25, 3) if avg_first_25 > 0 else 1.0
    
    # Sort stations alphabetically for the UI dropdown
    sorted_stations = sorted([s for s in interaction_matrix.keys() if s != 'Unknown'])
    
    output = {
        'interaction_matrix': interaction_matrix,
        'quota_multiplier': quota_mult,
        'stations': sorted_stations
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f)
        
    print("Rigorous interaction matrix exported successfully.")

if __name__ == '__main__':
    process_model()
