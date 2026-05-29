import pandas as pd
import math
import numpy as np
import httpx
from supabase import create_client, ClientOptions
from postgrest import SyncPostgrestClient

SUPABASE_URL = "https://zragvkqsslfyarjbjmmz.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpyYWd2a3Fzc2xmeWFyamJqbW16Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjYzMzY4NCwiZXhwIjoyMDg4MjA5Njg0fQ.V2VYm1pzKLbylTkHS4nTX8T6dMqpRdENpMWLydC_jmE"

EXCEL_FILE = r"C:\Users\tuannn2.ho\Desktop\Python Code\Book1_evaluated_penalty_18m.xlsx"
SERIES_SHEET = "Sheet1"
BOOKS_SHEET = "Licensed Books"

SUPABASE_TABLE = "ln_series_ranking"
BATCH_SIZE = 100


# Disable SSL verification
http_client = httpx.Client(verify=False)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    options=ClientOptions(
        postgrest_client_timeout=60
    ),
)

# Inject custom HTTP client
supabase.postgrest.session = http_client
# ============================================================


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
# RENAME COLUMNS FOR SUPABASE
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
# CLEAN INVALID JSON VALUES
# ============================================================
series_df = series_df.replace([np.inf, -np.inf], None)
series_df = series_df.astype(object).where(pd.notnull(series_df), None)


def clean_json_value(value):
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
        key: clean_json_value(value)
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
    print("Invalid JSON values found:")
    for item in bad_records[:20]:
        print(item)

    raise ValueError("Fix invalid JSON values before uploading.")

print(f"Prepared {len(records)} records for upload.")

# ============================================================
# UPSERT TO SUPABASE
# ============================================================
for i in range(0, len(records), BATCH_SIZE):
    batch = records[i:i + BATCH_SIZE]

    response = (
        supabase
        .table(SUPABASE_TABLE)
        .upsert(
            batch,
            on_conflict="series_id,series_code"
        )
        .execute()
    )

    print(f"Uploaded {i + len(batch)} / {len(records)}")

print("Done.")