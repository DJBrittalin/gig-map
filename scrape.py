"""
Gig map scraper.

Opens the gig guide page in a hidden browser, scrolls until every gig has
loaded, pulls out every gig (date, time, acts, venue),
looks up map coordinates for any venue it hasn't seen before, and writes
docs/gigs.json for the map page to read.

Run it by hand:
    python scrape.py https://example.com/gig-guide

Or set the GIG_GUIDE_URL environment variable (the GitHub Action does this).
To test against a saved copy of the page:
    python scrape.py --file saved_page.html --base https://example.com
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
GIGS_FILE = ROOT / "docs" / "gigs.json"
VENUES_FILE = ROOT / "venues.json"

# Nominatim (OpenStreetMap's free geocoder) asks for a real contact in the User-Agent
# and no more than one request per second.
USER_AGENT = os.environ.get("SCRAPER_CONTACT", "gig-map-scraper (personal project)")
GEOCODE_AREA = os.environ.get("GEOCODE_AREA", "Sydney NSW Australia")

# Past gigs older than this are dropped from gigs.json so the file stays small.
KEEP_PAST_DAYS = 30

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
FULL_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}


# ---------- reading the page ----------

def fetch(url):
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    return r.text


def fetch_with_scrolling(url, days_ahead=0, max_minutes=15):
    """
    The gig guide keeps loading more gigs as you scroll, so a plain download only
    gets the first batch. This opens the page in a hidden browser and keeps
    scrolling to the bottom until no new gigs appear (or until gigs are more than
    `days_ahead` days away, if set), then returns the full page.
    """
    from playwright.sync_api import sync_playwright

    stop_date = ((datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                 if days_ahead else None)
    deadline = time.time() + max_minutes * 60

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="networkidle", timeout=60_000)

        count, stalls = 0, 0
        while time.time() < deadline:
            page.mouse.wheel(0, 20_000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            page.wait_for_timeout(800)

            new_count = page.locator(".eventcardhost").count()
            if new_count == count:
                stalls += 1
                if stalls >= 4:  # nothing new after several tries: reached the end
                    break
            else:
                stalls = 0
                count = new_count
                last = page.locator("[data-gigstartdate]").last
                last_date = parse_start(last.get_attribute("data-gigstartdate")) if last.count() else None
                print(f"  {count} gigs loaded" + (f", up to {last_date:%d %b %Y}" if last_date else ""))
                if stop_date and last_date and last_date.strftime("%Y-%m-%d") > stop_date:
                    print(f"  reached {days_ahead} days ahead, stopping")
                    break
        else:
            print(f"  stopped after {max_minutes} minutes", file=sys.stderr)

        html = page.content()
        browser.close()
    return html


def text(el):
    return " ".join(el.get_text(" ", strip=True).split()) if el else ""


def parse_start(value):
    """'Mon Nov 02 2026 18:30:00 GMT+1100 (Australian Eastern Daylight Time)' -> datetime"""
    m = re.search(r"(\w{3}) (\d{1,2}) (\d{4}) (\d{2}):(\d{2}):(\d{2}) GMT([+-])(\d{2})(\d{2})", value or "")
    if not m:
        return None
    mon, day, year, hh, mm, ss, sign, oh, om = m.groups()
    offset = timedelta(hours=int(oh), minutes=int(om)) * (1 if sign == "+" else -1)
    return datetime(int(year), MONTHS[mon], int(day), int(hh), int(mm), int(ss),
                    tzinfo=timezone(offset))


def parse_heading_date(heading):
    """'Monday 2 November 2026' -> '2026-11-02' (used if a card has no start date)."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", heading or "")
    if not m or m.group(2).lower() not in FULL_MONTHS:
        return None
    return f"{m.group(3)}-{FULL_MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def parse_page(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    gigs = []
    for card in soup.select(".eventcardhost"):
        heading = card.find_previous("h3")
        start_el = card.select_one("[data-gigstartdate]")
        id_el = card.select_one("[data-gigid]")
        start = parse_start(start_el["data-gigstartdate"]) if start_el else None

        date = start.strftime("%Y-%m-%d") if start else parse_heading_date(text(heading))
        if not date:
            continue  # can't place it on the calendar

        headliners = [text(h) for h in card.select(".headliner") if text(h)]
        supports = [re.sub(r"^(w/|with)\s*", "", text(p), flags=re.I)
                    for p in card.select(".supports") if text(p)]

        venue_el = card.select_one("a.venue")
        venue_name = text(venue_el)
        venue_href = urljoin(base_url, venue_el["href"]) if venue_el and venue_el.get("href") else ""
        venue_id = (urlparse(venue_href).path.rstrip("/").split("/")[-1]
                    if venue_href else slugify(venue_name))

        # Badges like PWYC / free show up as classes on the card: "freegig pwycgig"
        tags = sorted({c[:-3] for c in card.get("class", [])
                       if c.endswith("gig") and c != "eventcardhost"})

        gig_link = ""
        for a in card.select("a[href]"):
            if a is not venue_el and "/venues/" not in a["href"]:
                gig_link = urljoin(base_url, a["href"])
                break

        gigs.append({
            "id": id_el["data-gigid"] if id_el else f"{date}-{venue_id}-{slugify(' '.join(headliners))}",
            "date": date,
            "start": start.isoformat() if start else None,
            "time": text(card.select_one(".time")),
            "headliners": headliners,
            "supports": supports,
            "venue": venue_id,
            "tags": tags,
            "link": gig_link,
            "_venue_name": venue_name,
            "_venue_url": venue_href,
        })
    return gigs


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------- venue coordinates ----------

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def geocode(query):
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "json", "limit": 1, "countrycodes": "au"},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    time.sleep(1.1)  # Nominatim usage policy: max 1 request per second
    r.raise_for_status()
    hits = r.json()
    if hits:
        return float(hits[0]["lat"]), float(hits[0]["lon"])
    return None


def update_venues(gigs, venues, offline=False):
    """Add any new venues to venues.json and look up coordinates for ones missing them."""
    for g in gigs:
        v = venues.setdefault(g["venue"], {"name": g["_venue_name"], "address": "", "lat": None, "lng": None})
        v.setdefault("name", g["_venue_name"])
        if g["_venue_url"]:
            v["url"] = g["_venue_url"]

    missing = [vid for vid, v in venues.items() if v.get("lat") is None and not v.get("skip")]
    for vid in missing:
        v = venues[vid]
        if offline:
            continue
        # Try the street address first if you've typed one in, then the venue name.
        queries = [q for q in (v.get("address"), f"{v['name']}, {GEOCODE_AREA}") if q]
        for q in queries:
            try:
                hit = geocode(q)
            except requests.RequestException as e:
                print(f"  geocode failed for {q!r}: {e}", file=sys.stderr)
                hit = None
            if hit:
                v["lat"], v["lng"] = round(hit[0], 6), round(hit[1], 6)
                print(f"  found {v['name']}: {v['lat']}, {v['lng']}")
                break
        else:
            print(f"  NO LOCATION for {v['name']} - add an address or lat/lng in venues.json",
                  file=sys.stderr)
    return venues


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="gig guide page(s) to read")
    ap.add_argument("--file", help="read a saved HTML file instead of downloading")
    ap.add_argument("--base", help="site address, used with --file to complete venue links")
    ap.add_argument("--offline", action="store_true", help="skip coordinate lookups")
    ap.add_argument("--simple", action="store_true",
                    help="plain download only (just the first batch of gigs, no scrolling)")
    ap.add_argument("--days-ahead", type=int, default=int(os.environ.get("DAYS_AHEAD", "0") or 0),
                    help="stop scrolling once gigs are this many days away (0 = load everything)")
    args = ap.parse_args()

    urls = args.urls or [u for u in os.environ.get("GIG_GUIDE_URL", "").split() if u]
    if not urls and not args.file:
        ap.error("give a gig guide URL, set GIG_GUIDE_URL, or use --file")

    scraped, html = [], ""
    if args.file:
        scraped += parse_page(Path(args.file).read_text(encoding="utf-8"), args.base or "")
    for url in urls:
        print(f"Reading {url}")
        html = fetch(url) if args.simple else fetch_with_scrolling(url, args.days_ahead)
        scraped += parse_page(html, url)

    # The same gig can appear twice if pages overlap; keep one of each.
    scraped = list({g["id"]: g for g in scraped}.values())
    print(f"Found {len(scraped)} gigs")
    if not scraped:
        # Print what the scraper actually saw, to help work out why
        if urls:
            soup = BeautifulSoup(html, "html.parser")
            print("Page title:", text(soup.title), file=sys.stderr)
            print("Start of page text:", text(soup.body)[:600] if soup.body else "(empty)", file=sys.stderr)
        sys.exit("No gigs found. Check GIG_GUIDE_URL is the gig guide page itself, "
                 "or the site's layout may have changed (see the class names in parse_page()).")

    venues = update_venues(scraped, load_json(VENUES_FILE, {}), offline=args.offline)
    VENUES_FILE.write_text(json.dumps(venues, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Merge with the previous run so recent past days stay browsable.
    previous = load_json(GIGS_FILE, {}).get("gigs", [])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_PAST_DAYS)).strftime("%Y-%m-%d")
    by_id = {g["id"]: g for g in previous if g.get("date", "") >= cutoff and not g.get("sample")}
    for g in scraped:
        by_id[g["id"]] = {k: v for k, v in g.items() if not k.startswith("_")}
    gigs = sorted(by_id.values(), key=lambda g: (g["date"], g.get("start") or "", g["venue"]))

    used = {g["venue"] for g in gigs}
    out = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": urls[0] if urls else args.base or "",
        "venues": {vid: v for vid, v in venues.items() if vid in used},
        "gigs": gigs,
    }
    GIGS_FILE.parent.mkdir(exist_ok=True)
    GIGS_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(gigs)} gigs across {len(used)} venues to {GIGS_FILE}")


if __name__ == "__main__":
    main()
