import asyncio
import aiohttp
import aiofiles
import csv
import os
import random
import re

API = "https://ranobedb.org/api/v0/series"
SERIES_URL = "https://ranobedb.org/series/{}"

CONCURRENT_REQUESTS = 8
TIMEOUT = aiohttp.ClientTimeout(total=30)
MAX_RETRIES = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RanobeDB ID Mapper/1.0)"
}

PATTERNS = {
    "anilist_id": re.compile(r'anilist\.co/manga/(\d+)'),
    "myanimelist_id": re.compile(r'myanimelist\.net/manga/(\d+)'),
    "anidb_id": re.compile(r'anidb\.net/anime/(\d+)'),
}


async def fetch_json(session, page):
    async with session.get(
        API,
        params={"page": page, "limit": 100},
    ) as resp:
        resp.raise_for_status()
        return await resp.json()


async def fetch_series(session, sem, series_id):
    async with sem:

        for attempt in range(MAX_RETRIES):

            try:
                async with session.get(SERIES_URL.format(series_id)) as resp:

                    if resp.status == 404:
                        return None

                    if resp.status in (429, 500, 502, 503, 504):
                        raise aiohttp.ClientError(resp.status)

                    resp.raise_for_status()

                    html = await resp.text()

                    result = {
                        "ranobedb_id": series_id,
                        "anilist_id": "",
                        "myanimelist_id": "",
                        "anidb_id": "",
                    }

                    for key, regex in PATTERNS.items():
                        m = regex.search(html)
                        if m:
                            result[key] = m.group(1)

                    return result

            except Exception:

                wait = (2 ** attempt) + random.random()

                print(f"Retry {series_id} in {wait:.1f}s")

                await asyncio.sleep(wait)

        print(f"FAILED {series_id}")
        return None


async def get_all_ids(session):
    page = 1
    ids = []

    while True:

        data = await fetch_json(session, page)

        for series in data["series"]:
            ids.append(series["id"])

        print(f"Loaded page {page}/{data['totalPages']}")

        if page >= data["totalPages"]:
            break

        page += 1

    return ids


async def main():

    connector = aiohttp.TCPConnector(limit=CONCURRENT_REQUESTS)

    sem = asyncio.Semaphore(CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=TIMEOUT,
        headers=HEADERS,
    ) as session:

        ids = await get_all_ids(session)

        print(f"{len(ids)} series found")

        filename = "ranobedb_external_ids.csv"

        file_exists = os.path.exists(filename)

        async with aiofiles.open(filename, "a", encoding="utf-8", newline="") as af:

            if not file_exists:
                await af.write(
                    "ranobedb_id,anilist_id,myanimelist_id,anidb_id\n"
                )

            tasks = [
                asyncio.create_task(fetch_series(session, sem, sid))
                for sid in ids
            ]

            completed = 0

            for task in asyncio.as_completed(tasks):

                result = await task

                completed += 1

                if result:

                    line = (
                        f"{result['ranobedb_id']},"
                        f"{result['anilist_id']},"
                        f"{result['myanimelist_id']},"
                        f"{result['anidb_id']}\n"
                    )

                    await af.write(line)

                if completed % 100 == 0:
                    print(f"{completed}/{len(ids)} completed")

    print("Finished.")


if __name__ == "__main__":
    asyncio.run(main())