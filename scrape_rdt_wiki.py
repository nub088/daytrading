#!/usr/bin/env python3
"""Scrape selected high-probability setup posts from r/RealDayTrading wiki.

Pipeline:
  1. GET /r/RealDayTrading/wiki/index.json → extract every reddit post
     link from the wiki markdown.
  2. Match a hand-curated CURATED list (date + title substring) against
     the link map.
  3. For each match, GET the post's /.json → extract title, body, and
     top comments.
  4. Save one text file per post into realdaytrading-wiki/.

Reddit's public JSON API works without auth on public subs. Use a
descriptive User-Agent (Reddit policy bans default library UAs).
Sleep ~1.2s between requests to stay under the 60/min unauth limit.

Excludes options-specific posts per the request — focus is on the
high-probability daily/intraday setup canon (RS/RW, screening, M5+D1,
top-tier filters, daily-chart leaning).
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import requests

OUTPUT_DIR = Path("/home/nublet/Projects/daytrading/realdaytrading-wiki")
OUTPUT_DIR.mkdir(exist_ok=True)
WIKI_JSON = "https://www.reddit.com/r/RealDayTrading/wiki/index.json"
UA = "daytrading-research/0.1 (personal study; non-commercial)"
HEADERS = {"User-Agent": UA}
SLEEP_S = 1.2
TOP_COMMENTS = 10

# Curated for high-probability daily/intraday setup work. NO options
# threads, NO pure mindset/macro/journal posts. Each tuple is
# (iso_date, title_substring). The substring is matched case-insensitive
# against the wiki's anchor text.
CURATED: list[tuple[str, str]] = [
    # --- The "top-tier" canon ---
    ("2022-04-02", "Method for Finding Highest Probability Trades"),
    ("2022-04-12", "Method for Picking the Best Trades"),
    ("2022-07-10", "Trading only Highest Probability Setup Trades"),
    ("2022-12-26", "Highest Probability Trade Setups"),
    ("2022-04-23", "Trading Criteria to Use for Top-Tier Trades"),
    # --- Rules / process / simple frameworks ---
    ("2022-02-18", "Keeping It Really Simple"),
    ("2022-09-11", "Stick To The Process"),
    ("2021-07-25", "A Simple Strategy"),
    ("2021-06-14", "Simple and Effective Day Trading Method"),
    ("2022-07-09", "This Criteria for Reading the Market"),
    # --- D1 + M5 mechanics ---
    ("2022-08-27", "How to Lean on the Daily Chart"),
    ("2023-03-05", "Great D1 and Great M5"),
    ("2021-12-01", "How To Day Trade Relative Strength"),
    ("2021-11-16", "How To Trade Relative Strength"),
    # --- Screening / scanning ---
    ("2021-07-18", "How to Use Screeners"),
    ("2022-03-03", "How To Find Stocks With RS/RW"),
    # --- Big "must-read" thread the wiki itself flags ---
    ("2023-10-23", "This Post Will Make You A Lot of Money Now"),
]

POST_LINK_RE = re.compile(
    r"\[([^\]]+)\]\((https?://(?:www\.|old\.|new\.)?reddit\.com/r/RealDayTrading/comments/[^)\s]+)\)"
)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80].strip("-")


def get_wiki_links() -> dict[str, str]:
    """Return {anchor_text: canonical_post_url} from the wiki markdown."""
    r = requests.get(WIKI_JSON, headers=HEADERS, timeout=30)
    r.raise_for_status()
    md = r.json()["data"]["content_md"]
    out: dict[str, str] = {}
    for m in POST_LINK_RE.finditer(md):
        text = m.group(1).strip()
        url = re.sub(r"\\_", "_", m.group(2).strip())  # unescape \_ from md
        url = re.sub(r"\?.*$", "", url)
        if not url.endswith("/"):
            url += "/"
        # Keep first occurrence (titles can repeat across sections).
        out.setdefault(text, url)
    return out


def find_match(links: dict[str, str], substring: str) -> str | None:
    needle = substring.lower()
    for text, url in links.items():
        if needle in text.lower():
            return url
    return None


def fetch_post(url: str) -> tuple[str, str, list[str]]:
    """Return (title, body_md, list[formatted_top_comment_str]) for a post."""
    json_url = url.rstrip("/") + ".json"
    r = requests.get(json_url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    listings = r.json()
    post = listings[0]["data"]["children"][0]["data"]
    title = post.get("title", "")
    body = post.get("selftext", "") or ""
    comments: list[str] = []
    for child in listings[1]["data"]["children"]:
        if child.get("kind") != "t1":
            continue
        c = child.get("data", {})
        b = (c.get("body") or "").strip()
        if not b or b.startswith(("[removed]", "[deleted]")):
            continue
        author = c.get("author", "?")
        score = c.get("score", 0)
        comments.append(f"--- u/{author} ({score} pts) ---\n{b}")
    return title, body, comments


def main() -> int:
    print(f"Fetching wiki index: {WIKI_JSON}")
    try:
        links = get_wiki_links()
    except Exception as e:
        print(f"ERROR fetching wiki: {e}")
        return 1
    print(f"Found {len(links)} reddit-post links in the wiki\n")

    missing: list[tuple[str, str]] = []
    saved = 0
    for date, substr in CURATED:
        print(f"[{date}] {substr}")
        url = find_match(links, substr)
        if not url:
            print("  -> NOT FOUND in wiki markdown")
            missing.append((date, substr))
            continue
        print(f"  -> {url}")
        try:
            title, body, comments = fetch_post(url)
        except Exception as e:
            print(f"  ERROR fetching post: {e}")
            missing.append((date, substr))
            continue
        fname = f"{date}-{slugify(substr)}.txt"
        out_path = OUTPUT_DIR / fname
        with out_path.open("w", encoding="utf-8") as f:
            f.write(f"# {title}\n")
            f.write(f"Source: {url}\nDate: {date}\n\n")
            f.write(body if body else "[no self-text]\n")
            f.write("\n\n" + "=" * 60 + "\n")
            f.write(f"Top {TOP_COMMENTS} comments\n")
            f.write("=" * 60 + "\n\n")
            for c in comments[:TOP_COMMENTS]:
                f.write(c + "\n\n")
        size = out_path.stat().st_size
        print(f"  -> saved {fname} ({size:,} bytes)")
        saved += 1
        time.sleep(SLEEP_S)

    print(f"\nDone. Saved {saved} / {len(CURATED)} posts to {OUTPUT_DIR}")
    if missing:
        print(f"\n{len(missing)} posts NOT FOUND — adjust substring matching:")
        for d, s in missing:
            print(f"  [{d}] {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
