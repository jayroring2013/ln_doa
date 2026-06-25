import os
import time
import urllib.request
import urllib.parse
import json
import re
import pandas as pd
from difflib import SequenceMatcher

# File paths
folder = r"C:\Users\tuannn2.ho\Desktop\Python Code\LN"
nu_match_path = os.path.join(folder, "NU_Match.xlsx")
ranobe_path = os.path.join(folder, "ranobedb_flat.xlsx")

# 1. Load data
print("Loading data...")
match_df = pd.read_excel(nu_match_path, sheet_name='Match')
mal_df = pd.read_excel(nu_match_path, sheet_name='MAL')
ranobe_df = pd.read_excel(ranobe_path, sheet_name='Sheet1')

# Ensure ID columns are treated properly (numeric or float for NaNs)
match_df['MAL ID'] = pd.to_numeric(match_df['MAL ID'], errors='coerce')
match_df['Ranobe ID'] = pd.to_numeric(match_df['Ranobe ID'], errors='coerce')
mal_df['MAL_ID'] = pd.to_numeric(mal_df['MAL_ID'], errors='coerce')
ranobe_df['series_id'] = pd.to_numeric(ranobe_df['series_id'], errors='coerce')

# Keep track of initial non-null counts
initial_mal_count = match_df['MAL ID'].notna().sum()
initial_ranobe_count = match_df['Ranobe ID'].notna().sum()

print(f"Initial Match sheet stats: {len(match_df)} rows. Populated MAL IDs: {initial_mal_count}, Populated Ranobe IDs: {initial_ranobe_count}")

# Name normalization
def normalize_name(name):
    if not isinstance(name, str):
        return ""
    name = name.lower().replace(",", " ").replace("'", "").replace(".", "")
    # Remove common honorifics or annotations if any
    tokens = [t.strip() for t in name.split() if t.strip()]
    return "".join(sorted(tokens))

# Title normalization
def normalize_title(title):
    if not isinstance(title, str):
        return ""
    title = title.lower()
    title = re.sub(r'[^a-z0-9]', '', title)
    return title

# Title similarity
def title_similarity(t1, t2):
    t1_norm = normalize_title(t1)
    t2_norm = normalize_title(t2)
    if not t1_norm or not t2_norm:
        return 0.0
    if t1_norm == t2_norm:
        return 1.0
    return SequenceMatcher(None, t1_norm, t2_norm).ratio()

# Fuzzy contributor match
def fuzzy_name_match(name1, name2):
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    return SequenceMatcher(None, n1, n2).ratio() > 0.85

# Google Translate function
def translate_title(text, sl='vi', tl='en'):
    if not text or not isinstance(text, str):
        return ""
    # Avoid translating numeric titles or very short ones
    if text.isdigit():
        return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q=" + urllib.parse.quote(text)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            result = "".join([part[0] for part in data[0] if part[0]])
            return result.strip()
    except Exception as e:
        print(f"Translation error for '{text}' ({sl}->{tl}): {e}")
        return ""

# Match score between Ranobe row and MAL row
def get_best_title_similarity(ranobe_row, mal_row):
    titles_ranobe = [
        ranobe_row.get('title'),
        ranobe_row.get('romaji'),
        ranobe_row.get('romaji_orig'),
        ranobe_row.get('title_orig')
    ]
    titles_mal = [
        mal_row.get('title')
    ]
    
    max_sim = 0.0
    for r_t in titles_ranobe:
        if not r_t or not isinstance(r_t, str):
            continue
        for m_t in titles_mal:
            if not m_t or not isinstance(m_t, str):
                continue
            sim = title_similarity(r_t, m_t)
            if sim > max_sim:
                max_sim = sim
    return max_sim

def compute_match_score(ranobe_row, mal_row):
    title_sim = get_best_title_similarity(ranobe_row, mal_row)
    
    r_auth = ranobe_row.get('author', '')
    r_art = ranobe_row.get('artist', '')
    m_auth = mal_row.get('contributor_1', '')
    m_art = mal_row.get('contributor_2', '')
    
    auth_ok = fuzzy_name_match(r_auth, m_auth) or fuzzy_name_match(r_auth, m_art)
    art_ok = fuzzy_name_match(r_art, m_art) or fuzzy_name_match(r_art, m_auth) if r_art else True
    
    contributor_score = 0.0
    if auth_ok and art_ok:
        contributor_score = 1.0
    elif auth_ok or art_ok:
        contributor_score = 0.5
        
    total_score = 0.6 * title_sim + 0.4 * contributor_score
    return total_score

# Indexing MAL reference data
print("Indexing MAL reference dataset...")
mal_by_author = {}
mal_by_title = {}
mal_by_prefix = {}
mal_by_id = {}

for idx, row in mal_df.iterrows():
    m_id = row['MAL_ID']
    auth1 = normalize_name(row.get('contributor_1'))
    auth2 = normalize_name(row.get('contributor_2'))
    title_norm = normalize_title(row.get('title'))
    
    mal_record = {
        'MAL_ID': m_id,
        'title': row['title'],
        'contributor_1': row.get('contributor_1'),
        'contributor_2': row.get('contributor_2'),
        'genres': row.get('genres'),
        'score': row.get('score'),
        'popularity': row.get('popularity'),
        'members': row.get('members'),
        'favorites': row.get('favorites')
    }
    
    mal_by_id[m_id] = mal_record
    
    if auth1:
        mal_by_author.setdefault(auth1, []).append(mal_record)
    if auth2:
        mal_by_author.setdefault(auth2, []).append(mal_record)
    if title_norm:
        mal_by_title.setdefault(title_norm, []).append(mal_record)
        if len(title_norm) >= 6:
            prefix = title_norm[:6]
            mal_by_prefix.setdefault(prefix, []).append(mal_record)

# Indexing Ranobe reference data
print("Indexing Ranobe reference dataset...")
ranobe_by_author = {}
ranobe_by_title = {}
ranobe_by_prefix = {}
ranobe_by_id = {}

for idx, row in ranobe_df.iterrows():
    r_id = row['series_id']
    auth = normalize_name(row.get('author'))
    title_norm = normalize_title(row.get('title'))
    romaji_norm = normalize_title(row.get('romaji'))
    romaji_orig_norm = normalize_title(row.get('romaji_orig'))
    
    ranobe_record = row.to_dict()
    ranobe_by_id[r_id] = ranobe_record
    
    if auth:
        ranobe_by_author.setdefault(auth, []).append(ranobe_record)
    for t_n in [title_norm, romaji_norm, romaji_orig_norm]:
        if t_n:
            ranobe_by_title.setdefault(t_n, []).append(ranobe_record)
            if len(t_n) >= 6:
                prefix = t_n[:6]
                ranobe_by_prefix.setdefault(prefix, []).append(ranobe_record)

# -----------------------------
# Part 1: Match Ranobe with MAL
# -----------------------------
print("Matching Ranobe records to MAL...")
ranobe_to_mal_map = {} # ranobe_series_id -> (mal_id, mal_title, score)
mal_to_ranobe_map = {} # mal_id -> (ranobe_series_id, score)

ranobe_mal_ids = []
ranobe_mal_titles = []
ranobe_match_scores = []

for idx, row in ranobe_df.iterrows():
    r_id = row['series_id']
    r_auth = row.get('author')
    r_title = row.get('title')
    r_romaji = row.get('romaji')
    r_romaji_orig = row.get('romaji_orig')
    
    candidates = []
    # 1. Author lookup
    auth_norm = normalize_name(r_auth)
    if auth_norm and auth_norm in mal_by_author:
        candidates.extend(mal_by_author[auth_norm])
        
    # 2. Title lookups
    for t in [r_title, r_romaji, r_romaji_orig]:
        t_norm = normalize_title(t)
        if t_norm:
            if t_norm in mal_by_title:
                candidates.extend(mal_by_title[t_norm])
            if len(t_norm) >= 6:
                prefix = t_norm[:6]
                if prefix in mal_by_prefix:
                    candidates.extend(mal_by_prefix[prefix])
                    
    # Deduplicate candidates
    seen_ids = set()
    unique_candidates = []
    for cand in candidates:
        if cand['MAL_ID'] not in seen_ids:
            seen_ids.add(cand['MAL_ID'])
            unique_candidates.append(cand)
            
    # Find best candidate
    best_cand = None
    best_score = 0.0
    for cand in unique_candidates:
        score = compute_match_score(row, cand)
        if score > best_score:
            best_score = score
            best_cand = cand
            
    if best_cand and best_score >= 0.70:
        mal_id = int(best_cand['MAL_ID'])
        ranobe_to_mal_map[r_id] = (mal_id, best_cand['title'], best_score)
        # Update reverse map if this match is stronger than previous
        if mal_id not in mal_to_ranobe_map or best_score > mal_to_ranobe_map[mal_id][1]:
            mal_to_ranobe_map[mal_id] = (r_id, best_score)
            
        ranobe_mal_ids.append(mal_id)
        ranobe_mal_titles.append(best_cand['title'])
        ranobe_match_scores.append(round(best_score, 3))
    else:
        ranobe_mal_ids.append(pd.NA)
        ranobe_mal_titles.append(pd.NA)
        ranobe_match_scores.append(pd.NA)

# Create the final Ranobe matching MAL sheet
ranobe_matched_df = ranobe_df.copy()
ranobe_matched_df['MAL ID'] = ranobe_mal_ids
ranobe_matched_df['MAL Title'] = ranobe_mal_titles
ranobe_matched_df['Match Score'] = ranobe_match_scores

print(f"Matched {len(ranobe_to_mal_map)} / {len(ranobe_df)} Ranobe series with MAL IDs.")

# -----------------------------
# Part 2: Match Match sheet rows
# -----------------------------
print("\nTranslating Vietnamese titles and matching Match sheet...")

# First, collect translations to speed up and avoid rate limiting
vi_titles = match_df['Title'].dropna().unique()
en_translations = {}
ja_translations = {}

for idx, vi_title in enumerate(vi_titles):
    print(f"Translating {idx+1}/{len(vi_titles)}: '{vi_title}'")
    en_t = translate_title(vi_title, sl='vi', tl='en')
    ja_t = translate_title(vi_title, sl='vi', tl='ja')
    en_translations[vi_title] = en_t
    ja_translations[vi_title] = ja_t
    time.sleep(0.15) # Wait to prevent IP blocking

def compute_match_score_vietnamese(match_row, mal_row, en_trans, ja_trans):
    r_auth = match_row.get('Author', '')
    r_art = match_row.get('Artist', '')
    m_auth = mal_row.get('contributor_1', '')
    m_art = mal_row.get('contributor_2', '')
    
    auth_ok = fuzzy_name_match(r_auth, m_auth) or fuzzy_name_match(r_auth, m_art)
    art_ok = fuzzy_name_match(r_art, m_art) or fuzzy_name_match(r_art, m_auth) if r_art else True
    
    contributor_score = 0.0
    if auth_ok and art_ok:
        contributor_score = 1.0
    elif auth_ok or art_ok:
        contributor_score = 0.5
        
    titles_match = [
        match_row.get('Title'),
        match_row.get('Romaji'),
        en_trans,
        ja_trans
    ]
    titles_mal = [
        mal_row.get('title')
    ]
    
    max_title_sim = 0.0
    for mt in titles_match:
        if not mt or not isinstance(mt, str):
            continue
        for m_t in titles_mal:
            if not m_t or not isinstance(m_t, str):
                continue
            sim = title_similarity(mt, m_t)
            if sim > max_title_sim:
                max_title_sim = sim
                
    total_score = 0.6 * max_title_sim + 0.4 * contributor_score
    return total_score

def compute_match_score_ranobe_vietnamese(match_row, ranobe_row, en_trans, ja_trans):
    r_auth = match_row.get('Author', '')
    r_art = match_row.get('Artist', '')
    ran_auth = ranobe_row.get('author', '')
    ran_art = ranobe_row.get('artist', '')
    
    auth_ok = fuzzy_name_match(r_auth, ran_auth) or fuzzy_name_match(r_auth, ran_art)
    art_ok = fuzzy_name_match(r_art, ran_art) or fuzzy_name_match(r_art, ran_auth) if r_art else True
    
    contributor_score = 0.0
    if auth_ok and art_ok:
        contributor_score = 1.0
    elif auth_ok or art_ok:
        contributor_score = 0.5
        
    titles_match = [
        match_row.get('Title'),
        match_row.get('Romaji'),
        en_trans,
        ja_trans
    ]
    titles_ran = [
        ranobe_row.get('title'),
        ranobe_row.get('romaji'),
        ranobe_row.get('romaji_orig'),
        ranobe_row.get('title_orig')
    ]
    
    max_title_sim = 0.0
    for mt in titles_match:
        if not mt or not isinstance(mt, str):
            continue
        for r_t in titles_ran:
            if not r_t or not isinstance(r_t, str):
                continue
            sim = title_similarity(mt, r_t)
            if sim > max_title_sim:
                max_title_sim = sim
                
    v_match = match_row.get('Original Volumes')
    v_ran = ranobe_row.get('num_books')
    volume_score = 0.0
    if v_match is not None and v_ran is not None:
        try:
            v_match_int = int(v_match)
            v_ran_int = int(v_ran)
            if v_match_int == v_ran_int:
                volume_score = 1.0
            elif abs(v_match_int - v_ran_int) <= 1:
                volume_score = 0.5
        except:
            pass
            
    total_score = 0.55 * max_title_sim + 0.35 * contributor_score + 0.1 * volume_score
    return total_score

# Match loops
new_mal_ids = []
new_ranobe_ids = []

for idx, row in match_df.iterrows():
    title = row['Title']
    romaji = row.get('Romaji')
    curr_mal_id = row['MAL ID']
    curr_ranobe_id = row['Ranobe ID']
    
    en_t = en_translations.get(title, "")
    ja_t = ja_translations.get(title, "")
    
    # Anchor values
    mal_id = curr_mal_id if pd.notna(curr_mal_id) else None
    ranobe_id = curr_ranobe_id if pd.notna(curr_ranobe_id) else None
    
    # Step A: Cross-referencing existing anchors
    if mal_id is not None and ranobe_id is None:
        # Check reverse map
        if mal_id in mal_to_ranobe_map:
            ranobe_id = mal_to_ranobe_map[mal_id][0]
            print(f"[{title}] Mapped Ranobe ID {ranobe_id} from existing MAL ID {mal_id} via cross-ref")
            
    if ranobe_id is not None and mal_id is None:
        # Check direct map
        if ranobe_id in ranobe_to_mal_map:
            mal_id = ranobe_to_mal_map[ranobe_id][0]
            print(f"[{title}] Mapped MAL ID {mal_id} from existing Ranobe ID {ranobe_id} via cross-ref")

    # Step B: Match missing MAL ID
    if mal_id is None:
        candidates = []
        auth_norm = normalize_name(row.get('Author'))
        if auth_norm and auth_norm in mal_by_author:
            candidates.extend(mal_by_author[auth_norm])
            
        for t in [title, romaji, en_t, ja_t]:
            t_norm = normalize_title(t)
            if t_norm:
                if t_norm in mal_by_title:
                    candidates.extend(mal_by_title[t_norm])
                if len(t_norm) >= 6:
                    prefix = t_norm[:6]
                    if prefix in mal_by_prefix:
                        candidates.extend(mal_by_prefix[prefix])
                        
        seen_cands = set()
        unique_cands = []
        for c in candidates:
            if c['MAL_ID'] not in seen_cands:
                seen_cands.add(c['MAL_ID'])
                unique_cands.append(c)
                
        best_cand = None
        best_score = 0.0
        for cand in unique_cands:
            score = compute_match_score_vietnamese(row, cand, en_t, ja_t)
            if score > best_score:
                best_score = score
                best_cand = cand
                
        if best_cand and best_score >= 0.65:
            mal_id = int(best_cand['MAL_ID'])
            print(f"[{title}] Matched MAL ID -> {mal_id} ({best_cand['title']}), Score: {best_score:.3f}")
            # Try to get Ranobe ID from this newly matched MAL ID
            if ranobe_id is None and mal_id in mal_to_ranobe_map:
                ranobe_id = mal_to_ranobe_map[mal_id][0]
                print(f"  └─ Mapped Ranobe ID {ranobe_id} via cross-ref of new MAL ID")

    # Step C: Match missing Ranobe ID
    if ranobe_id is None:
        candidates = []
        auth_norm = normalize_name(row.get('Author'))
        if auth_norm and auth_norm in ranobe_by_author:
            candidates.extend(ranobe_by_author[auth_norm])
            
        for t in [title, romaji, en_t, ja_t]:
            t_norm = normalize_title(t)
            if t_norm:
                if t_norm in ranobe_by_title:
                    candidates.extend(ranobe_by_title[t_norm])
                if len(t_norm) >= 6:
                    prefix = t_norm[:6]
                    if prefix in ranobe_by_prefix:
                        candidates.extend(ranobe_by_prefix[prefix])
                        
        seen_cands = set()
        unique_cands = []
        for c in candidates:
            if c['series_id'] not in seen_cands:
                seen_cands.add(c['series_id'])
                unique_cands.append(c)
                
        best_cand = None
        best_score = 0.0
        for cand in unique_cands:
            score = compute_match_score_ranobe_vietnamese(row, cand, en_t, ja_t)
            if score > best_score:
                best_score = score
                best_cand = cand
                
        if best_cand and best_score >= 0.65:
            ranobe_id = int(best_cand['series_id'])
            print(f"[{title}] Matched Ranobe ID -> {ranobe_id} ({best_cand['title']}), Score: {best_score:.3f}")
            # Try to get MAL ID from this newly matched Ranobe ID
            if mal_id is None and ranobe_id in ranobe_to_mal_map:
                mal_id = ranobe_to_mal_map[ranobe_id][0]
                print(f"  └─ Mapped MAL ID {mal_id} via cross-ref of new Ranobe ID")

    new_mal_ids.append(mal_id if mal_id is not None else pd.NA)
    new_ranobe_ids.append(ranobe_id if ranobe_id is not None else pd.NA)

# Assign back to sheet Match (preserving other columns and format)
updated_match_df = match_df.copy()
# We only overwrite if original was null, per "dont modify existing MAL ID and Ranobe ID value"
updated_match_df['MAL ID'] = match_df['MAL ID'].fillna(pd.Series(new_mal_ids))
updated_match_df['Ranobe ID'] = match_df['Ranobe ID'].fillna(pd.Series(new_ranobe_ids))

# Final Stats
final_mal_count = updated_match_df['MAL ID'].notna().sum()
final_ranobe_count = updated_match_df['Ranobe ID'].notna().sum()

print("\n" + "="*40)
print("MATCHING SUMMARY")
print(f"MAL ID: {initial_mal_count} -> {final_mal_count} (New: {final_mal_count - initial_mal_count})")
print(f"Ranobe ID: {initial_ranobe_count} -> {final_ranobe_count} (New: {final_ranobe_count - initial_ranobe_count})")
print("="*40)

# Write to excel writer
print("Saving updated Excel file...")
with pd.ExcelWriter(nu_match_path, mode='w', engine='openpyxl') as writer:
    updated_match_df.to_excel(writer, sheet_name='Match', index=False)
    mal_df.to_excel(writer, sheet_name='MAL', index=False)
    ranobe_matched_df.to_excel(writer, sheet_name='Ranobe', index=False)

print("Done! Excel file updated successfully.")
