"""Fetch scam/fraud headlines from Google News RSS for each site language.

Runs in GitHub Actions (Google blocks the site host's shared IPs). Writes one JSON file
that vocaguard.com reads from this public repo.

Usage: fetch_scam_news.py <previous.json> <output.json>
A language whose fetch fails keeps its previous headlines. Exits 1 (without
writing) only if every language failed.
"""
import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

MAX_ITEMS = 12

FEEDS = {
    "en": "https://news.google.com/rss/search?q=%22phone+scam%22+OR+%22scam+call%22+OR+%22fraud+arrest%22+OR+%22scammers%22+when:14d&hl=en-US&gl=US&ceid=US:en",
    # (הונאה OR עוקץ OR נוכלים OR נוכל) (טלפון OR שיחה OR וואטסאפ OR SMS OR התחזות OR נעצרו OR קשישים OR בנק) when:21d
    "he": "https://news.google.com/rss/search?q=(%D7%94%D7%95%D7%A0%D7%90%D7%94%20OR%20%D7%A2%D7%95%D7%A7%D7%A5%20OR%20%D7%A0%D7%95%D7%9B%D7%9C%D7%99%D7%9D%20OR%20%D7%A0%D7%95%D7%9B%D7%9C)%20(%D7%98%D7%9C%D7%A4%D7%95%D7%9F%20OR%20%D7%A9%D7%99%D7%97%D7%94%20OR%20%D7%95%D7%95%D7%90%D7%98%D7%A1%D7%90%D7%A4%20OR%20SMS%20OR%20%D7%94%D7%AA%D7%97%D7%96%D7%95%D7%AA%20OR%20%D7%A0%D7%A2%D7%A6%D7%A8%D7%95%20OR%20%D7%A7%D7%A9%D7%99%D7%A9%D7%99%D7%9D%20OR%20%D7%91%D7%A0%D7%A7)%20when%3A21d&hl=he&gl=IL&ceid=IL:he",
    "ru": "https://news.google.com/rss/search?q=%D0%BC%D0%BE%D1%88%D0%B5%D0%BD%D0%BD%D0%B8%D0%BA%D0%B8+%D1%82%D0%B5%D0%BB%D0%B5%D1%84%D0%BE%D0%BD+when:14d&hl=ru&gl=RU&ceid=RU:ru",
    "ar": "https://news.google.com/rss/search?q=%D8%A7%D8%AD%D8%AA%D9%8A%D8%A7%D9%84+%D9%87%D8%A7%D8%AA%D9%81%D9%8A+when:14d&hl=ar&gl=AE&ceid=AE:ar",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VocaGuardNews/1.0)",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.5",
    "Cookie": "SOCS=CAI; CONSENT=YES+",
}


def fetch(url: str) -> str:
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
            if not body.lstrip().startswith("<?xml"):
                raise ValueError(f"not RSS: {body[:120]!r}")
            return body
        except Exception as e:  # noqa: BLE001 - log and retry any failure
            last_err = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(last_err)


def parse(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    seen, items = set(), []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        source = (item.findtext("source") or "").strip()
        if not title or not url.startswith("https://"):
            continue
        # Google News titles end with " - Source"; the source is shown separately.
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)].strip()
        if title.lower() in seen:
            continue
        seen.add(title.lower())
        published = None
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "").astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
        items.append({"title": title, "source": source, "url": url, "published": published})
    items.sort(key=lambda i: i["published"] or "", reverse=True)
    return items[:MAX_ITEMS]


def main() -> int:
    prev_path, out_path = sys.argv[1], sys.argv[2]
    try:
        with open(prev_path, encoding="utf-8") as f:
            prev = json.load(f).get("langs", {})
    except (OSError, ValueError):
        prev = {}

    langs, fresh = {}, 0
    for lang, url in FEEDS.items():
        try:
            items = parse(fetch(url))
            if not items:
                raise RuntimeError("0 items")
            langs[lang] = items
            fresh += 1
            print(f"{lang}: {len(items)} headlines")
        except Exception as e:  # noqa: BLE001
            langs[lang] = prev.get(lang, [])
            print(f"::warning::{lang}: fetch failed ({e}); keeping {len(langs[lang])} previous headlines")
        time.sleep(2)

    if fresh == 0:
        print("::error::Every language failed; leaving the published file unchanged")
        return 1

    out = {"updated": datetime.now(timezone.utc).isoformat(), "langs": langs}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
