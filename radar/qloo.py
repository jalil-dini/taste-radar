"""Qloo Taste AI client for the hackathon environment.

Two calls do the work:
  search(name)            -> the Qloo entity a person named ("Phoebe Bridgers", "The Bear", "tacos")
  brands_for(entity_ids)  -> brands that people with that taste also like, via /v2/insights

Set QLOO_API_KEY in .env. With QLOO_MOCK=1 the client answers from tests/fixtures so the app runs without a key.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://hackathon.api.qloo.com"


def _load_env():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()
MOCK = os.environ.get("QLOO_MOCK") == "1"


def _get(path, params):
    if MOCK:
        name = path.strip("/").replace("/", "_") + ".json"
        return json.load(open(os.path.join(ROOT, "tests", "fixtures", name)))
    key = os.environ.get("QLOO_API_KEY", "")
    if not key:
        raise RuntimeError("Set QLOO_API_KEY in .env (or QLOO_MOCK=1 to try the app with sample data).")
    url = BASE + path + "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"X-Api-Key": key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError("Qloo returned HTTP %d for %s: %s" % (e.code, path, e.read().decode()[:200]))


def _entities(payload):
    """Qloo wraps lists differently per endpoint; find the list of entities wherever it sits."""
    if isinstance(payload, list):
        return payload
    results = payload.get("results", payload)
    if isinstance(results, list):
        return results
    return results.get("entities", []) if isinstance(results, dict) else []


def search(name, types=None):
    params = {"query": name, "take": 3}
    if types:
        params["types"] = types
    found = _entities(_get("/search", params))
    return [{"id": e.get("entity_id") or e.get("id"), "name": e.get("name"), "types": e.get("types", [])} for e in found]


def _brand_entities(entity_ids, take, popularity_max=None):
    params = {"filter.type": "urn:entity:brand", "signal.interests.entities": ",".join(entity_ids), "take": take}
    if popularity_max:
        params["filter.popularity.max"] = popularity_max
    return _entities(_get("/v2/insights", params))


def brands_for(entity_ids, take=24, famous=8, small_cap=0.9):
    """The best-known matches, then smaller brands (popularity under small_cap). Big brands rarely give things away;
    small and indie brands are the ones that mail stickers and samples, so most slots go to them."""
    seen, picked = set(), []
    for batch in (_brand_entities(entity_ids, famous), _brand_entities(entity_ids, take, small_cap)):
        for e in batch:
            key = e.get("entity_id") or e.get("id")
            if key not in seen and len(picked) < take:
                seen.add(key)
                picked.append(e)
    out = []
    for e in picked:
        props = e.get("properties") or {}
        out.append({"id": e.get("entity_id") or e.get("id"), "name": e.get("name"),
                    "affinity": (e.get("query") or {}).get("affinity") or e.get("affinity"),
                    "popularity": e.get("popularity"),
                    "website": props.get("official_site") or props.get("website") or props.get("url") or "",
                    "tags": [t.get("name") for t in e.get("tags", [])[:5] if isinstance(t, dict)]})
    return out
