import re
import pandas as pd

INPUT_FILE = "Book1_evaluated_penalty_18m.xlsx"
OUTPUT_FILE = "series_table_import_v5.xlsx"

# ============================================================
# HELPERS
# ============================================================

def normalize_id(v):
    if pd.isna(v):
        return ""

    if isinstance(v, float) and v.is_integer():
        return str(int(v))

    return str(v).strip()


def normalize_code(v):
    if pd.isna(v):
        return ""

    return str(v).strip()


def slugify(text):
    text = str(text or "").lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


def clean_description(text):
    if pd.isna(text):
        return None

    text = str(text).strip()

    if text == "":
        return None

    text = text.replace("\r", "\n")

    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")

    return text


def clean_text(text):
    if pd.isna(text):
        return None

    text = str(text).strip()
    return text or None


def first_text(row, columns):
    for col in columns:
        if col in row.index:
            value = clean_text(row.get(col))
            if value:
                return value

    return None


STATUS_MAP = {
    "Đang phát hành": "ongoing",
    "Hoàn thành": "completed",
    "Drop": "dropped",
    "Lâu lắm rồi chưa có tập mới": "stalled",
    "Đã bắt kịp bản gốc JP": "caught_up",
}


def is_special(title):
    t = str(title or "").lower()

    return any(
        keyword in t
        for keyword in [
            "boxset",
            "trọn bộ",
            "omnibus",
            "special",
            "collector",
        ]
    )


# ============================================================
# MAIN
# ============================================================

def main():
    sheet1 = pd.read_excel(
        INPUT_FILE,
        sheet_name="Sheet1",
    )

    books = pd.read_excel(
        INPUT_FILE,
        sheet_name="Licensed Books",
    )

    # --------------------------------------------------------
    # Create stable series key
    # --------------------------------------------------------
    sheet1["series_key"] = (
        sheet1["Series ID"].apply(normalize_id)
        + "|"
        + sheet1["Series Code"].apply(normalize_code)
    )

    books["series_key"] = (
        books["Series ID"].apply(normalize_id)
        + "|"
        + books["Series Code"].apply(normalize_code)
    )

    # --------------------------------------------------------
    # Parse dates
    # --------------------------------------------------------
    books["Released At"] = pd.to_datetime(
        books["Released At"],
        errors="coerce",
        dayfirst=True,
    )

    # --------------------------------------------------------
    # Latest cover per series
    # --------------------------------------------------------
    latest_covers = (
        books
        .dropna(subset=["Cover URL"])
        .sort_values(["series_key", "Released At", "ID"])
        .groupby("series_key")
        .tail(1)[["series_key", "Cover URL"]]
    )

    # --------------------------------------------------------
    # First volume summary per series
    # Based ONLY on release date ordering
    # --------------------------------------------------------
    first_volume_summary = (
        books
        .sort_values(
            ["series_key", "Released At", "ID"],
            na_position="last",
        )
        .groupby("series_key")
        .first()[["Summary"]]
        .reset_index()
        .rename(
            columns={
                "Summary": "series_description"
            }
        )
    )

    # --------------------------------------------------------
    # Build series source
    # --------------------------------------------------------
    series_src = (
        sheet1
        .merge(
            latest_covers,
            on="series_key",
            how="left",
        )
        .merge(
            first_volume_summary,
            on="series_key",
            how="left",
        )
    )

    # --------------------------------------------------------
    # Build public.series sheet
    # --------------------------------------------------------
    series_rows = []
    series_id_map = {}

    for idx, row in series_src.iterrows():
        generated_id = idx + 1
        series_key = row["series_key"]

        series_id_map[series_key] = generated_id

        title = row.get("Series Title")
        description = clean_description(
            row.get("series_description")
        )
        author = first_text(
            row,
            [
                "Author",
                "Authors",
                "Writer",
            ],
        )
        illustrator = first_text(
            row,
            [
                "Illustrator",
                "Illustrators",
                "Artist",
                "Artists",
            ],
        )

        series_rows.append(
            {
                "id": generated_id,
                "item_type": "novel",
                "title": title,
                "title_vi": title,
                "title_native": None,
                "title_english": None,
                "slug": slugify(title),
                "cover_url": row.get("Cover URL"),
                "banner_url": None,
                "description": description,
                "description_vi": description,
                "status": STATUS_MAP.get(
                    row.get("Trạng thái"),
                    "unknown",
                ),
                "genres": "{}",
                "tags": "{}",
                "source": "LIGHT_NOVEL",
                "author": author,
                "artist": illustrator,
                "studio": None,
                "publisher_id": None,
                "anilist_id": None,
                "mangadex_id": None,
                "mal_id": None,
                "created_at": pd.Timestamp.now(),
                "updated_at": pd.Timestamp.now(),
            }
        )

    series_df = pd.DataFrame(series_rows)

    # --------------------------------------------------------
    # Build public.volumes sheet
    # volume_number is based ONLY on release date ordering
    # --------------------------------------------------------
    volume_rows = []

    books_sorted = books.sort_values(
        ["series_key", "Released At", "ID"],
        na_position="last",
    )

    for series_key, group in books_sorted.groupby("series_key"):
        group = group.sort_values(
            ["Released At", "ID"],
            na_position="last",
        )

        generated_series_id = series_id_map.get(series_key)

        if generated_series_id is None:
            continue

        for order, (_, row) in enumerate(
            group.iterrows(),
            start=1,
        ):
            released_at = row.get("Released At")

            if pd.notna(released_at):
                release_date = released_at.date()
            else:
                release_date = None

            volume_rows.append(
                {
                    "id": len(volume_rows) + 1,
                    "series_id": generated_series_id,
                    "publisher_id": None,
                    "volume_number": order,
                    "title": row.get("Title"),
                    "isbn": row.get("ISBN"),
                    "cover_url": row.get("Cover URL"),
                    "release_date": release_date,
                    "price": row.get("Price"),
                    "currency": "VND",
                    "is_special": is_special(
                        row.get("Title")
                    ),
                    "is_digital": False,
                    "created_at": pd.Timestamp.now(),
                    "page_count": row.get("Pages"),
                    "translator": row.get("Translator"),
                }
            )

    volumes_df = pd.DataFrame(volume_rows)

    # --------------------------------------------------------
    # Mapping notes
    # --------------------------------------------------------
    notes = pd.DataFrame(
        [
            [
                "series.description",
                "Mapped from Summary of the first volume by release_date order within each series.",
            ],
            [
                "series.description_vi",
                "Same as series.description.",
            ],
            [
                "series.status",
                "Mapped from Sheet1 Trạng thái to English enum.",
            ],
            [
                "series.item_type",
                "Always novel.",
            ],
            [
                "series.source",
                "Always LIGHT_NOVEL.",
            ],
            [
                "series.author",
                "Mapped from Sheet1 Author column when present.",
            ],
            [
                "series.artist",
                "Mapped from Sheet1 Illustrator column when present. Artist/Artists are accepted as fallback aliases.",
            ],
            [
                "volumes.volume_number",
                "Assigned by release_date order within each series only. Book title is not used.",
            ],
            [
                "volumes.currency",
                "Always VND.",
            ],
            [
                "volumes.is_digital",
                "Always false.",
            ],
            [
                "volumes.is_special",
                "Detected from title keywords: boxset, trọn bộ, omnibus, special, collector.",
            ],
        ],
        columns=[
            "field",
            "mapping_note",
        ],
    )

    # --------------------------------------------------------
    # Export
    # --------------------------------------------------------
    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl",
    ) as writer:
        series_df.to_excel(
            writer,
            sheet_name="series",
            index=False,
        )

        volumes_df.to_excel(
            writer,
            sheet_name="volumes",
            index=False,
        )

        notes.to_excel(
            writer,
            sheet_name="mapping_notes",
            index=False,
        )

    print(f"Created: {OUTPUT_FILE}")
    print(f"Series rows: {len(series_df)}")
    print(f"Volume rows: {len(volumes_df)}")


if __name__ == "__main__":
    main()
