import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import store
from data import TF, get_pair, normalize_symbol
from zones import analyze

st.set_page_config(page_title="Zones 5★ SMC", layout="wide")
st.title("Zones SMC — OB · Imbalance · OTE")

DEFAULT_SYMBOLS = "EURUSD,XAUUSD,XAGUSD,DAX40,ETC"

with st.sidebar:
    symbols = [normalize_symbol(s) for s in st.text_input("Symboles (forex, indices, commodités)", DEFAULT_SYMBOLS).split(",") if s.strip()]
    tf = st.selectbox("Unité de temps", list(TF), index=1)
    min_stars = st.slider("Étoiles minimum", 1, 5, 5)
    refresh = st.slider("Rafraîchissement (s)", 15, 120, 30)


@st.cache_data(ttl=15, show_spinner=False)
def load(sym, tf):
    df, htf, src = get_pair(sym, tf)
    return df, htf, analyze(df, htf), src


def draw(sym, df, zones):
    d = df.tail(150)
    fig = go.Figure(go.Candlestick(x=d.index, open=d.open, high=d.high, low=d.low, close=d.close, name=sym))
    for _, z in zones[zones.t0 >= d.index[0]].iterrows():
        col = "0,160,90" if z.side == "bull" else "210,50,50"
        bottom, top = min(z.bottom, z.top), max(z.bottom, z.top)
        fig.add_shape(type="rect", x0=z.t0, x1=d.index[-1], y0=bottom, y1=top,
                      fillcolor=f"rgba({col},0.25)", line=dict(color=f"rgb({col})", width=1))
        if z.fvg:
            fvg_bottom, fvg_top = min(z.fvg), max(z.fvg)
            fig.add_shape(type="rect", x0=z.t0, x1=d.index[-1], y0=fvg_bottom, y1=fvg_top,
                          fillcolor="rgba(120,120,255,0.18)", line_width=0)
        for y in z.ote:
            fig.add_shape(type="line", x0=z.t0, x1=d.index[-1], y0=y, y1=y, line=dict(color="gold", dash="dot", width=1))
        fig.add_annotation(x=z.t0, y=top, text="★" * z.stars, showarrow=False, yshift=10)
    fig.update_layout(xaxis_rangeslider_visible=False, height=520, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)


@st.fragment(run_every=f"{refresh}s")
def live():
    frames, tables = {}, []
    for s in symbols:
        try:
            df, _, z, src = load(s, tf)
        except Exception as e:
            st.warning(f"{s}: {e}")
            continue
        frames[s] = (df, z, src)
        z = z[z.stars >= min_stars]
        if len(z):
            tables.append(z.assign(symbole=s, prix=round(float(df.close.iloc[-1]), 4)))
    st.caption(f"Mis à jour {pd.Timestamp.now():%H:%M:%S} — {len(tables)} symbole(s) avec zone ≥ {min_stars}★")
    if tables:
        t = pd.concat(tables)[["symbole", "side", "stars", "bottom", "top", "prix", "dist_pct", "in_zone", "criteres"]]
        st.dataframe(t.sort_values(["stars", "in_zone"], ascending=False), use_container_width=True, hide_index=True)
    sel = st.selectbox("Graphique", list(frames))
    if sel:
        df, z, src = frames[sel]
        st.caption(f"Source des données : {src}")
        draw(sel, df, z[z.stars >= max(1, min_stars - 1)])


def stats():
    if not store.enabled():
        st.info("Supabase non configuré (secrets SUPABASE_URL et SUPABASE_KEY).")
        return
    try:
        d = pd.DataFrame(store.all_zones())
    except Exception as e:
        st.warning(f"Erreur Supabase : {e}")
        return
    if d.empty:
        st.info("Aucune zone enregistrée pour l'instant : le scanner GitHub Actions doit tourner quelques heures.")
        return
    g = d.groupby("stars").agg(
        zones=("id", "count"),
        gagnants=("outcome", lambda s: int((s == "win").sum())),
        perdants=("outcome", lambda s: int((s == "loss").sum())),
        en_cours=("outcome", lambda s: int(s.isin(["pending", "open"]).sum())),
    )
    done = g.gagnants + g.perdants
    g["taux_%"] = (100 * g.gagnants / done.where(done > 0)).round(1)
    st.dataframe(g, use_container_width=True)
    st.bar_chart(g["taux_%"])
    st.caption("Gagnant = le prix touche la zone puis atteint +2R (R = hauteur de la zone) avant de casser son bord opposé. "
               "Seuil de rentabilité : 33 % (hors frais). Peu de zones résolues = chiffres peu fiables.")


tab_live, tab_stats = st.tabs(["Live", "Stats"])
with tab_live:
    live()
with tab_stats:
    stats()

