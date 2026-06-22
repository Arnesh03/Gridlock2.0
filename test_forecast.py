import json

with open("data/time_series.json") as f:
    data = json.load(f)

weekly = data["weekly"][:-1] # drop incomplete week

train = [w["count"] for w in weekly[-12:-4]]
test = [w["count"] for w in weekly[-4:]]

def holt(y, alpha=0.6, beta=0.4):
    level = y[0]
    trend = y[1] - y[0]
    for i in range(1, len(y)):
        last = level
        level = alpha * y[i] + (1 - alpha) * (last + trend)
        trend = beta * (level - last) + (1 - beta) * trend
    forecasts = []
    curr = trend
    for i in range(4):
        curr *= 0.9
        forecasts.append(max(0, level + curr * (i+1)))
    return forecasts

def sma(y, window=4):
    val = sum(y[-window:]) / window
    return [val] * 4

for name, func in [("Holt", lambda y: holt(y)), ("SMA-4", lambda y: sma(y, 4))]:
    pred = func(train)
    errors = [abs(a-p)/a for a, p in zip(test, pred) if a > 0]
    mape = sum(errors)/len(errors) * 100 if errors else 0
    print(f"{name}: MAPE = {mape:.1f}%")
