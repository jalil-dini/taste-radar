"""For one brand, find a free-item page on the open web and decide, carefully, whether it is a real offer.

Search finds candidate pages; a cheap keyword pass drops obvious misses; then a typed decision model (Jev) answers five
yes/no questions about the page. These are the guards from a form-filling agent, tuned on 48 hand-labelled pages
(see github.com/jalil-dini/field-notes, demo 07). Nothing is ever filled in or submitted here: the app shows the
person how to ask, and they decide.
"""
import html
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
FREE_RE = re.compile(r"free\W+(?:[\w&'-]+\W+){0,2}?(?:stickers?|decals?|samples?|fan packs?|catalogs?|swag)\b|stickers? requests?|request\W+(?:[\w&'-]+\W+){0,3}?(?:stickers?|samples?|catalogs?)\b|fan packs?", re.I)
SKIP_HOSTS = ("facebook.", "instagram.", "reddit.", "pinterest.", "youtube.", "tiktok.", "x.com", "twitter.", "amazon.",
              "ebay.", "etsy.", "redbubble.", "wikipedia.", "linkedin.")
ENDED_RE = re.compile(r"suspend(ed)? (our |all )?(free )?(samples?|stickers?|offers?)|(samples?|stickers?|offer|program) (is|are|has been) (no longer available|discontinued|suspended|paused)"
                      r"|no longer (offer|send|provid)(ing)? (free )?(samples?|stickers?)|(offer|promotion|program) has (ended|expired)|out of (free )?(samples?|stickers?)", re.I)
AGGREGATOR_RE = re.compile(r"freebie|free-?stuff|free-?samples|hunt4freebies|tryspree|ilovefreebies|moneypantry|wallethacks|dollarsanity", re.I)

QUESTIONS = {
    "offer": "Is `page` a form where a person requests a free physical item (sample, stickers, fan pack, catalog) or free information, with no payment? If the page says to request it by mail, with a stamped or self-addressed envelope, or by email instead of with a form, the answer is no. A sign-up form that sends the free item counts.",
    "mail_or_email": "Does `page` tell a person to request a free item by postal mail (for example with a self-addressed stamped envelope) or by email?",
    "sweepstakes": "Is `page` an entry form for a sweepstakes, contest, raffle or prize drawing, where only chosen winners get something? A free item sent to everyone who asks is not one.",
    "cause": "Is `page` run by a political campaign, candidate, advocacy or activist group, petition, religious organization or charity fundraiser, or does sending the form sign the person up to support a cause?",
    "restricted": "Is this offer only for businesses, trade professionals, employees, contractors, members of a program, or existing customers with an order, and not for the general public?",
}


def jev(state, questions):
    key = os.environ.get("JEV_API_KEY", "")
    if not key:
        raise RuntimeError("Set JEV_API_KEY in .env.")
    body = json.dumps({"model": "jev-latest", "state": state, "questions": questions}).encode()
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["answers"]


def search(query):
    from ddgs import DDGS
    try:
        return [r["href"] for r in DDGS().text(query, max_results=8) if r.get("href", "").startswith("http")]
    except Exception:
        return []


def fetch(url, tries=2):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read(600000).decode(r.headers.get_content_charset() or "utf-8", "replace")
        except urllib.error.HTTPError:
            raise                                   # a real answer such as 404: retrying will not change it
        except Exception:
            if attempt == tries - 1:
                raise


def text_of(doc):
    doc = re.sub(r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", doc)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", doc))).strip()


def host(url):
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def slug(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


GUESS_PATHS = ("/stickers", "/free-stickers", "/pages/stickers", "/pages/free-stickers", "/pages/sticker-request",
               "/sticker-request", "/pages/request-stickers", "/request-stickers", "/samples", "/free-sample", "/pages/free-sticker", "/fan-pack", "/catalog-request")


def render(url):
    """Open the page in a headless browser (radar/render.js) and return its visible text and form fields."""
    try:
        out = subprocess.run(["node", os.path.join(os.path.dirname(os.path.abspath(__file__)), "render.js"), url],
                             capture_output=True, text=True, timeout=60).stdout.strip().splitlines()
        data = json.loads(out[-1]) if out else {}
    except Exception:
        return None
    return None if data.get("error") or not data.get("text") else data


def site_answers(h):
    try:
        fetch("https://" + h)
        return True
    except Exception:
        return False


official_site_cache = {}


def official_site(brand):
    site = _official_site(brand)
    official_site_cache[brand["name"]] = site
    return site


def _official_site(brand):
    if brand.get("website"):
        return host(brand["website"])
    s = slug(brand["name"])
    for url in search("%s official site" % brand["name"]):
        h = host(url)
        if not any(b in h for b in SKIP_HOSTS) and len(s) >= 4 and s[:8] in h.replace("-", "").replace(".", ""):
            return h
    guess = slug(brand["name"]) + ".com"          # search can come back empty when rate-limited
    return guess if len(guess) > 6 and site_answers(guess) else ""


def best_excerpt(text):
    """The sentence-sized passage around the free-item mention that reads most like prose."""
    best = None
    for m in FREE_RE.finditer(text):
        around = text[m.start():m.start() + 320]
        cost = code_density(around) + (1.0 if m.start() < 200 else 0.0)   # a mention in the title sits beside the menu
        if best is None or cost < best[0]:
            best = (cost, around)
    return best[1].strip() if best else ""


def candidate_pages(brand):
    """Pages on the brand's own site that may hold a free-item offer: search hits first, then the usual addresses."""
    site = official_site(brand)
    if not site:
        return []
    out = []
    for q in ("%s free stickers" % brand["name"], "%s free sample request" % brand["name"], "site:%s free sticker OR sample" % site):
        for url in search(q):
            if host(url).endswith(site) and url not in out and not re.search(r"confirm|thank|success|cart|checkout|account", url, re.I):
                out.append(url)
    for path in GUESS_PATHS:
        url = "https://%s%s" % (site, path)
        if url not in out:
            out.append(url)
    return out


def form_fields(doc):
    """Labels, placeholders and names of the form controls, which say what the form actually asks for."""
    found = []
    for tag in re.findall(r"<(?:input|select|textarea)\b[^>]*>", doc, re.I):
        if re.search(r'type=["\']?(hidden|submit|button|search)', tag, re.I):
            continue
        m = re.search(r'(?:aria-label|placeholder|name)=["\']([^"\']{2,60})', tag, re.I)
        if m and m.group(1) not in found:
            found.append(m.group(1))
    return found[:25]


def code_density(chunk):
    return sum(chunk.count(c) for c in "{};=<>") / max(len(chunk), 1)


def gate_view(doc, text):
    """What the gate reads: the page title, the prose around a free-item mention, and the form's fields.

    Pages that build their form with JavaScript leave script code in the downloaded text, so the mention chosen is the
    one whose surroundings look least like code."""
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", doc)
    best = None
    for m in FREE_RE.finditer(text):
        around = text[max(0, m.start() - 300):m.end() + 300]
        if best is None or code_density(around) < best[0]:
            best = (code_density(around), m.start())
    start = max(0, best[1] - 600) if best else 0
    fields = form_fields(doc)
    return {"title": text_of(title.group(1)) if title else "", "page": text[start:start + 2200],
            "form_fields": fields or "not readable: the form may be built by JavaScript after the page loads"}


def how_to_ask(doc, text):
    if re.search(r"self[- ]addressed|stamped envelope|\bSASE\b", text, re.I):
        return "mail"
    if len(set(m.lower() for m in re.findall(r'<(?:input|select|textarea)[^>]*(?:name|id|placeholder|aria-label)=["\'][^"\']*?(zip|postal|address|city|state)', doc, re.I))) >= 2:
        return "form"
    if re.search(r"mailto:", doc, re.I):
        return "email"
    return "page"


def check_brand(brand, home=""):
    """Return the best real offer for this brand, or the reason none was found."""
    pages = candidate_pages(brand)
    if not pages:
        return {"brand": brand["name"], "status": "none", "reason": "could not find the brand's own website"}
    skipped, loaded = [], 0
    for url in pages:
        if loaded >= 6:
            break
        if url.startswith("https://" + official_site_cache.get(brand["name"], "~")) and url.endswith(GUESS_PATHS):
            time.sleep(0.4)                         # guessed addresses: go gently, sites rate-limit bursts of 404s
        try:
            doc = fetch(url)
        except Exception:
            continue
        loaded += 1
        text = text_of(doc)
        if not FREE_RE.search(text):
            continue
        qs = {k: {"type": "noul", "instructions": v} for k, v in QUESTIONS.items()}
        if home:
            qs["excluded"] = {"type": "noul", "instructions": "Does `page` limit this offer to a place, such as one city, region or country, that would exclude someone living in %s?" % home}
        view = gate_view(doc, text)
        if isinstance(view["form_fields"], str):          # no form in the HTML: it is drawn by JavaScript
            shown = render(url)
            if shown:
                m = FREE_RE.search(shown["text"])
                start = max(0, m.start() - 600) if m else 0
                view = {"title": view["title"], "page": shown["text"][start:start + 2200], "form_fields": shown["fields"] or "none visible"}
                text = shown["text"]
        if ENDED_RE.search(text):
            skipped.append({"url": url, "reason": "the page says the offer has ended", "scores": None})
            continue
        a = {k: v["noul"] for k, v in jev(view, qs).items()}
        scores = {k: round(v, 2) for k, v in a.items()}
        for name, limit, why in (("sweepstakes", 0.7, "a sweepstakes entry"), ("excluded", 0.6, "limited to another area"),
                                 ("cause", 0.4, "a political, advocacy, religious or fundraising sign-up"),
                                 ("restricted", 0.5, "only for businesses, members or customers")):
            if a.get(name, 0) >= limit:
                skipped.append({"url": url, "reason": why, "scores": scores})
                break
        else:
            route = how_to_ask(doc, text)
            if a["offer"] >= 0.5 or (a["mail_or_email"] >= 0.6 and route in ("mail", "email")):
                return {"brand": brand["name"], "status": "offer", "url": url, "how": route if a["offer"] < 0.5 else "form",
                        "scores": scores, "excerpt": best_excerpt(text)}
            skipped.append({"url": url, "reason": "not a free-item offer", "scores": scores})
    if skipped:
        return {"brand": brand["name"], "status": "skipped", "reason": skipped[0]["reason"], "url": skipped[0]["url"], "scores": skipped[0]["scores"]}
    return {"brand": brand["name"], "status": "none", "reason": "pages found, but none mention a free item"}
