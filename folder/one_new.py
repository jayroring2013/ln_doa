import re
import numpy as np
import pandas as pd

# ============================================================
# CONFIG
# ============================================================

INPUT_FILE = "Book1_author_artist_matched.xlsx"
OUTPUT_FILE = "Book1_evaluated_penalty_18m.xlsx"

TODAY = pd.Timestamp("2026-06-30")

SERIES_SHEET = "Sheet1"
BOOKS_SHEET = "Licensed Books"

OPTIONAL_SERIES_COLUMNS = {
    "Author": [
        "Author",
        "Authors",
        "Writer",
    ],
    "Illustrator": [
        "Illustrator",
        "Illustrators",
        "Artist",
        "Artists",
    ],
}

COMPLETED_STATUSES = {
    "completed",
    "complete",
    "finished",
    "ended",
    "完結",
}


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


def ensure_optional_series_columns(df):
    """
    Keep optional Sheet1 metadata columns stable through the evaluated workbook.
    If the workbook uses a close alias, copy it into the canonical column name.
    """

    for target, candidates in OPTIONAL_SERIES_COLUMNS.items():
        if target in df.columns:
            continue

        source = next(
            (col for col in candidates if col in df.columns),
            None,
        )

        if source:
            df[target] = df[source]
        else:
            df[target] = None

    return df


def volume_units(title):
    """
    Count special bundle / boxset volume units.
    Normal books count as 1.
    """

    t = str(title or "").lower()

    m = re.search(r"(trọn bộ|boxset)\s*(\d+)\s*tập", t)
    if m:
        return int(m.group(2))

    if "boxset" in t or "trọn bộ" in t:
        m = re.search(r"(\d+)\s*tập", t)
        if m:
            return int(m.group(1))

    return 1


def safe_float(v, default=None):
    try:
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def months_since(d):
    d = pd.to_datetime(
        d,
        errors="coerce",
        dayfirst=True,
    )

    if pd.isna(d):
        return 999.0

    return max(0, (TODAY - d).days / 30.4375)


def original_completed(status):
    return str(status or "").lower().strip() in COMPLETED_STATUSES


def release_status(evalution, original_status, vn_vols, jp_vols):
    jp_done = original_completed(original_status)

    caught_up_ongoing = (
        jp_vols
        and jp_vols > 0
        and vn_vols >= jp_vols
        and not jp_done
    )

    if evalution == "Completed":
        return "Hoàn thành"

    if caught_up_ongoing:
        return "Đã bắt kịp bản gốc JP"

    if evalution == "Dead":
        return "Lâu lắm rồi chưa có tập mới"

    if evalution == "Dropped":
        return "Drop"

    return "Đang phát hành"


# ============================================================
# DROP RISK
# ============================================================

def calculate_drop(row, score, evalution, months, ratio, jp_done, trang_thai):
    vn = safe_float(row.get("Number of Volumes"), 0) or 0
    jp = safe_float(row.get("Original Volumes"), None)
    avg_gap = safe_float(row.get("Average Gap Months"), None)
    recent_gap = safe_float(row.get("Recent Gap Months"), None)
    pub24 = safe_float(row.get("Publisher Releases Last 24M"), 0) or 0
    pub12 = safe_float(row.get("Publisher Releases Last 12M"), 0) or 0
    series24 = safe_float(row.get("Series Releases Last 24M"), 0) or 0
    series12 = safe_float(row.get("Series Releases Last 12M"), 0) or 0

    # Weighted effective gap: 60% recent cadence, 40% historical average
    if recent_gap is not None and avg_gap is not None:
        effective_gap = round(0.4 * avg_gap + 0.6 * recent_gap, 1)
    elif recent_gap is not None:
        effective_gap = recent_gap
    else:
        effective_gap = avg_gap

    if evalution == "Completed":
        return 0.0, "Series đã hoàn thành: 0%"

    if trang_thai == "Đã bắt kịp bản gốc JP":
        return 0.05, "VN đã bắt kịp JP: 5%"

    risk = (10 - score) * 7.5

    components = [
        f"Từ Điểm LN {score:.1f}/10: {risk:.0f}%"
    ]

    # Release recency
    if months <= 6:
        risk -= 8
        components.append("Tập mới trong 6 tháng: -8%")
    elif months <= 12:
        components.append("Trong vòng 1 năm: +0%")
    elif months <= 18:
        risk += 10
        components.append("12–18 tháng chưa có tập: +10%")
    elif months <= 21:
        risk += 16
        components.append("18–21 tháng chưa có tập: +16%")
    elif months <= 24:
        risk += 22
        components.append("21–24 tháng chưa có tập: +22%")
    elif months <= 36:
        risk += 35
        components.append("2–3 năm chưa có tập: +35%")
    else:
        risk += 45
        components.append("Hơn 3 năm chưa có tập: +45%")

    # Catch-up ratio
    if ratio is not None:
        if ratio < 0.25:
            risk += 12
            components.append("Còn rất xa JP: +12%")
        elif ratio < 0.4:
            risk += 8
            components.append("Còn xa JP: +8%")
        elif ratio >= 0.8:
            risk -= 5
            components.append("Gần bắt kịp JP: -5%")

    # One-volume risk
    if vn <= 1 and jp and jp > 1:
        risk += 10
        components.append("Mới có 1 tập VN: +10%")

    # Effective release gap (4 tiers, no silent zone)
    if effective_gap is not None:
        if effective_gap <= 6:
            risk -= 4
            components.append("Nhịp ra tập nhanh (≤6 tháng): -4%")
        elif effective_gap <= 12:
            risk -= 2
            components.append("Nhịp ra tập ổn định (6–12 tháng): -2%")
        elif effective_gap <= 18:
            risk += 6
            components.append("Nhịp ra tập chậm (12–18 tháng): +6%")
        else:
            risk += 12
            components.append("Nhịp ra tập rất chậm (>18 tháng): +12%")

    # Publisher activity (portfolio-wide 24M signal)
    if pub24 >= 5:
        risk -= 5
        components.append("Nhà phát hành còn hoạt động (24M): -5%")
    elif pub24 <= 0:
        risk += 8
        components.append("Nhà phát hành ít hoạt động (24M): +8%")

    # Publisher recent activity — stricter 12M window
    if pub12 <= 2 and pub24 >= 5:
        risk += 6
        components.append("Nhà phát hành đang chậm lại trong 12M gần nhất: +6%")

    # Series-specific release activity (direct signal for this series)
    if series24 >= 3:
        risk -= 6
        components.append("Series ra ≥3 tập trong 24M: -6%")
    elif series24 == 0 and months > 12:
        risk += 5
        components.append("Series không có tập nào trong 24M: +5%")

    # Series recent activity — stricter 12M window
    if series12 == 0 and months > 6:
        risk += 5
        components.append("Series không có tập nào trong 12M gần nhất: +5%")

    # JP completed but VN unfinished penalty only after 18 months
    if jp_done and ratio is not None and ratio < 1 and months > 18:
        risk += 5
        components.append(
            "JP đã hoàn thành nhưng VN chưa xong và quá 18 tháng: +5%"
        )

    # Evaluation band clamp (widened to preserve outlier signal)
    if evalution == "Good":
        risk = max(10, min(55, risk))
        components.append("Khung nhóm Tốt: giữ trong 10–55%")
    elif evalution == "Limping":
        risk = max(30, min(70, risk))
        components.append("Khung nhóm Cầm chừng: giữ trong 30–70%")
    elif evalution == "Dead":
        risk = max(60, min(88, risk))
        components.append("Khung nhóm Gần chết: giữ trong 60–88%")
    elif evalution == "Dropped":
        risk = max(84, min(99, risk))
        components.append("Khung nhóm Đã drop: giữ trong 84–99%")

    return round(risk / 100, 2), "\n".join(components)


# ============================================================
# LN SCORE / EVALUATION
# ============================================================

def score_series(row):
    vn = safe_float(row.get("Number of Volumes"), 0) or 0
    jp = safe_float(row.get("Original Volumes"), None)

    original_status = row.get("Original Status")
    latest = row.get("Max Release At")

    avg_gap = safe_float(row.get("Average Gap Months"), None)
    recent_gap = safe_float(row.get("Recent Gap Months"), None)
    pub24 = safe_float(row.get("Publisher Releases Last 24M"), 0) or 0
    pub12 = safe_float(row.get("Publisher Releases Last 12M"), 0) or 0
    series24 = safe_float(row.get("Series Releases Last 24M"), 0) or 0
    series12 = safe_float(row.get("Series Releases Last 12M"), 0) or 0

    months = months_since(latest)
    jp_done = original_completed(original_status)

    ratio = vn / jp if jp and jp > 0 else None
    caught_up = jp and jp > 0 and vn >= jp

    # Weighted effective gap: 60% recent cadence, 40% historical average.
    # Series that have slowed down recently are penalised faster.
    if recent_gap is not None and avg_gap is not None:
        effective_gap = round(0.4 * avg_gap + 0.6 * recent_gap, 1)
    elif recent_gap is not None:
        effective_gap = recent_gap
    else:
        effective_gap = avg_gap

    components = []

    # --------------------------------------------------------
    # Case 0: Licensed but not yet published (no VN volumes at all)
    # --------------------------------------------------------
    if vn <= 0:
        evalution = "Unreleased"
        score = np.nan
        trang_thai = "Có bản quyền nhưng chưa phát hành"
        drop = 0.50

        score_basis = "Đã có bản quyền nhưng chưa phát hành tập nào: LN Score = N/A."
        drop_basis = "Chưa phát hành tập nào: Drop % mặc định = 50%."

        return (
            evalution,
            score,
            trang_thai,
            drop,
            score_basis,
            drop_basis,
        )

    # --------------------------------------------------------
    # Case 1: VN completed and JP completed
    # Score is tiered by how recently completion occurred —
    # rewarding series that were maintained until the end.
    # --------------------------------------------------------
    if caught_up and jp_done:
        evalution = "Completed"
        trang_thai = "Hoàn thành"
        drop = 0.0

        months_since_done = months_since(latest)
        if months_since_done <= 12:
            score = 9.5
            score_basis = "VN đã hoàn thành gần đây (≤12 tháng): LN Score = 9.5."
        elif months_since_done <= 24:
            score = 9.3
            score_basis = "VN đã hoàn thành trong 1–2 năm: LN Score = 9.3."
        elif months_since_done <= 36:
            score = 9.0
            score_basis = "VN đã hoàn thành trong 2–3 năm: LN Score = 9.0."
        else:
            score = 8.7
            score_basis = "VN đã hoàn thành nhưng đã lâu (>3 năm): LN Score = 8.7."

        drop_basis = "Series đã hoàn thành tại VN: Drop % = 0%"

        return (
            evalution,
            score,
            trang_thai,
            drop,
            score_basis,
            drop_basis,
        )

    # --------------------------------------------------------
    # Case 2: VN caught up but JP still ongoing
    # --------------------------------------------------------
    if caught_up and not jp_done:
        evalution = "Good"
        score = 9.0

        components.append("Điểm nền nhóm bắt kịp JP: 9.0")

        if months <= 6:
            score += 0.2
            components.append("Tập mới gần đây: +0.2")
        elif months > 18:
            score -= 0.5
            components.append("Bắt kịp JP nhưng đã lâu chưa có tập mới: -0.5")

        score = round(max(8.0, min(9.2, score)), 1)

        trang_thai = "Đã bắt kịp bản gốc JP"
        drop = 0.05

        return (
            evalution,
            score,
            trang_thai,
            drop,
            "\n".join(components),
            "VN đã bắt kịp JP, rủi ro thấp nhưng JP vẫn đang tiếp tục.",
        )

    # --------------------------------------------------------
    # Base score from release recency
    # ≤3M and 3–6M are split so a release "just under" 6 months
    # does not receive the same base as a truly fresh release.
    # Bases are deliberately conservative: recency is a positive
    # signal but should not guarantee a high score on its own.
    # --------------------------------------------------------
    if months <= 3:
        score = 6.8
        components.append("Tập mới trong 3 tháng: 6.8")
    elif months <= 6:
        score = 6.2
        components.append("Tập mới trong 3–6 tháng: 6.2")
    elif months <= 12:
        score = 5.7
        components.append("Có tập mới trong vòng 1 năm: 5.7")
    elif months <= 18:
        score = 5.0
        components.append("1–1.5 năm chưa có tập mới: 5.0")
    elif months <= 24:
        score = 3.8
        components.append("Gần 2 năm chưa có tập mới: 3.8")
    elif months <= 36:
        score = 2.5
        components.append("2–3 năm chưa có tập mới: 2.5")
    else:
        score = 1.5
        components.append("Hơn 3 năm chưa có tập mới: 1.5")

    # --------------------------------------------------------
    # Catch-up ratio adjustment
    # The 40–49% band now carries a slight penalty to close the
    # previous neutral dead zone between 40% and 50%.
    # --------------------------------------------------------
    if ratio is not None:
        if ratio >= 0.8:
            score += 0.5
            components.append("Gần bắt kịp JP: +0.5")
        elif ratio >= 0.5:
            score += 0.2
            components.append("Đã đi được ít nhất nửa bản gốc: +0.2")
        elif ratio < 0.25:
            score -= 0.8
            components.append("Còn rất xa bản gốc: -0.8")
        elif ratio < 0.4:
            score -= 0.5
            components.append("Còn khá xa bản gốc: -0.5")
        elif ratio < 0.5:
            score -= 0.2
            components.append("Tỷ lệ bắt kịp 40–49%: -0.2")

    # --------------------------------------------------------
    # JP completed but VN unfinished penalty
    # Only applies if latest VN release is older than 18 months
    # --------------------------------------------------------
    if jp_done and ratio is not None and ratio < 1 and months > 18:
        score -= 0.5
        components.append(
            "Bản gốc đã hoàn thành nhưng VN chưa xong và đã quá 18 tháng: -0.5"
        )

    # --------------------------------------------------------
    # Effective release gap adjustment (weighted blend of recent + historical)
    # Positive bonus only applies when the series has released ≥2 volumes
    # in the last 12 months — otherwise historical pace is not indicative
    # of current momentum and should not earn credit.
    # --------------------------------------------------------
    if effective_gap is None:
        if vn <= 1:
            score -= 0.2
            components.append("Chưa đủ dữ liệu nhịp ra tập: -0.2")
    elif effective_gap <= 6:
        if series12 >= 2:
            score += 0.3
            components.append("Nhịp ra tập nhanh + series active gần đây: +0.3")
        else:
            components.append("Nhịp ra tập nhanh (lịch sử) nhưng series chưa active 12M: +0.0")
    elif effective_gap <= 12:
        if series12 >= 2:
            score += 0.1
            components.append("Nhịp ra tập bình thường + series active gần đây: +0.1")
        else:
            components.append("Nhịp ra tập bình thường (lịch sử) nhưng series chưa active 12M: +0.0")
    elif effective_gap <= 18:
        score -= 0.4
        components.append("Nhịp ra tập chậm: -0.4")
    else:
        score -= 0.8
        components.append("Nhịp ra tập rất chậm: -0.8")

    # --------------------------------------------------------
    # Publisher activity (portfolio-wide 24M signal)
    # --------------------------------------------------------
    if pub24 >= 5:
        score += 0.2
        components.append("Nhà phát hành còn hoạt động (24M): +0.2")
    elif pub24 <= 0:
        score -= 0.5
        components.append("Nhà phát hành không có release trong 24 tháng: -0.5")

    # Publisher recent activity — stricter 12M window
    # Catches publishers who were active 1–2 years ago but have slowed recently.
    if pub12 <= 2 and pub24 >= 5:
        score -= 0.4
        components.append("Nhà phát hành đang chậm lại trong 12M gần nhất: -0.4")

    # --------------------------------------------------------
    # Series-specific release activity (direct signal for this series)
    # Positive bonus gated on series12 ≥2: if the series only released
    # ≤1 volume in the last 12M its 24M count reflects past activity,
    # not current momentum, so no reward is given.
    # --------------------------------------------------------
    if series24 >= 3 and series12 >= 2:
        score += 0.3
        components.append("Series ra ≥3 tập trong 24M và active trong 12M: +0.3")
    elif series24 >= 3 and series12 <= 1:
        components.append("Series ra ≥3 tập trong 24M nhưng chậm lại trong 12M: +0.0")
    elif series24 == 0 and months > 12:
        score -= 0.2
        components.append("Series không có tập nào trong 24M: -0.2")

    # Series recent activity — stricter 12M window
    # Penalises a series that has gone quiet in the past year specifically.
    if series12 == 0 and months > 6:
        score -= 0.3
        components.append("Series không có tập nào trong 12M gần nhất: -0.3")

    # --------------------------------------------------------
    # One-volume caution
    # --------------------------------------------------------
    if vn <= 1 and jp and jp > 1 and months > 6:
        score -= 0.3
        components.append("Mới có 1 tập VN trong khi JP có nhiều tập: -0.3")

    # --------------------------------------------------------
    # Strong / Near active close-to-JP exception
    # Must be calculated BEFORE the staleness cap.
    # Strong (full bypass): ratio ≥80%, effective gap ≤6M, pub ≥5, months ≤18
    # Near  (partial floor): ratio ≥75%, effective gap ≤8M, pub ≥3, months ≤18
    # Example of strong: 86 Eighty Six
    # --------------------------------------------------------
    strong_active_close_to_jp = (
        months <= 18
        and ratio is not None
        and ratio >= 0.80
        and effective_gap is not None
        and effective_gap <= 6
        and pub24 >= 5
    )

    near_active_close_to_jp = (
        not strong_active_close_to_jp
        and months <= 18
        and ratio is not None
        and ratio >= 0.75
        and effective_gap is not None
        and effective_gap <= 8
        and pub24 >= 3
    )

    # --------------------------------------------------------
    # Staleness caps
    # Normal stale series are capped.
    # Strong active close-to-JP: bypass cap, floor at 7.1.
    # Near active close-to-JP: partial floor at 6.5.
    # --------------------------------------------------------
    if months > 36:
        score = min(score, 2.5)
        components.append("Hơn 3 năm chưa có tập mới: cap 2.5")
    elif months > 24:
        score = min(score, 3.5)
        components.append("Hơn 2 năm chưa có tập mới: cap 3.5")
    elif months > 21:
        score = min(score, 4.5)
        components.append("Gần 2 năm chưa có tập mới: cap 4.5")
    elif months > 18:
        score = min(score, 5.2)
        components.append("Hơn 1.5 năm chưa có tập mới: cap 5.2")
    elif months > 12 and strong_active_close_to_jp:
        score = max(score, 7.1)
        components.append(
            "Gần bắt kịp JP + nhịp ra nhanh + nhà phát hành active: giữ điểm tối thiểu 7.1"
        )
    elif months > 12 and near_active_close_to_jp:
        score = max(score, 6.5)
        components.append(
            "Gần bắt kịp JP + nhịp ra hợp lý (near exception): giữ điểm tối thiểu 6.5"
        )
    elif months > 12:
        score = min(score, 6.0)
        components.append("Hơn 1 năm chưa có tập mới: cap 6.0")

    score = round(max(1.0, min(10.0, score)), 1)

    # --------------------------------------------------------
    # Final Evalution classification
    # --------------------------------------------------------
    if months > 36 or score <= 2.5:
        evalution = "Dropped"

    elif months > 21 or score <= 4.5:
        evalution = "Dead"

    elif strong_active_close_to_jp:
        evalution = "Good"
        components.append(
            "Gần bắt kịp JP + nhịp ra nhanh + nhà phát hành active: giữ nhóm Good"
        )

    elif months > 12 or score <= 6.3:
        evalution = "Limping"

    else:
        evalution = "Good"

    trang_thai = release_status(
        evalution,
        original_status,
        vn,
        jp,
    )

    drop, drop_basis = calculate_drop(
        row,
        score,
        evalution,
        months,
        ratio,
        jp_done,
        trang_thai,
    )

    return (
        evalution,
        score,
        trang_thai,
        drop,
        "\n".join(components),
        drop_basis,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    # --------------------------------------------------------
    # Load workbook
    # --------------------------------------------------------
    books = pd.read_excel(
        INPUT_FILE,
        sheet_name=BOOKS_SHEET,
    )

    sheet1 = pd.read_excel(
        INPUT_FILE,
        sheet_name=SERIES_SHEET,
    )

    sheet1 = ensure_optional_series_columns(sheet1)

    # --------------------------------------------------------
    # Normalize dates and keys
    # --------------------------------------------------------
    books["Released At"] = pd.to_datetime(
        books["Released At"],
        errors="coerce",
        dayfirst=True,
    )

    books["series_key"] = (
        books["Series ID"].apply(normalize_id)
        + "|"
        + books["Series Code"].apply(normalize_code)
    )

    sheet1["series_key"] = (
        sheet1["Series ID"].apply(normalize_id)
        + "|"
        + sheet1["Series Code"].apply(normalize_code)
    )

    # --------------------------------------------------------
    # Recalculate source-of-truth metrics from Licensed Books
    # --------------------------------------------------------
    books["volume_units"] = books["Title"].apply(volume_units)

    agg = (
        books.groupby("series_key")
        .agg(
            **{
                "Number of Volumes": ("volume_units", "sum"),
                "Average Price": ("Price", "mean"),
                "Max Release At": ("Released At", "max"),
                "Average View Count": ("View Count", "mean"),
            }
        )
        .reset_index()
    )

    base = (
        sheet1.drop_duplicates("series_key")
        .merge(
            agg,
            on="series_key",
            how="left",
            suffixes=("", "_new"),
        )
    )

    # Strictly overwrite these values from Licensed Books
    for col in [
        "Number of Volumes",
        "Average Price",
        "Max Release At",
        "Average View Count",
    ]:
        new_col = f"{col}_new"

        if new_col in base.columns:
            base[col] = base[new_col]
            base.drop(columns=[new_col], inplace=True)

    # --------------------------------------------------------
    # Average release gap
    # --------------------------------------------------------
    gap_map = {}

    for key, g in books.groupby("series_key"):
        dates = sorted(
            g["Released At"]
            .dropna()
            .dt.date
            .unique()
        )

        if len(dates) >= 2:
            gaps = [
                (dates[i] - dates[i - 1]).days / 30.4375
                for i in range(1, len(dates))
            ]

            gap_map[key] = round(
                sum(gaps) / len(gaps),
                1,
            )
        else:
            gap_map[key] = np.nan

    base["Average Gap Months"] = base["series_key"].map(gap_map)

    # --------------------------------------------------------
    # Recent release gap (average of last 3 unique release dates)
    # --------------------------------------------------------
    recent_gap_map = {}

    for key, g in books.groupby("series_key"):
        dates = sorted(
            g["Released At"]
            .dropna()
            .dt.date
            .unique()
        )

        if len(dates) >= 2:
            last_dates = dates[-min(3, len(dates)):]
            recent_gaps = [
                (last_dates[i] - last_dates[i - 1]).days / 30.4375
                for i in range(1, len(last_dates))
            ]
            recent_gap_map[key] = round(
                sum(recent_gaps) / len(recent_gaps),
                1,
            )
        else:
            recent_gap_map[key] = np.nan

    base["Recent Gap Months"] = base["series_key"].map(recent_gap_map)

    base["Months Since Last Release"] = (
        base["Max Release At"]
        .apply(months_since)
    )

    # --------------------------------------------------------
    # Completion ratio
    # --------------------------------------------------------
    base["Completion Ratio"] = base.apply(
        lambda r: (
            safe_float(r.get("Number of Volumes"), 0)
            / safe_float(r.get("Original Volumes"), np.nan)
            if safe_float(r.get("Original Volumes"), 0)
            else np.nan
        ),
        axis=1,
    )

    # --------------------------------------------------------
    # Publisher activity
    # --------------------------------------------------------
    publisher_map = (
        base
        .set_index("series_key")["Publisher"]
        .to_dict()
    )

    books["Publisher"] = books["series_key"].map(publisher_map)

    cutoff24 = TODAY - pd.DateOffset(months=24)
    cutoff12 = TODAY - pd.DateOffset(months=12)

    pub24 = (
        books[books["Released At"] >= cutoff24]
        .groupby("Publisher")
        .size()
    )

    base["Publisher Releases Last 24M"] = (
        base["Publisher"]
        .map(pub24)
        .fillna(0)
        .astype(int)
    )

    # Publisher release count in the most recent 12 months (stricter recency signal)
    pub12 = (
        books[books["Released At"] >= cutoff12]
        .groupby("Publisher")
        .size()
    )

    base["Publisher Releases Last 12M"] = (
        base["Publisher"]
        .map(pub12)
        .fillna(0)
        .astype(int)
    )

    # Series-specific release count in last 24 months
    series24_count = (
        books[books["Released At"] >= cutoff24]
        .groupby("series_key")
        .size()
    )

    base["Series Releases Last 24M"] = (
        base["series_key"]
        .map(series24_count)
        .fillna(0)
        .astype(int)
    )

    # Series-specific release count in last 12 months
    series12_count = (
        books[books["Released At"] >= cutoff12]
        .groupby("series_key")
        .size()
    )

    base["Series Releases Last 12M"] = (
        base["series_key"]
        .map(series12_count)
        .fillna(0)
        .astype(int)
    )

    base["Publisher Activity"] = pd.cut(
        base["Publisher Releases Last 24M"],
        bins=[-1, 0, 4, 999],
        labels=["Inactive", "Low", "Active"],
    ).astype(str)

    # --------------------------------------------------------
    # Evaluation
    # --------------------------------------------------------
    results = base.apply(
        score_series,
        axis=1,
    )

    base["Evalution"] = [x[0] for x in results]
    base["LN Score"] = [x[1] for x in results]
    base["Trạng thái"] = [x[2] for x in results]
    base["Khả năng drop (Drop %)"] = [x[3] for x in results]
    base["Evaluation Basis"] = [x[4] for x in results]
    base["Drop % Basis"] = [x[5] for x in results]

    base["Score Components"] = base["Evaluation Basis"]
    base["Drop Components"] = base["Drop % Basis"]

    # --------------------------------------------------------
    # Penalty audit
    # --------------------------------------------------------
    penalty_audit = base[
        (
            base["Original Status"]
            .astype(str)
            .str.lower()
            .isin(COMPLETED_STATUSES)
        )
        & (base["Completion Ratio"] < 1)
    ][
        [
            "Series Title",
            "Number of Volumes",
            "Original Volumes",
            "Max Release At",
            "Months Since Last Release",
            "Completion Ratio",
            "Evalution",
            "LN Score",
            "Khả năng drop (Drop %)",
        ]
    ]

    # --------------------------------------------------------
    # Publisher activity summary
    # --------------------------------------------------------
    publisher_activity = (
        base.groupby("Publisher")
        .agg(
            Series_Count=("Series Title", "count"),
            Avg_LN_Score=("LN Score", "mean"),
            Avg_Drop_Percent=("Khả năng drop (Drop %)", "mean"),
            Releases_Last_24M=("Publisher Releases Last 24M", "max"),
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # Evaluation summary
    # --------------------------------------------------------
    eval_summary = (
        base.groupby("Evalution")
        .size()
        .reset_index(name="Count")
    )

    # --------------------------------------------------------
    # Evaluation logic notes
    # --------------------------------------------------------
    evaluation_logic = pd.DataFrame(
        [
            [
                "Source of truth",
                "Number of Volumes, Average Price, Max Release At and Average View Count are always recalculated from Licensed Books.",
            ],
            [
                "JP completed penalty",
                "Only applies when JP is completed, VN is unfinished, and latest VN release is older than 18 months.",
            ],
            [
                "Strong / Near active close-to-JP exception",
                "Strong: months <= 18, ratio >= 80%, effective gap <= 6M, pub >= 5 → score floor 7.1, Evalution Good. Near: ratio >= 75%, gap <= 8M, pub >= 3 → score floor 6.5 (partial benefit).",
            ],
            [
                "Caught up ongoing JP",
                "If VN volumes >= JP volumes but JP is Ongoing, Evalution is Good and Trạng thái is Đã bắt kịp bản gốc JP.",
            ],
            [
                "Volume count",
                "Boxset/trọn bộ titles can count as multiple volume units.",
            ],
            [
                "Licensed but unpublished",
                "If Number of Volumes is 0 (no VN volumes released yet), Evalution is Unreleased, LN Score is N/A (blank), Trạng thái is Có bản quyền nhưng chưa phát hành, and Drop % is fixed at 50%.",
            ],
            [
                "Catch-up ratio gap filled",
                "Ratio 40–49% now applies a slight penalty of -0.2 to LN Score, closing the previous neutral dead zone between 40% and 50%.",
            ],
            [
                "Effective gap (weighted blend)",
                "Release cadence is measured as: 60% recent gap (avg of last 3 release dates) + 40% historical average. Series that have slowed down recently are penalised faster.",
            ],
            [
                "Series-specific release activity",
                "Separate from publisher-wide activity. Series releasing >= 3 volumes in 24M get +0.3 score / -6% drop. Series with 0 releases and stale > 12M get -0.2 score / +5% drop.",
            ],
            [
                "Completed score tiered by recency",
                "Completed series score 9.5 (<=12M since last release), 9.3 (12–24M), 9.0 (24–36M), or 8.7 (>36M), rewarding recently finished series over ones completed long ago.",
            ],
            [
                "Widened drop % band clamps",
                "Band clamps widened to let outlier signal through: Good 10–55% (was 15–45%), Limping 30–70% (was 35–65%), Dead 60–88% (was 65–85%), Dropped 84–99% (was 86–99%).",
            ],
            [
                "Drop gap zone fix",
                "Drop risk gap buckets now cover all cadences: <=6M -4%, 6-12M -2% (new), 12-18M +6%, >18M +12%. The previously silent 6-12M zone now correctly credits stable release pacing.",
            ],
        ],
        columns=[
            "Rule",
            "Description",
        ],
    )

    # --------------------------------------------------------
    # Export
    # --------------------------------------------------------
    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl",
    ) as writer:
        base.drop(
            columns=["series_key"],
            errors="ignore",
        ).to_excel(
            writer,
            sheet_name="Sheet1",
            index=False,
        )

        books.drop(
            columns=["series_key"],
            errors="ignore",
        ).to_excel(
            writer,
            sheet_name="Licensed Books",
            index=False,
        )

        eval_summary.to_excel(
            writer,
            sheet_name="LN Score Summary",
            index=False,
        )

        publisher_activity.to_excel(
            writer,
            sheet_name="Publisher Activity",
            index=False,
        )

        penalty_audit.to_excel(
            writer,
            sheet_name="Penalty Rule Audit",
            index=False,
        )

        evaluation_logic.to_excel(
            writer,
            sheet_name="Evaluation Logic",
            index=False,
        )

    print(f"Created: {OUTPUT_FILE}")
    print(f"Series rows: {len(base)}")
    print(f"Licensed book rows: {len(books)}")


if __name__ == "__main__":
    main()
