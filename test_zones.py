import numpy as np, pandas as pd
from zones import analyze

def build(flip=False):
    rows = []
    for t in range(25):
        o = 100 + 0.3 * np.sin(t); c = o + (0.2 if t % 2 else -0.2)
        rows.append([o, max(o, c) + .4, min(o, c) - .4, c])
    rows[15][1] = 102.5
    rows += [[101.2, 101.4, 100.4, 100.6], [100.7, 104.1, 100.65, 104], [104, 105, 102.5, 104.6], [104.6, 105.5, 104.2, 105.2]]
    rows += [[105, 105.4, 104, 105.1]] * 6
    a = np.array(rows)
    if flip:
        a = 200 - a[:, [0, 2, 1, 3]]
    idx = pd.date_range("2026-01-05 09:00", periods=len(a), freq="5min")
    return pd.DataFrame(a, columns=["open", "high", "low", "close"], index=idx)

def htf(up=True):
    c = np.linspace(80, 105, 80) if up else np.linspace(120, 95, 80)
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c})

r = analyze(build(), htf(True)); print(r[["side", "bottom", "top", "stars", "criteres"]])
assert r.iloc[0].stars == 5 and r.iloc[0].side == "bull"
r = analyze(build(True), htf(False)); print(r[["side", "bottom", "top", "stars", "criteres"]])
assert r.iloc[0].stars == 5 and r.iloc[0].side == "bear"
print("OK")
