"""Moteur SMC : Order Blocks + Imbalance (FVG) + OTE -> note de 1 à 5 étoiles.

Critères (1 point chacun) :
  1. OB valide : bougie opposée avant un déplacement fort (>= k*ATR) qui casse la structure (BOS)
  2. Imbalance : un FVG créé par l'impulsion, collé à l'OB
  3. OTE : l'OB ou le FVG chevauche la zone 62%-79% de la jambe d'impulsion
  4. Fraîche : prix jamais revenu toucher l'OB depuis sa formation (et non invalidée)
  5. Biais HTF aligné (EMA50 + pente sur la unité de temps supérieure)
"""
import numpy as np
import pandas as pd

OTE = (0.62, 0.79)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n, min_periods=3).mean()


def htf_bias(htf: pd.DataFrame | None) -> int:
    if htf is None or len(htf) < 30:
        return 0
    ema = htf["close"].ewm(span=50, adjust=False).mean()
    up = htf["close"].iloc[-1] > ema.iloc[-1] and ema.iloc[-1] > ema.iloc[-5]
    dn = htf["close"].iloc[-1] < ema.iloc[-1] and ema.iloc[-1] < ema.iloc[-5]
    return 1 if up else -1 if dn else 0


def _flip(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {"open": -df["open"], "high": -df["low"], "low": -df["high"], "close": -df["close"]},
        index=df.index,
    )


def _detect_zone(df: pd.DataFrame, n: int = 3, k: float = 1.3) -> list[dict]:
    o, h, l, c = (df[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    a = atr(df).to_numpy()
    N = len(df)
    swing_highs = [(p, h[p]) for p in range(n, N - n) if h[p] == h[p - n : p + n + 1].max()]
    out, seen = [], set()

    for i in range(n + 2, N):
        ref = a[i - 1]
        if np.isnan(ref):
            continue
        if not (c[i] > o[i] and c[i] - o[i] >= k * ref):
            continue

        j = next((b for b in range(i - 1, max(i - 6, -1), -1) if c[b] < o[b]), None)
        if j is None or j in seen:
            continue

        prev = [p for idx, p in swing_highs if idx + n <= j]
        if not prev or c[i] <= prev[-1]:
            continue

        seen.add(j)
        ob_bot, ob_top = l[j], h[j]
        if (c[i + 1 :] < ob_bot).any():
            continue

        leg_hi = h[j : min(i + 3, N)].max()
        rng = leg_hi - ob_bot
        if rng <= 0:
            continue

        strength = (c[i] - o[i]) / ref
        if strength < 1.2:
            continue

        fvg = None
        for kk in range(j + 2, min(i + 2, N)):
            if l[kk] > h[kk - 2] and h[kk - 2] <= ob_top + 0.25 * ref:
                fvg = (h[kk - 2], l[kk])
                break

        if fvg is None:
            continue

        ote = (leg_hi - OTE[1] * rng, leg_hi - OTE[0] * rng)
        hit = lambda z: z is not None and z[0] <= ote[1] and z[1] >= ote[0]
        fresh = not (l[j + 1 : i + 1] <= ob_top).any()

        out.append(
            dict(
                j=j,
                i=i,
                ob=(ob_bot, ob_top),
                fvg=fvg,
                ote=ote,
                ote_hit=hit((ob_bot, ob_top)) or hit(fvg),
                fresh=fresh,
                strength=strength,
            )
        )
    return out


def analyze(df: pd.DataFrame, htf: pd.DataFrame | None = None, n: int = 3, k: float = 1.3) -> pd.DataFrame:
    last = float(df["close"].iloc[-1])
    bias = htf_bias(htf)
    rows = []

    for side, d, s in (("bull", df, 1), ("bear", _flip(df), -1)):
        m = (lambda z: z) if s == 1 else (lambda z: None if z is None else (-z[1], -z[0]))
        for z in _detect_zone(d, n, k):
            ob, fvg, ote = m(z["ob"]), m(z["fvg"]), m(z["ote"])
            crit = ["OB+BOS"]
            if fvg:
                crit.append("FVG")
            if z["ote_hit"]:
                crit.append("OTE")
            if z["fresh"]:
                crit.append("Fraîche")
            if bias == s:
                crit.append("HTF")

            rows.append(
                dict(
                    side=side,
                    bottom=ob[0],
                    top=ob[1],
                    fvg=fvg,
                    ote=ote,
                    stars=len(crit),
                    criteres=" · ".join(crit),
                    t0=df.index[z["j"]],
                    t_imp=df.index[z["i"]],
                    dist_pct=round((last - (ob[1] if side == "bull" else ob[0])) / last * 100, 2),
                    in_zone=ob[0] <= last <= ob[1],
                    strength=float(z["strength"]),
                )
            )

    cols = [
        "side",
        "bottom",
        "top",
        "fvg",
        "ote",
        "stars",
        "criteres",
        "t0",
        "t_imp",
        "dist_pct",
        "in_zone",
        "strength",
    ]
    res = pd.DataFrame(rows, columns=cols)
    if res.empty:
        return res

    return res.sort_values(["stars", "strength", "dist_pct"], ascending=[False, False, True]).reset_index(drop=True)


def outcome(df: pd.DataFrame, side: str, bottom: float, top: float, t_imp) -> str:
    d = df[df.index > t_imp]
    if side == "bear":
        lo, hi = -d["high"].to_numpy(float), -d["low"].to_numpy(float)
        bottom, top = -top, -bottom
    else:
        lo, hi = d["low"].to_numpy(float), d["high"].to_numpy(float)

    r = top - bottom
    target = top + 2 * r if side == "bull" else bottom - 2 * r
    touched = False

    for l, h in zip(lo, hi):
        if not touched and l <= top:
            touched = True
        if touched:
            if side == "bull":
                if l <= bottom:
                    return "loss"
                if h >= target:
                    return "win"
            else:
                if h >= top:
                    return "loss"
                if l <= target:
                    return "win"
    return "open" if touched else "pending"

