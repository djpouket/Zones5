"""Historique des zones dans Supabase (API REST, sans dépendance supplémentaire)."""
import os

import requests


def _cfg():
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    if not (url and key):
        return None
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):            # ancienne clé service_role (JWT) ; les clés sb_secret_... vont dans apikey seul
        headers["Authorization"] = f"Bearer {key}"
    return url.rstrip("/") + "/rest/v1", headers


def enabled() -> bool:
    return _cfg() is not None


def _req(method, params=None, json=None, prefer=None):
    base, headers = _cfg()
    if prefer:
        headers = {**headers, "Prefer": prefer}
    r = requests.request(method, f"{base}/zones", headers=headers, params=params, json=json, timeout=20)
    r.raise_for_status()
    return r


def _in(values):
    return "in.(" + ",".join(f'"{v}"' for v in values) + ")"


def existing_ids(ids):
    return {x["id"] for x in _req("GET", {"select": "id", "id": _in(ids)}).json()}


def insert_zones(rows):
    _req("POST", {"on_conflict": "id"}, rows, "resolution=ignore-duplicates,return=minimal")


def not_entry_alerted(ids):
    return {x["id"] for x in _req("GET", {"select": "id", "id": _in(ids), "entry_alerted": "eq.false"}).json()}


def patch(zone_id, **fields):
    _req("PATCH", {"id": f"eq.{zone_id}"}, fields, "return=minimal")


def open_zones():
    return _req("GET", {"select": "id,symbol,tf,side,bottom,top,t_imp,outcome", "outcome": _in(["pending", "open"])}).json()


def all_zones():
    return _req("GET", {"select": "id,symbol,tf,side,stars,outcome,created_at", "order": "created_at.desc", "limit": 5000}).json()
