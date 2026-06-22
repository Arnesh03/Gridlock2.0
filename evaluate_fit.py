import json

with open("data/time_series.json") as f:
    data = json.load(f)

# The pipeline already drops the last incomplete week
weekly = [w["count"] for w in data["weekly"]]

def sma(y, window=4):
    preds = []
    # Train predictions (in-sample)
    for i in range(window, len(y)):
        preds.append((y[i], sum(y[i-window:i]) / window))
    return preds

evals = sma(weekly, 4)
train_evals = evals[:-4]
test_evals = evals[-4:]

train_errors = [abs(actual - pred)/actual for actual, pred in train_evals]
test_errors = [abs(actual - pred)/actual for actual, pred in test_evals]

train_mape = sum(train_errors)/len(train_errors) * 100 if train_errors else 0
test_mape = sum(test_errors)/len(test_errors) * 100 if test_errors else 0

residuals = [(actual - pred) for actual, pred in test_evals]
bias = sum(residuals) / len(residuals) if residuals else 0

print(f"Train MAPE (In-sample): {train_mape:.1f}%")
print(f"Test MAPE (Out-of-sample): {test_mape:.1f}%")
print(f"Test Residuals: {[round(r) for r in residuals]}")
print(f"Mean Error (Bias): {bias:.1f}")

