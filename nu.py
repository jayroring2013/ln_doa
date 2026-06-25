"""
NovelUpdates - Japanese Light Novel Crawler
============================================
Scrapes all Japanese LN entries from the Series Finder.

Fields per novel:
  Title, Genres, Rating, Status, Associated Names, Recommendations,
  activity_week_rank, activity_month_rank, activity_all_time_rank,
  on_reading_lists, reading_list_month_rank, reading_list_all_time_rank,
  related_series_ids, URL

Usage:
  pip install cloudscraper beautifulsoup4 pandas openpyxl
  python crawl_japanese_lns.py

Tip: If your IP is blocked by Cloudflare, set PROXY below or pass
     --proxy http://ip:port on the command line.
"""

import pandas as pd
import time
import argparse
import os
import sys
from datetime import datetime
from bs4 import BeautifulSoup, NavigableString
import cloudscraper

# ━━━ CONFIG ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROXY = None  # e.g. "http://1.2.3.4:8080" — leave None for direct connection

BASE_URL = "https://www.novelupdates.com/series-finder/"
FINDER_PARAMS = {
    "sf": "1",
    "sort": "sdate",
    "order": "desc",
    "pg": 1,
    "nt": "2443",    # Novel Type: Light Novel
    "org": "496",    # Origin: Japanese
}

OUTPUT_FILE = "japanese_light_novels_full.xlsx"
FINDER_DELAY = 2       # seconds between Series Finder pages
NOVEL_DELAY = 1        # seconds between individual novel pages
ERROR_DELAY = 3        # seconds after an error before retrying
MAX_RETRIES = 2        # retries per novel before giving up
MAX_CONSECUTIVE_ERRORS = 5  # stop crawl after this many errors in a row
SAVE_EVERY = 10        # incremental save to disk every N novels
TOTAL_PAGES = 89       # 89 pages × 25 = ~2,225 novels (as of 2026-06-25)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def log(msg):
    """Timestamped log to stdout."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def create_scraper():
    """Create a cloudscraper session (handles Cloudflare JS challenges)."""
    return cloudscraper.create_scraper(delay=5, browser={"timeout": 15})


def get_finder_links(scraper, page, proxies):
    """Fetch one Series Finder page and return a list of novel URLs."""
    FINDER_PARAMS["pg"] = page
    log(f"Fetching Series Finder page {page}...")
    resp = scraper.get(BASE_URL, params=FINDER_PARAMS, proxies=proxies, timeout=15)

    if resp.status_code != 200 or "search_title" not in resp.text:
        raise Exception(f"Bad response: HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.content, "html.parser")
    entries = soup.find_all("div", class_="search_title")
    links = [e.find("a")["href"] for e in entries if e.find("a")]
    log(f"  Found {len(links)} novel links")
    return links


def extract_sidebar_data(soup):
    """
    Parse the sidebar to extract:
      - Activity Stats: weekly / monthly / all-time rank
      - Reading List: user count, monthly / all-time rank
      - Related Series: slugs of linked series
    """
    data = {
        "activity_week_rank": None,
        "activity_month_rank": None,
        "activity_all_time_rank": None,
        "on_reading_lists": None,
        "reading_list_month_rank": None,
        "reading_list_all_time_rank": None,
        "related_series_ids": "",
    }

    # Find the sidebar wrapper that contains .rank spans
    wrapper = None
    for w in soup.select(".wpb_wrapper"):
        if w.select(".rank"):
            wrapper = w
            break
    if not wrapper:
        return data

    section = None  # tracks which h5 section we're inside

    for child in wrapper.children:
        # ── Section headers ──
        if child.name == "h5":
            h5_text = child.get_text(strip=True)
            if "Activity Stats" in h5_text:
                section = "activity"
            elif "Reading List" in h5_text:
                section = "reading"
            elif "Related Series" in h5_text:
                section = "related"
            else:
                section = None
            continue

        # ── Activity Stats section ──
        if section == "activity":
            if isinstance(child, NavigableString):
                label = child.strip()
                if label == "Weekly Rank:":
                    data["activity_week_rank"] = "_PENDING_"
                elif label == "Monthly Rank:":
                    data["activity_month_rank"] = "_PENDING_"
                elif label == "All Time Rank:":
                    data["activity_all_time_rank"] = "_PENDING_"
            elif child.name == "span" and "rank" in child.get("class", []):
                value = child.get_text(strip=True).lstrip("#")
                for key in ("activity_week_rank", "activity_month_rank", "activity_all_time_rank"):
                    if data[key] == "_PENDING_":
                        data[key] = value
                        break

        # ── Reading List section ──
        elif section == "reading":
            if isinstance(child, NavigableString):
                label = child.strip()
                if label == "Monthly Rank:":
                    data["reading_list_month_rank"] = "_PENDING_"
                elif label == "All Time Rank:":
                    data["reading_list_all_time_rank"] = "_PENDING_"
            elif child.name == "b" and "rlist" in child.get("class", []):
                data["on_reading_lists"] = child.get_text(strip=True)
            elif child.name == "span" and "rank" in child.get("class", []):
                value = child.get_text(strip=True).lstrip("#")
                for key in ("reading_list_month_rank", "reading_list_all_time_rank"):
                    if data[key] == "_PENDING_":
                        data[key] = value
                        break

        # ── Related Series section ──
        elif section == "related":
            if child.name == "a" and "/series/" in child.get("href", ""):
                slug = child["href"].rstrip("/").split("/")[-1]
                if slug and "http" not in slug:
                    if data["related_series_ids"]:
                        data["related_series_ids"] += ","
                    data["related_series_ids"] += slug

    # Clean up any unresolved pending values
    for key in data:
        if data[key] == "_PENDING_":
            data[key] = None

    return data


def scrape_novel(scraper, url, proxies):
    """Scrape all fields from a single novel page. Returns a dict."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = scraper.get(url, proxies=proxies, timeout=15)
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")

            soup = BeautifulSoup(resp.content, "html.parser")

            # ── Helper functions ──
            def safe_text(selector):
                try:
                    return soup.select_one(selector).get_text(strip=True)
                except (AttributeError, TypeError):
                    return ""

            def safe_list(selector):
                try:
                    return [a.get_text(strip=True) for a in soup.select(selector)]
                except (AttributeError, TypeError):
                    return []

            title = safe_text(".seriestitlenu")
            if not title:
                raise Exception("No title found — possibly a blocked/captcha page")

            try:
                status = "\n".join(
                    list(soup.select("#editstatus")[0].stripped_strings)
                )
            except (IndexError, AttributeError):
                status = ""

            try:
                associated = "\n".join(
                    list(soup.select("#editassociated")[0].stripped_strings)
                )
            except (IndexError, AttributeError):
                associated = ""

            sidebar = extract_sidebar_data(soup)

            return {
                "Title": title,
                "Genres": ", ".join(safe_list("#seriesgenre a")),
                "Rating": safe_text(".uvotes"),
                "Status": status,
                "Associated Names": associated,
                "Recommendations": ", ".join(
                    safe_list(".wpb_wrapper a[title]")
                ),
                "activity_week_rank": sidebar["activity_week_rank"],
                "activity_month_rank": sidebar["activity_month_rank"],
                "activity_all_time_rank": sidebar["activity_all_time_rank"],
                "on_reading_lists": sidebar["on_reading_lists"],
                "reading_list_month_rank": sidebar["reading_list_month_rank"],
                "reading_list_all_time_rank": sidebar["reading_list_all_time_rank"],
                "related_series_ids": sidebar["related_series_ids"],
                "URL": url,
            }

        except Exception as e:
            if attempt < MAX_RETRIES:
                log(f"    Retry {attempt}/{MAX_RETRIES}: {e}")
                time.sleep(ERROR_DELAY)
            else:
                raise


# ── Column order for the Excel output ──
COLUMNS = [
    "Title",
    "Genres",
    "Rating",
    "Status",
    "Associated Names",
    "Recommendations",
    "activity_week_rank",
    "activity_month_rank",
    "activity_all_time_rank",
    "on_reading_lists",
    "reading_list_month_rank",
    "reading_list_all_time_rank",
    "related_series_ids",
    "URL",
]


def save_to_excel(data, filepath):
    """Save list of dicts to Excel with consistent column order."""
    df = pd.DataFrame(data)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    df[COLUMNS].to_excel(filepath, index=False)


def detect_last_page(scraper, proxies):
    """Check pagination to find total pages (in case it changed)."""
    try:
        FINDER_PARAMS["pg"] = TOTAL_PAGES
        resp = scraper.get(BASE_URL, params=FINDER_PARAMS, proxies=proxies, timeout=15)
        if resp.status_code == 200 and "search_title" in resp.text:
            soup = BeautifulSoup(resp.content, "html.parser")
            links = soup.find_all("div", class_="search_title")
            if links:
                return TOTAL_PAGES
        # If last page is empty, binary search for the real last page
        lo, hi = TOTAL_PAGES // 2, TOTAL_PAGES
        while lo < hi:
            mid = (lo + hi + 1) // 2
            FINDER_PARAMS["pg"] = mid
            r = scraper.get(BASE_URL, params=FINDER_PARAMS, proxies=proxies, timeout=15)
            if r.status_code == 200 and "search_title" in r.text:
                entries = BeautifulSoup(r.content, "html.parser").find_all(
                    "div", class_="search_title"
                )
                if entries:
                    lo = mid
                else:
                    hi = mid - 1
            else:
                hi = mid - 1
        return lo
    except Exception:
        return TOTAL_PAGES


def main():
    global PROXY
    parser = argparse.ArgumentParser(description="Crawl Japanese LNs from NovelUpdates")
    parser.add_argument(
        "--proxy",
        help="HTTP proxy, e.g. http://ip:port",
        default=PROXY,
    )
    parser.add_argument(
        "--output",
        help=f"Output Excel file (default: {OUTPUT_FILE})",
        default=OUTPUT_FILE,
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing output file if it exists",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="Page number to start from (default: 1)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Max pages to crawl (0 = all, default: 0)",
    )
    args = parser.parse_args()

    PROXY = args.proxy
    proxies = {"http": PROXY, "https": PROXY} if PROXY else None

    if PROXY:
        log(f"Using proxy: {PROXY}")
    else:
        log("No proxy — direct connection")

    scraper = create_scraper()

    # ── Resume from existing file? ──
    all_data = []
    start_page = args.start_page

    if args.resume and os.path.exists(args.output):
        existing = pd.read_excel(args.output)
        all_data = existing.to_dict("records")
        estimated_pages = len(all_data) // 25
        start_page = max(start_page, estimated_pages + 1)
        log(f"Resumed: {len(all_data)} existing novels, starting from page {start_page}")
    elif os.path.exists(args.output):
        log(f"File '{args.output}' exists. Use --resume to continue, or delete it first.")
        sys.exit(1)

    # ── Detect actual last page ──
    log("Checking total pages...")
    last_page = detect_last_page(scraper, proxies)
    max_page = min(start_page - 1 + args.max_pages, last_page) if args.max_pages > 0 else last_page
    log(f"Total pages: {last_page}. Crawling pages {start_page} to {max_page}.")

    # ── Main crawl loop ──
    page = start_page
    consecutive_errors = 0

    while page <= max_page:
        # Fetch links from Series Finder
        try:
            links = get_finder_links(scraper, page, proxies)
        except Exception as e:
            log(f"ERROR on finder page {page}: {e}")
            if "403" in str(e) or "1005" in str(e):
                log("Proxy/IP appears blocked by Cloudflare. Stopping.")
                break
            consecutive_errors += 1
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                log(f"Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS}). Stopping.")
                break
            page += 1
            time.sleep(ERROR_DELAY)
            continue

        if not links:
            log(f"Page {page} returned no links. Reached the end.")
            break

        consecutive_errors = 0
        time.sleep(FINDER_DELAY)

        # Crawl each novel on this page
        for link in links:
            try:
                details = scrape_novel(scraper, link, proxies)
                all_data.append(details)
                n = len(all_data)

                log(
                    f"  [{n}] {details['Title'][:60]} | "
                    f"act:W{details['activity_week_rank']} "
                    f"M{details['activity_month_rank']} "
                    f"A{details['activity_all_time_rank']} | "
                    f"rl:{details['on_reading_lists']} "
                    f"M{details['reading_list_month_rank']} "
                    f"A{details['reading_list_all_time_rank']}"
                )

                # Incremental save
                if n % SAVE_EVERY == 0:
                    save_to_excel(all_data, args.output)
                    log(f"  >> Checkpoint: {n} novels saved to disk")

                time.sleep(NOVEL_DELAY)

            except Exception as e:
                log(f"  ERROR scraping {link[-50:]}: {e}")
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    log(f"Too many consecutive errors. Stopping.")
                    break
                time.sleep(ERROR_DELAY)

        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            break

        page += 1

    # ── Final save ──
    if all_data:
        save_to_excel(all_data, args.output)
        log(f"\n{'='*60}")
        log(f"DONE! {len(all_data)} novels saved to '{args.output}'")
        log(f"{'='*60}")
    else:
        log("No novels were crawled.")


if __name__ == "__main__":
    main()