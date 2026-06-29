import os
import math
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values

# ============================================================
# CONFIG
# ============================================================

# Set this in your environment rather than hardcoding it here, e.g. (PowerShell):

NEON_DATABASE_URL = "postgresql://neondb_owner:npg_m8HMX3QZNERs@ep-divine-poetry-aou08wpe-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

if not NEON_DATABASE_URL:
    raise RuntimeError(
        "NEON_DATABASE_URL is not set. Set it as an environment variable "
        "before running this script (see comment above)."
    )

EXCEL_FILE = r"C:\Users\ADMIN\Desktop\Web\Supabase pre\Book1_evaluated_penalty_18m.xlsx"
SERIES_SHEET = "Sheet1"
BOOKS_SHEET = "Licensed Books"

NEON_TABLE = "ln_series_ranking"
CONFLICT_COLS = ["series_id", "series_code"]
BATCH_SIZE = 100


# ============================================================
# LOAD EXCEL
# ============================================================
series_df = pd.read_excel(EXCEL_FILE, sheet_name=SERIES_SHEET)
books_df = pd.read_excel(EXCEL_FILE, sheet_name=BOOKS_SHEET)

# ============================================================
# NORMALIZE JOIN KEY
# ============================================================
def normalize_id(value):
    if pd.isna(value):
        return ""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value).strip()


def normalize_code(value):
    if pd.isna(value):
        return ""

    return str(value).strip()


series_df["series_key"] = (
    series_df["Series ID"].apply(normalize_id)
    + "|"
    + series_df["Series Code"].apply(normalize_code)
)

books_df["series_key"] = (
    books_df["Series ID"].apply(normalize_id)
    + "|"
    + books_df["Series Code"].apply(normalize_code)
)

# ============================================================
# GET LATEST COVER FROM LICENSED BOOKS
# ============================================================
books_df["Released At"] = pd.to_datetime(
    books_df["Released At"],
    errors="coerce",
    dayfirst=True
)

latest_covers = (
    books_df
    .dropna(subset=["Cover URL"])
    .sort_values("Released At")
    .groupby("series_key", as_index=False)
    .tail(1)[["series_key", "Cover URL", "Title"]]
    .rename(columns={
        "Cover URL": "Cover URL",
        "Title": "Cover Source Title"
    })
)

series_df = series_df.merge(
    latest_covers,
    on="series_key",
    how="left"
)

# ============================================================
# RENAME COLUMNS FOR NEON
# ============================================================
rename_map = {
    "Series Title": "series_title",
    "Series ID": "series_id",
    "Series Code": "series_code",
    "Number of Volumes": "number_of_volumes",
    "Average Price": "average_price",
    "Max Release At": "max_release_at",
    "Average View Count": "average_view_count",
    "Publisher": "publisher",
    "Original Volumes": "original_volumes",
    "Original Status": "original_status",
    "Evalution": "evalution",
    "Evaluation Basis": "evaluation_basis",
    "LN Score": "ln_score",
    "Trạng thái": "trang_thai",
    "Khả năng drop (Drop %)": "drop_percent",
    "Drop % Basis": "drop_basis",
    "Average Gap Months": "average_gap_months",
    "Months Since Last Release": "months_since_last_release",
    "Completion Ratio": "completion_ratio",
    "Publisher Activity": "publisher_activity",
    "Publisher Releases Last 24M": "publisher_releases_last_24m",
    "Score Components": "score_components",
    "Drop Components": "drop_components",
    "Cover URL": "cover_url",
    "Cover Source Title": "cover_source_title",
}

series_df = series_df.rename(columns=rename_map)

wanted_cols = list(rename_map.values())

for col in wanted_cols:
    if col not in series_df.columns:
        series_df[col] = None

series_df = series_df[wanted_cols]

# ============================================================
# DATA TYPE CLEANUP
# ============================================================
series_df["series_id"] = series_df["series_id"].apply(normalize_id)
series_df["series_code"] = series_df["series_code"].apply(normalize_code)

date_cols = [
    "max_release_at"
]

for col in date_cols:
    series_df[col] = pd.to_datetime(
        series_df[col],
        errors="coerce",
        dayfirst=True
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

numeric_cols = [
    "number_of_volumes",
    "average_price",
    "average_view_count",
    "original_volumes",
    "ln_score",
    "drop_percent",
    "average_gap_months",
    "months_since_last_release",
    "completion_ratio",
    "publisher_releases_last_24m",
]

for col in numeric_cols:
    series_df[col] = pd.to_numeric(
        series_df[col],
        errors="coerce"
    )

# ============================================================
# CLEAN INVALID VALUES
# ============================================================
series_df = series_df.replace([np.inf, -np.inf], None)
series_df = series_df.astype(object).where(pd.notnull(series_df), None)


def clean_value(value):
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        value = float(value)

        if math.isnan(value) or math.isinf(value):
            return None

        return value

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None

        return value

    if isinstance(value, str):
        value = value.strip()

        if value.lower() in ["nan", "nat", "none", "null"]:
            return None

        return value

    return value


records = [
    {
        key: clean_value(value)
        for key, value in row.items()
    }
    for row in series_df.to_dict(orient="records")
]

# ============================================================
# DEBUG CHECK BEFORE UPLOAD
# ============================================================
bad_records = []

for i, record in enumerate(records):
    for key, value in record.items():
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                bad_records.append((i, key, value))

if bad_records:
    print("Invalid values found:")
    for item in bad_records[:20]:
        print(item)

    raise ValueError("Fix invalid values before uploading.")

print(f"Prepared {len(records)} records for upload.")

# ============================================================
# UPSERT TO NEON (POSTGRES)
# ============================================================
update_cols = [c for c in wanted_cols if c not in CONFLICT_COLS]

insert_sql = (
    f"INSERT INTO {NEON_TABLE} ({', '.join(wanted_cols)}) "
    f"VALUES %s "
    f"ON CONFLICT ({', '.join(CONFLICT_COLS)}) "
    f"DO UPDATE SET {', '.join(f'{c} = EXCLUDED.{c}' for c in update_cols)}"
)

conn = psycopg2.connect(NEON_DATABASE_URL)

try:
    with conn:
        with conn.cursor() as cur:
            for i in range(0, len(records), BATCH_SIZE):
                batch = records[i:i + BATCH_SIZE]
                values = [tuple(r[c] for c in wanted_cols) for r in batch]

                execute_values(cur, insert_sql, values)

                print(f"Uploaded {i + len(batch)} / {len(records)}")
finally:
    conn.close()

print("Done.")
