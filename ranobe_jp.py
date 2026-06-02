import asyncio
import aiohttp
import random
import pandas as pd

BASE_URL = "https://ranobedb.org/api/v0"
OUTPUT_EXCEL = "ranobedb_flat.xlsx"

CONCURRENT_REQUESTS = 8
BATCH_SIZE = 500

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


def parse_date(v):
    if not v:
        return None

    try:
        return pd.to_datetime(
            str(v),
            format="%Y%m%d",
            errors="coerce"
        )
    except Exception:
        return None


def build_image_url(image_obj):
    if not image_obj:
        return None

    filename = image_obj.get("filename")

    if not filename:
        return None

    return f"https://ranobedb.org/covers/{filename}"


def get_display_name(obj):
    return obj.get("romaji") or obj.get("name")


async def fetch_json(session, url):
    retries = 6

    for attempt in range(retries):
        try:
            async with session.get(url, timeout=60) as response:
                if response.status == 200:
                    return await response.json()

                if response.status in [429, 500, 502, 503, 504]:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    print(f"[{response.status}] sleep {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue

                print(f"[WARN] {response.status} {url}")
                return None

        except Exception as e:
            print("[ERROR]", e)
            await asyncio.sleep(2)

    return None


async def crawl_index(session):
    rows = []
    page = 1

    while True:
        print(f"[INDEX] PAGE {page}")

        url = f"{BASE_URL}/series?page={page}&limit=100"
        data = await fetch_json(session, url)

        if not data:
            break

        series = data.get("series", [])

        if not series:
            break

        for item in series:
            rows.append({
                "series_id": item.get("id"),
                "title": item.get("title"),
                "romaji": item.get("romaji"),
                "title_orig": item.get("title_orig"),
                "romaji_orig": item.get("romaji_orig"),
                "lang": item.get("lang"),
                "num_books": item.get("c_num_books")
            })

        page += 1
        await asyncio.sleep(random.uniform(0.2, 0.8))

    return pd.DataFrame(rows)


async def fetch_detail(session, semaphore, row):
    sid = row["series_id"]

    async with semaphore:
        await asyncio.sleep(random.uniform(0.1, 0.5))

        url = f"{BASE_URL}/series/{sid}"
        response = await fetch_json(session, url)

        if not response:
            return None

        data = response.get("series", {})

        if not data:
            return None

        books = data.get("books", [])
        latest_book = None

        if books:
            latest_book = max(
                books,
                key=lambda x: x.get("c_release_date", 0) or 0
            )

        image_url = build_image_url(
            latest_book.get("image") if latest_book else None
        )

        # STAFF
        authors = []
        artists = []

        for s in data.get("staff", []):
            role = (s.get("role_type") or "").lower()
            lang = s.get("lang")
            name = get_display_name(s)

            if not name:
                continue

            # Prefer original Japanese credit, but romaji name
            if lang != "ja":
                continue

            if role == "author":
                authors.append(name)

            if role in ["artist", "illustrator"]:
                artists.append(name)

        # GENRES
        genres = []

        for tag in data.get("tags", []):
            if tag.get("ttype") == "genre" and tag.get("name"):
                genres.append(tag["name"])

        genre = " | ".join(sorted(set(genres)))

        # IMPRINT
        imprint = None
        publishers = data.get("publishers", [])

        jp_imprints = [
            p for p in publishers
            if p.get("lang") == "ja"
            and p.get("publisher_type") == "imprint"
        ]

        jp_publishers = [
            p for p in publishers
            if p.get("lang") == "ja"
            and p.get("publisher_type") == "publisher"
        ]

        if jp_imprints:
            imprint = get_display_name(jp_imprints[0])
        elif jp_publishers:
            imprint = get_display_name(jp_publishers[0])

        return {
            "series_id": row["series_id"],
            "title": row["title"],
            "romaji": row["romaji"],
            "title_orig": row["title_orig"],
            "romaji_orig": row["romaji_orig"],
            "lang": row["lang"],
            "num_books": row["num_books"],
            "description": data.get("description"),
            "aliases": " | ".join(data.get("aliases", [])),
            "start_date": parse_date(data.get("start_date")),
            "end_date": parse_date(data.get("end_date")),
            "image_url": image_url,
            "author": " | ".join(sorted(set(authors))),
            "artist": " | ".join(sorted(set(artists))),
            "genre": genre,
            "imprint": imprint
        }


async def main():
    connector = aiohttp.TCPConnector(
        limit=CONCURRENT_REQUESTS,
        limit_per_host=4,
        ttl_dns_cache=300
    )

    timeout = aiohttp.ClientTimeout(total=60)
    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession(
        headers=HEADERS,
        connector=connector,
        timeout=timeout
    ) as session:

        index_df = await crawl_index(session)

        print(f"\n[INDEX COUNT] {len(index_df)}")

        rows = index_df.to_dict("records")
        results = []

        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]

            print(f"\n[BATCH] {start} -> {start + len(batch)}")

            tasks = [
                fetch_detail(session, semaphore, row)
                for row in batch
            ]

            batch_results = await asyncio.gather(*tasks)

            results.extend([
                x for x in batch_results
                if x
            ])

            await asyncio.sleep(random.uniform(3, 8))

    df = pd.DataFrame(results)

    df.to_excel(
        OUTPUT_EXCEL,
        index=False
    )

    print("\n[DONE]")
    print(df.shape)


if __name__ == "__main__":
    asyncio.run(main())