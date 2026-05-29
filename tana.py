import requests
import pandas as pd
import time
import random
import re

from html import unescape
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://pb.tana.moe/api/collections"

OUTPUT_FILE = "tana_full_database.xlsx"

PER_PAGE = 500

MIN_DELAY = 0.5
MAX_DELAY = 1.5

TIMEOUT = 60

# ============================================================
# SESSION + RETRY
# ============================================================

session = requests.Session()
session.verify = False

retry = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)

adapter = HTTPAdapter(max_retries=retry)

session.mount("https://", adapter)
session.mount("http://", adapter)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json"
}

# ============================================================
# HELPERS
# ============================================================

def sleep_random():
    """
    Randomized polite delay.
    """
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def clean_html(text):
    """
    Remove HTML tags and clean formatting.
    """

    if not text:
        return ""

    text = unescape(text)

    text = re.sub(
        r"</p>",
        "\n\n",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"<[^>]+>",
        "",
        text
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


def safe_get(d, *keys):

    current = d

    for k in keys:

        if not isinstance(current, dict):
            return None

        current = current.get(k)

    return current


def extract_cover_urls(images):

    if not images:
        return []

    urls = []

    if isinstance(images, list):

        for img in images:

            if isinstance(img, dict):

                if "1280w" in img:

                    urls.append(
                        "https://pb.tana.moe/api/files/"
                        + img["1280w"]
                    )

    elif isinstance(images, dict):

        if "1280w" in images:

            urls.append(
                "https://pb.tana.moe/api/files/"
                + images["1280w"]
            )

    return urls


# ============================================================
# STORAGE
# ============================================================

book_rows = []
publication_rows = []
release_rows = []
title_rows = []
publisher_rows = []

# ============================================================
# FETCH ALL BOOKS
# ============================================================

print("=" * 80)
print("CRAWLING TANA DATABASE")
print("=" * 80)

page = 1

while True:

    print(f"\n[PAGE {page}]")

    url = (
        f"{BASE_URL}/books/records"
        f"?page={page}"
        f"&perPage={PER_PAGE}"
        f"&sort=-updated"
        f"&skipTotal=true"
        f"&expand="
        f"publication,"
        f"publication.release,"
        f"publication.release.publisher,"
        f"publication.release.partner,"
        f"publication.release.title,"
        f"publication.release.title.genres,"
        f"publication.release.title.demographic,"
        f"publication.release.title.format"
        f"&fields="
        f"id,"
        f"edition,"
        f"price,"
        f"publishDate,"
        f"note,"
        f"created,"
        f"updated,"
        f"expand.publication.id,"
        f"expand.publication.name,"
        f"expand.publication.volume,"
        f"expand.publication.subtitle,"
        f"expand.publication.description,"
        f"expand.publication.defaultBook,"
        f"expand.publication.metadata,"
        f"expand.publication.updated,"
        f"expand.publication.expand.release.id,"
        f"expand.publication.expand.release.name,"
        f"expand.publication.expand.release.type,"
        f"expand.publication.expand.release.status,"
        f"expand.publication.expand.release.digital,"
        f"expand.publication.expand.release.updated,"
        f"expand.publication.expand.release.expand.publisher.id,"
        f"expand.publication.expand.release.expand.publisher.name,"
        f"expand.publication.expand.release.expand.publisher.slug,"
        f"expand.publication.expand.release.expand.partner.id,"
        f"expand.publication.expand.release.expand.partner.name,"
        f"expand.publication.expand.release.expand.title.id,"
        f"expand.publication.expand.release.expand.title.name,"
        f"expand.publication.expand.release.expand.title.slug,"
        f"expand.publication.expand.release.expand.title.slugGroup,"
        f"expand.publication.expand.release.expand.title.description,"
        f"expand.publication.expand.release.expand.title.metadata,"
        f"expand.publication.expand.release.expand.title.updated,"
        f"expand.publication.expand.release.expand.title.expand.genres.name,"
        f"expand.publication.expand.release.expand.title.expand.demographic.name,"
        f"expand.publication.expand.release.expand.title.expand.format.name"
    )

    response = session.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT, verify = False
    )

    print("HTTP:", response.status_code)

    if response.status_code == 429:

        print("RATE LIMITED")
        print("Sleeping 30 seconds...")

        time.sleep(30)

        continue

    response.raise_for_status()

    data = response.json()

    items = data.get("items", [])

    if not items:

        print("No more pages.")
        break

    print("Books fetched:", len(items))

    # ========================================================
    # PROCESS ITEMS
    # ========================================================

    for idx, book in enumerate(items, start=1):

        try:

            publication = safe_get(
                book,
                "expand",
                "publication"
            ) or {}

            release = safe_get(
                publication,
                "expand",
                "release"
            ) or {}

            title = safe_get(
                release,
                "expand",
                "title"
            ) or {}

            publisher = safe_get(
                release,
                "expand",
                "publisher"
            ) or {}

            partner = safe_get(
                release,
                "expand",
                "partner"
            ) or {}

            genres = safe_get(
                title,
                "expand",
                "genres"
            ) or []

            genre_names = [
                g.get("name")
                for g in genres
                if g.get("name")
            ]

            demographic = safe_get(
                title,
                "expand",
                "demographic",
                "name"
            )

            format_name = safe_get(
                title,
                "expand",
                "format",
                "name"
            )

            raw_volume = publication.get("volume")

            volume_number = None

            if isinstance(raw_volume, int):
                volume_number = raw_volume // 10000

            title_description = clean_html(
                title.get("description", "")
            )

            publication_description = clean_html(
                publication.get("description", "")
            )

            publication_images = extract_cover_urls(
                safe_get(
                    publication,
                    "metadata",
                    "images"
                )
            )

            title_images = extract_cover_urls(
                safe_get(
                    title,
                    "metadata",
                    "images"
                )
            )

            # ====================================================
            # BOOK ROW
            # ====================================================

            book_rows.append({

                "book_id": book.get("id"),

                "publication_id": publication.get("id"),

                "release_id": release.get("id"),

                "title_id": title.get("id"),

                "book_title": publication.get("name"),

                "series_title": title.get("name"),

                "edition": book.get("edition"),

                "volume_index_raw": raw_volume,

                "volume_number": volume_number,

                "publisher": publisher.get("name"),

                "imprint": partner.get("name"),

                "release_name": release.get("name"),

                "release_type": release.get("type"),

                "release_status": release.get("status"),

                "demographic": demographic,

                "format": format_name,

                "genres": ", ".join(genre_names),

                "price": book.get("price"),

                "publish_date": book.get("publishDate"),

                "title_description": title_description,

                "publication_description": publication_description,

                "note": book.get("note"),

                "publication_cover_urls":
                    "\n".join(publication_images),

                "title_cover_urls":
                    "\n".join(title_images),

                "slug": title.get("slug"),

                "slug_group": title.get("slugGroup"),

                "created": book.get("created"),

                "updated": book.get("updated")
            })

            # ====================================================
            # PUBLICATION ROW
            # ====================================================

            publication_rows.append({

                "publication_id": publication.get("id"),

                "name": publication.get("name"),

                "release_id": release.get("id"),

                "default_book": publication.get(
                    "defaultBook"
                ),

                "volume_raw": raw_volume,

                "volume_number": volume_number,

                "subtitle": publication.get(
                    "subtitle"
                ),

                "description":
                    publication_description,

                "updated":
                    publication.get("updated")
            })

            # ====================================================
            # RELEASE ROW
            # ====================================================

            release_rows.append({

                "release_id": release.get("id"),

                "name": release.get("name"),

                "title_id": title.get("id"),

                "publisher_id": publisher.get("id"),

                "partner_id": partner.get("id"),

                "publisher_name":
                    publisher.get("name"),

                "partner_name":
                    partner.get("name"),

                "type":
                    release.get("type"),

                "status":
                    release.get("status"),

                "digital":
                    release.get("digital"),

                "updated":
                    release.get("updated")
            })

            # ====================================================
            # TITLE ROW
            # ====================================================

            title_rows.append({

                "title_id": title.get("id"),

                "name": title.get("name"),

                "slug": title.get("slug"),

                "slug_group":
                    title.get("slugGroup"),

                "demographic":
                    demographic,

                "format":
                    format_name,

                "genres":
                    ", ".join(genre_names),

                "description":
                    title_description,

                "updated":
                    title.get("updated")
            })

            # ====================================================
            # PUBLISHER ROW
            # ====================================================

            if publisher:

                publisher_rows.append({

                    "publisher_id":
                        publisher.get("id"),

                    "publisher_name":
                        publisher.get("name"),

                    "slug":
                        publisher.get("slug")
                })

        except Exception as e:

            print("ERROR PROCESSING BOOK")
            print(e)

    # ========================================================
    # PAGE SUMMARY
    # ========================================================

    print(
        f"TOTAL BOOKS SO FAR: "
        f"{len(book_rows):,}"
    )

    # ========================================================
    # PERIODIC SAVE
    # ========================================================

    if page % 10 == 0:

        print("Saving checkpoint...")

        pd.DataFrame(book_rows).to_csv(
            "books_checkpoint.csv",
            index=False
        )

    # ========================================================
    # NEXT PAGE
    # ========================================================

    if len(items) < PER_PAGE:
        break

    page += 1

    sleep_random()

# ============================================================
# DATAFRAMES
# ============================================================

books_df = pd.DataFrame(book_rows)

publications_df = pd.DataFrame(
    publication_rows
).drop_duplicates()

releases_df = pd.DataFrame(
    release_rows
).drop_duplicates()

titles_df = pd.DataFrame(
    title_rows
).drop_duplicates()

publishers_df = pd.DataFrame(
    publisher_rows
).drop_duplicates()

# ============================================================
# SAVE EXCEL
# ============================================================

print("\nSaving Excel file...")

with pd.ExcelWriter(
    OUTPUT_FILE,
    engine="openpyxl"
) as writer:

    books_df.to_excel(
        writer,
        sheet_name="books",
        index=False
    )

    publications_df.to_excel(
        writer,
        sheet_name="publications",
        index=False
    )

    releases_df.to_excel(
        writer,
        sheet_name="releases",
        index=False
    )

    titles_df.to_excel(
        writer,
        sheet_name="titles",
        index=False
    )

    publishers_df.to_excel(
        writer,
        sheet_name="publishers",
        index=False
    )

# ============================================================
# FINAL STATS
# ============================================================

print("\n" + "=" * 80)
print("CRAWL COMPLETE")
print("=" * 80)

print("Books:", len(books_df))
print("Publications:", len(publications_df))
print("Releases:", len(releases_df))
print("Titles:", len(titles_df))
print("Publishers:", len(publishers_df))

print("\nSaved:", OUTPUT_FILE)