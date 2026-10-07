import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import store
from data import TF, get_pair, normalize_symbol
from zones import analyze

st.set_page_config(page_title="Zones 5★ SMC", page_icon="📈", layout="wide")

CSS = """
<style>
    .stApp {
        background: radial-gradient(circle at top, #101827 0%, #070b14 48%, #04070d 100%);
        color: #eef2ff;
    }
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }
    [data-testid="stSidebar"] {
        background: rgba(10, 14, 22, 0.94);
        border-right: 1px solid rgba(148, 163, 184, 0.12);
    }
    .metric-card {
        background: linear-gradient(180deg, rgba(15,23,42,0.92), rgba(15,23,42,0.72));
        border: 1px solid rgba(148,163,184,0.15);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.25);
    }
    .kpi-title {
        color: #94a3b8;
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .kpi-value {
        font-size: 1.9rem;
        font-weight: 700;
        margin-top: 0.5rem;
        color: #f8fafc;
    }
    .panel {
        background: rgba(15, 23, 42, 0.82);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 18px;
        padding: 1rem;
    }
    .soft-label {
        color: #94a3b8;
        font-size: 0.75rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

st.title("Zones 5★ SMC")
st.caption("Order Block • Imbalance • OTE • BTC / FX / Indices / Commodités")

DEFAULT_SYMBOLS = "EURUSD=X,XAUUSD=X,XAGUSD=X,^GDAXI,ETC-USD,BTC-USD"

with st.sidebar:
    st.header("Scanner")
    symbols = [normalize_symbol(s) for s in st.text_input("Symboles", DEFAULT_SYMBOLS).split(",") if s.strip()]
    tf = st.selectbox("Unité de temps", list(TF), index=1)
    min_stars = st.slider("Étoiles minimum", 1, 5, 5)
    refresh = st.slider("Rafraîchissement (s)", 10, 120, 20)
    st.caption("Le scanner fonctionne en temps réel et alerte Telegram si la configuration est active.")


@st.cache_data(ttl=15, show_spinner=False)
def load_symbol(sym: str, tf: str):
    df, htf, src = get_pair(sym, tf)
    return df, htf, analyze(df, htf), src


def draw_chart(sym: str, df: pd.DataFrame, zones: pd.DataFrame):
    d = df.tail(220)
    fig = go.Figure(go.Candlestick(x=d.index, open=d.open, high=d.high, low=d.low, close=d.close, name=sym))

    for _, z in zones[zones.t0 >= d.index[0]].iterrows():
        col = "#22c55e" if z.side == "bull" else "#ef4444"
        bottom, top = min(float(z.bottom), float(z.top)), max(float(z.bottom), float(z.top))
        fig.add_shape(type="rect", x0=z.t0, x1=d.index[-1], y0=bottom, y1=top,
                      fillcolor=f"rgba({col},0.22)", line=dict(color=col, width=1))
        if z.fvg:
            fvg_bottom, fvg_top = min(z.fvg), max(z.fvg)
            fig.add_shape(type="rect", x0=z.t0, x1=d.index[-1], y0=fvg_bottom, y1=fvg_top,
                          fillcolor="rgba(96,165,250,0.16)", line_width=0)
        for y in z.ote or []:
            fig.add_shape(type="line", x0=z.t0, x1=d.index[-1], y0=y, y1=y,
                          line=dict(color="#fbbf24", dash="dot", width=1))
        fig.add_annotation(x=z.t0, y=top, text="★" * int(z.stars), showarrow=False, yshift=12,
                           font=dict(size=13, color=col))

    fig.update_layout(
        template="plotly_dark",
        height=560,
        margin=dict(l=0, r=0, t=6, b=0),
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


@st.fragment(run_every=f"{refresh}s")
def live_panel():
    frames = {}
    metrics = []

    for s in symbols:
        try:
            df, _, z, src = load_symbol(s, tf)
            frames[s] = (df, z, src)
            best = z[z.stars >= min_stars].head(1)
            if not best.empty:
                r = best.iloc[0]
                metrics.append({
                    "symbol": s,
                    "side": r.side,
                    "stars": int(r.stars),
                    "price": float(df.close.iloc[-1]),
                    "dist_pct": float(r.dist_pct),
                    "criteres": r.criteres,
                })
        except Exception as e:
            st.warning(f"{s}: {e}")
            continue

    if not frames:
        st.info("Aucune donnée de marché disponible. Vérifie les symboles et la connexion au marché.")
        return

    cols = st.columns(3)
    for i, metric in enumerate(metrics[:3]):
        with cols[i % 3]:
            st.markdown(f"<div class='metric-card'>\n<div class='kpi-title'>{metric['symbol']}</div>\n<div class='kpi-value'>{metric['side'].upper()} · {metric['stars']}★</div>\n<div style='color:#cbd5e1;margin-top:0.4rem;'>Prix {metric['price']:.4f} · {metric['dist_pct']:.2f}%</div>\n<div style='color:#a5b4fc;margin-top:0.4rem;font-size:0.8rem;'>{metric['criteres']}</div>\n</div>", unsafe_allow_html=True)

    selected = st.selectbox("Graphique", list(frames.keys()), index=0)
    df, z, src = frames[selected]
    st.caption(f"Source des données : {src}")
    chart = draw_chart(selected, df, z[z.stars >= max(1, min_stars - 1)])
    st.plotly_chart(chart, use_container_width=True)

    st.markdown("<div class='soft-label'>Sélection de zones</div>", unsafe_allow_html=True)
    table = z[z.stars >= min_stars][["side", "stars", "bottom", "top", "dist_pct", "in_zone", "criteres"]].copy()
    if table.empty:
        st.info("Aucune zone active au seuil actuel. Réduis le minimum d'étoiles ou attends une validation dessus.")
        return

    table["bottom"] = table["bottom"].round(5)
    table["top"] = table["top"].round(5)
    table["dist_pct"] = table["dist_pct"].round(2)
    st.dataframe(table.sort_values(["stars", "dist_pct"], ascending=[False, True]), use_container_width=True, hide_index=True)


live_panel()


# Optional stats block
if store.enabled():
    try:
        d = pd.DataFrame(store.all_zones())
        if not d.empty:
            st.subheader("Historique des zones")
            st.dataframe(d.head(10), use_container_width=True)
    except Exception:
        pass
else:
    st.info("Supabase non configuré : le dashboard fonctionne en live sans stockage historique.")

