"""Record a full Taste Radar run so the hosted page (GitHub Pages, no server) can replay it.

  python3 -m radar.snapshot "Trail runner" "Orlando, Florida, USA" "Kilian Jornet" "Outside magazine" "Patagonia"

Writes docs/demo/<slug>.json and adds it to docs/demo/index.json. Every result in a snapshot is a real run: live Qloo
data (unless QLOO_MOCK=1, which the file records), live web pages and live guard decisions, with the time it ran.
"""
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from . import offers, qloo, server

DEMO = os.path.join(server.ROOT, "docs", "demo")


def record(name, home, likes):
    started = time.time()
    t = server.taste(likes, home)
    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(lambda b: offers.check_brand({"name": b["name"], "website": b.get("website", "")}, home), t["brands"]))
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    snap = {"name": name, "home": home, "likes": likes, "understood": t["understood"], "brands": t["brands"], "results": results,
            "recorded": time.strftime("%Y-%m-%d %H:%M"), "seconds": round(time.time() - started), "sample_qloo_data": qloo.MOCK}
    os.makedirs(DEMO, exist_ok=True)
    json.dump(snap, open(os.path.join(DEMO, slug + ".json"), "w"), indent=1)
    index_path = os.path.join(DEMO, "index.json")
    index = json.load(open(index_path)) if os.path.exists(index_path) else []
    index = [i for i in index if i["slug"] != slug] + [{"slug": slug, "name": name, "likes": likes, "home": home}]
    json.dump(index, open(index_path, "w"), indent=1)
    found = sum(r["status"] == "offer" for r in results)
    print("%s: %d brands, %d real offers, %ds -> docs/demo/%s.json" % (name, len(results), found, snap["seconds"], slug))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    record(sys.argv[1], sys.argv[2], sys.argv[3:])
