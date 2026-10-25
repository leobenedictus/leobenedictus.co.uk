#!/usr/bin/env python3
"""Rebuild writing.html from the Interesting Data Substack feed.

Substack's RSS feed only carries the most recent 20 posts, so every post we
see is kept in data/substack-posts.json and merged with each new fetch. That
way older posts stay on the page after they drop out of the feed.

Run from anywhere:  python3 scripts/build_writing.py
Uses only the Python standard library.
"""

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

FEED_URL = "https://leobenedictus.substack.com/feed"
SOURCES = [
    FEED_URL,
    "https://api.allorigins.win/raw?url=" + urllib.parse.quote(FEED_URL, safe=""),
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/141.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "data" / "substack-posts.json"
TEMPLATE = ROOT / "scripts" / "writing-template.html"
OUTPUT = ROOT / "writing.html"

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def fetch_feed():
    """Return the feed's posts, trying Substack directly and then a proxy.

    Substack sometimes refuses requests from cloud servers such as GitHub's,
    so we look like a browser, retry, and fall back to a public proxy.
    """
    errors = []
    for url in SOURCES:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    posts = parse_feed(resp.read())
                if posts:
                    return posts
                errors.append(f"{url}: no posts in response")
            except urllib.error.HTTPError as exc:
                body = exc.read(200).decode("utf-8", "replace")
                errors.append(f"{url}: HTTP {exc.code} {body!r}")
            except (OSError, ET.ParseError) as exc:
                errors.append(f"{url}: {exc}")
            time.sleep(5 * (attempt + 1))
    print("\n".join(errors))
    return []


def plain_text(fragment):
    """Strip tags and entities from an HTML fragment."""
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def summarise(item):
    """Use the post's subtitle; fall back to the first two sentences."""
    summary = plain_text(item.findtext("description"))
    if summary:
        return summary
    body = plain_text(item.findtext(CONTENT_NS))
    sentences = re.split(r"(?<=[.!?])\s+", body)
    summary = " ".join(sentences[:2])
    if len(summary) > 300:
        summary = summary[:297].rsplit(" ", 1)[0] + "…"
    return summary


def parse_feed(xml_bytes):
    posts = []
    for item in ET.fromstring(xml_bytes).findall("./channel/item"):
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate")
        if not link or not pub:
            continue
        posts.append({
            "title": plain_text(item.findtext("title")),
            "link": link,
            "date": parsedate_to_datetime(pub).date().isoformat(),
            "summary": summarise(item),
        })
    return posts


def load_archive():
    if ARCHIVE.exists():
        return json.loads(ARCHIVE.read_text(encoding="utf-8"))
    return []


def merge(archive, fresh):
    # Feed entries win, so edited titles and subtitles are picked up.
    by_link = {p["link"]: p for p in archive}
    by_link.update({p["link"]: p for p in fresh})
    return sorted(by_link.values(), key=lambda p: (p["date"], p["title"]), reverse=True)


def format_date(iso):
    year, month, day = (int(n) for n in iso.split("-"))
    return f"{day} {MONTHS[month - 1]} {year}"


def render_post(post):
    e = html.escape
    return (
        '        <article class="post">\n'
        f'            <time class="post-date" datetime="{e(post["date"])}">{format_date(post["date"])}</time>\n'
        f'            <h2 class="post-title"><a href="{e(post["link"])}" target="_blank" rel="noopener">{e(post["title"])}</a></h2>\n'
        f'            <p class="post-summary">{e(post["summary"])}</p>\n'
        '        </article>'
    )


def write_if_changed(path, text):
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def main():
    fresh = fetch_feed()
    if not fresh:
        # A warning rather than a failure, so a Substack outage doesn't send
        # an email every six hours. It shows on the run's page in Actions.
        print("::warning::Couldn't read the Substack feed; "
              "writing.html left unchanged.")
        return

    posts = merge(load_archive(), fresh)
    page = TEMPLATE.read_text(encoding="utf-8").replace(
        "{{POSTS}}", "\n".join(render_post(p) for p in posts))

    changed = write_if_changed(
        ARCHIVE, json.dumps(posts, indent=2, ensure_ascii=False) + "\n")
    changed = write_if_changed(OUTPUT, page) or changed
    print(f"{len(posts)} posts ({len(fresh)} in feed); "
          f"{'updated' if changed else 'no changes'}.")


if __name__ == "__main__":
    main()
