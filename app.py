"""Historique des zones dans Supabase (API REST, sans dépendance supplémentaire)."""
import os

import requests


def _cfg():
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    if not (url and key):
        return None
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    return url.rstrip("/") + "/rest/v1", headers


def enabled() -> bool:
    return _cfg() is not None


def _safe_req(method, params=None, json=None, prefer=None):
    cfg = _cfg()
    if cfg is None:
        return None
    base, headers = cfg
    if prefer:
        headers = {**headers, "Prefer": prefer}
    try:
        r = requests.request(method, f"{base}/zones", headers=headers, params=params, json=json, timeout=20)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"[store] erreur HTTP: {e}")
        return None


def _in(values):
    values = [str(v) for v in values]
    return "in.(" + ",".join(f'"{v}"' for v in values) + ")"


def existing_ids(ids):
    r = _safe_req("GET", {"select": "id", "id": _in(ids)})
    if r is None:
        return set()
    try:
        return {x["id"] for x in r.json()}
    except Exception:
        return set()


def insert_zones(rows):
    if not rows:
        return
    r = _safe_req("POST", {"on_conflict": "id"}, rows, "resolution=ignore-duplicates,return=minimal")
    return r


def not_entry_alerted(ids):
    if not ids:
        return set()
    r = _safe_req("GET", {"select": "id", "id": _in(ids), "entry_alerted": "eq.false"})
    if r is None:
        return set()
    try:
        return {x["id"] for x in r.json()}
    except Exception:
        return set()


def patch(zone_id, **fields):
    if not zone_id:
        return None
    return _safe_req("PATCH", {"id": f"eq.{zone_id}"}, fields, "return=minimal")


def open_zones():
    r = _safe_req("GET", {"select": "id,symbol,tf,side,bottom,top,t_imp,outcome", "outcome": _in(["pending", "open"])})
    if r is None:
        return []
    try:
        return r.json()
    except Exception:
        return []


def all_zones():
    r = _safe_req("GET", {"select": "id,symbol,tf,side,stars,outcome,created_at", "order": "created_at.desc", "limit": 5000})
    if r is None:
        return []
    try:
        return r.json()
    except Exception:
        return []
