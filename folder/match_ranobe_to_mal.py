import os
import sys
import re
import pandas as pd
from collections import Counter
from difflib import SequenceMatcher

# Setup paths
folder = r"C:\Users\tuannn2.ho\Desktop\Python Code\LN"
ranobe_path = os.path.join(folder, "Ranobe.xlsx")
mal_path = os.path.join(folder, "MAL.xlsx")
output_path = os.path.join(folder, "Ranobe_Mapped.xlsx")

# Helper functions for normalization
def normalize_title(title):
    if not title or pd.isna(title) or not isinstance(title, str):
        return ""
    title = title.lower()
    title = re.sub(r'[^a-z0-9]', '', title)
    return title

def normalize_name(name):
    if not name or pd.isna(name) or not isinstance(name, str):
        return ""
    name = name.lower().replace(",", " ").replace("'", "").replace(".", "")
    tokens = [t.strip() for t in name.split() if t.strip()]
    return "".join(sorted(tokens))

def extract_year(date_str):
    if not date_str or pd.isna(date_str):
        return None
    match = re.search(r'\b(19\d{2}|20\d{2})\b', str(date_str))
    return int(match.group(1)) if match else None

# Similarity helper functions
def get_best_title_similarity_fast(r_norm_titles, m_norm_titles):
    max_sim = 0.0
    for r_t in r_norm_titles:
        len_r = len(r_t)
        if len_r == 0:
            continue
        for m_t in m_norm_titles:
            len_m = len(m_t)
            if len_m == 0:
                continue
            if r_t == m_t:
                return 1.0
            # Length filter heuristic: if one is > 2.5x longer than the other, skip SequenceMatcher
            if len_r / len_m > 2.5 or len_m / len_r > 2.5:
                continue
            sim = SequenceMatcher(None, r_t, m_t).ratio()
            if sim > max_sim:
                max_sim = sim
    return max_sim

def get_volume_score(r_vol, m_vol):
    if pd.isna(r_vol) or pd.isna(m_vol):
        return 1.0  # No penalty if volume info is missing
    try:
        r_vol = int(r_vol)
        m_vol = int(m_vol)
        if r_vol == m_vol:
            return 1.0
        elif abs(r_vol - m_vol) <= 1:
            return 0.8
        elif abs(r_vol - m_vol) <= 3:
            return 0.5
        else:
            return 0.1
    except:
        return 1.0

def get_contributor_score_fast(r_auth_norm, r_art_norm, m_auth_norm, m_art_norm):
    auth_match = False
    if r_auth_norm and m_auth_norm:
        if r_auth_norm == m_auth_norm or (abs(len(r_auth_norm) - len(m_auth_norm)) <= 3 and SequenceMatcher(None, r_auth_norm, m_auth_norm).ratio() > 0.85):
            auth_match = True
        elif r_auth_norm == m_art_norm or (abs(len(r_auth_norm) - len(m_art_norm)) <= 3 and SequenceMatcher(None, r_auth_norm, m_art_norm).ratio() > 0.85):
            auth_match = True
            
    art_match = False
    if r_art_norm:
        if m_art_norm:
            if r_art_norm == m_art_norm or (abs(len(r_art_norm) - len(m_art_norm)) <= 3 and SequenceMatcher(None, r_art_norm, m_art_norm).ratio() > 0.85):
                art_match = True
            elif r_art_norm == m_auth_norm or (abs(len(r_art_norm) - len(m_auth_norm)) <= 3 and SequenceMatcher(None, r_art_norm, m_auth_norm).ratio() > 0.85):
                art_match = True
        else:
            art_match = True  # Don't penalize missing artist on MAL
    else:
        art_match = True
        
    if auth_match and art_match:
        return 1.0
    elif auth_match or art_match:
        return 0.6
    else:
        if r_auth_norm and m_auth_norm:
            return 0.0
        return 0.5

# Match Score Combiner
def compute_match_score_fast(r_rec, m_rec):
    title_sim = get_best_title_similarity_fast(r_rec['normalized_titles'], m_rec['normalized_titles'])
    contributor_score = get_contributor_score_fast(
        r_rec['author_norm'], r_rec['artist_norm'],
        m_rec['contributor_1_norm'], m_rec['contributor_2_norm']
    )
    
    # Combined base score
    base_score = 0.6 * title_sim + 0.4 * contributor_score
    
    # Date mismatch penalty
    if r_rec['year'] is not None and m_rec['year'] is not None:
        year_diff = abs(r_rec['year'] - m_rec['year'])
        if year_diff > 2:
            base_score -= 0.3
        elif year_diff > 1:
            base_score -= 0.15
            
    # Volume count mismatch penalty
    vol_score = get_volume_score(r_rec['num_books'], m_rec['Volumes'])
    if vol_score < 1.0:
        base_score -= (1.0 - vol_score) * 0.2
        
    return max(0.0, base_score)

def main():
    print("Loading datasets...")
    if not os.path.exists(ranobe_path) or not os.path.exists(mal_path):
        print("Error: Excel files missing.")
        sys.exit(1)
        
    df_ranobe = pd.read_excel(ranobe_path, sheet_name="Sheet1")
    df_mal = pd.read_excel(mal_path, sheet_name="Sheet1")
    
    print(f"Loaded Ranobe: {df_ranobe.shape[0]} rows.")
    print(f"Loaded MAL: {df_mal.shape[0]} rows.")
    
    # Enforce numeric types
    df_ranobe['series_id'] = pd.to_numeric(df_ranobe['series_id'], errors='coerce')
    df_mal['MAL_ID'] = pd.to_numeric(df_mal['MAL_ID'], errors='coerce')
    
    # Detect pre-existing mapping column (if any)
    existing_mappings = {}
    mal_id_col = None
    for col in df_ranobe.columns:
        if col.lower().replace("_", "").replace(" ", "") == "malid":
            mal_id_col = col
            break
            
    if mal_id_col:
        print(f"Found pre-existing mapping column: '{mal_id_col}'")
        df_ranobe[mal_id_col] = pd.to_numeric(df_ranobe[mal_id_col], errors='coerce')
        for idx, row in df_ranobe.iterrows():
            r_id = row['series_id']
            m_id = row[mal_id_col]
            if pd.notna(m_id):
                existing_mappings[int(r_id)] = int(m_id)
        print(f"Loaded {len(existing_mappings)} pre-existing mappings from Ranobe file.")
        
    # Mark pre-existing MAL IDs as matched (to avoid duplicates)
    matched_mal_ids = set(existing_mappings.values())
    matched_ranobe_ids = set(existing_mappings.keys())
    
    # Compute word frequencies in MAL to exclude common words (stop words)
    print("Calculating word frequencies in MAL titles...")
    word_counts = Counter()
    for idx, row in df_mal.iterrows():
        for field in ['title', 'Japanese_Titles']:
            val = row.get(field)
            if val and isinstance(val, str):
                words = re.findall(r'\w+', val.lower())
                word_counts.update(set(words))
                
    # Filter out words appearing in > 60 series to avoid huge candidate list explosion
    valid_words = {word for word, count in word_counts.items() if count <= 60 and len(word) >= 4}
    print(f"Indexed {len(valid_words)} selective rare words for candidate matching.")
    
    # Pre-normalize MAL dataset
    print("Pre-normalizing MAL reference dataset...")
    mal_records = []
    mal_by_id = {}
    for idx, row in df_mal.iterrows():
        m_id = int(row['MAL_ID'])
        
        normalized_titles = []
        for field in ['title', 'Japanese_Titles']:
            norm = normalize_title(row.get(field))
            if norm:
                normalized_titles.append(norm)
                
        contributor_1_norm = normalize_name(row.get('contributor_1'))
        contributor_2_norm = normalize_name(row.get('contributor_2'))
        
        year = extract_year(row.get('Published'))
        
        rec = {
            'MAL_ID': m_id,
            'title': row['title'],
            'normalized_titles': normalized_titles,
            'contributor_1_norm': contributor_1_norm,
            'contributor_2_norm': contributor_2_norm,
            'year': year,
            'Volumes': row.get('Volumes'),
            'original_titles_str_list': [str(row.get('title', '')), str(row.get('Japanese_Titles', ''))]
        }
        mal_records.append(rec)
        mal_by_id[m_id] = rec

    # Index MAL reference data for fast candidate lookup
    print("Indexing MAL reference dataset...")
    mal_by_word = {}
    mal_by_creator = {}
    
    for rec in mal_records:
        m_id = rec['MAL_ID']
        
        # Index by creator
        for creator_norm in [rec['contributor_1_norm'], rec['contributor_2_norm']]:
            if creator_norm:
                mal_by_creator.setdefault(creator_norm, []).append(m_id)
                
        # Index by title words
        for val in rec['original_titles_str_list']:
            if val:
                words = re.findall(r'\w+', val.lower())
                for w in words:
                    if w in valid_words:
                        mal_by_word.setdefault(w, []).append(m_id)

    # Pre-normalize Ranobe dataset
    print("Pre-normalizing Ranobe dataset...")
    ranobe_records = []
    for idx, row in df_ranobe.iterrows():
        r_id = int(row['series_id'])
        
        normalized_titles = []
        for field in ['title', 'ai_eng', 'title_orig', 'romaji_orig']:
            norm = normalize_title(row.get(field))
            if norm:
                normalized_titles.append(norm)
                
        author_norm = normalize_name(row.get('author'))
        artist_norm = normalize_name(row.get('artist'))
        
        year = extract_year(row.get('start_date'))
        
        ranobe_records.append({
            'series_id': r_id,
            'normalized_titles': normalized_titles,
            'author_norm': author_norm,
            'artist_norm': artist_norm,
            'year': year,
            'num_books': row.get('num_books'),
            'original_titles_str_list': [str(row.get('title', '')), str(row.get('ai_eng', '')), 
                                         str(row.get('title_orig', '')), str(row.get('romaji_orig', ''))]
        })
                        
    # Generate match candidates
    print("Generating match candidates...")
    candidates = []
    
    total_records = len(ranobe_records)
    for idx, r_rec in enumerate(ranobe_records):
        r_id = r_rec['series_id']
        if r_id in matched_ranobe_ids:
            continue
            
        if idx % 5000 == 0 and idx > 0:
            print(f"  Processed {idx}/{total_records} Ranobe records...")
            
        cand_ids = set()
        
        # Match title words
        for val in r_rec['original_titles_str_list']:
            if val:
                words = re.findall(r'\w+', val.lower())
                for w in words:
                    if w in mal_by_word:
                        cand_ids.update(mal_by_word[w])
                        
        # Match creator
        for creator_norm in [r_rec['author_norm'], r_rec['artist_norm']]:
            if creator_norm and creator_norm in mal_by_creator:
                cand_ids.update(mal_by_creator[creator_norm])
                
        # Evaluate match score for candidate set
        for m_id in cand_ids:
            if m_id in matched_mal_ids:
                continue
                
            m_rec = mal_by_id[m_id]
            score = compute_match_score_fast(r_rec, m_rec)
            if score >= 0.60:
                candidates.append((r_id, m_id, score))
                
    print(f"Generated {len(candidates)} candidate matching pairs.")
    
    # Sort candidates by score descending
    candidates.sort(key=lambda x: x[2], reverse=True)
    
    # Bipartite matching (1-to-1 constraint resolution)
    print("Performing 1-to-1 matching...")
    bipartite_mappings = {}
    
    for r_id, m_id, score in candidates:
        if r_id not in matched_ranobe_ids and m_id not in matched_mal_ids:
            bipartite_mappings[r_id] = (m_id, score)
            matched_ranobe_ids.add(r_id)
            matched_mal_ids.add(m_id)
            
    print(f"Created {len(bipartite_mappings)} new 1-to-1 mappings.")
    
    # Build final columns
    print("Assembling final columns...")
    final_mal_ids = []
    final_mal_titles = []
    final_match_scores = []
    
    for idx, row in df_ranobe.iterrows():
        r_id = int(row['series_id'])
        if r_id in existing_mappings:
            m_id = existing_mappings[r_id]
            mal_title = mal_by_id[m_id]['title'] if m_id in mal_by_id else "Pre-mapped"
            score = 1.0
        elif r_id in bipartite_mappings:
            m_id, score = bipartite_mappings[r_id]
            mal_title = mal_by_id[m_id]['title']
        else:
            m_id, mal_title, score = pd.NA, pd.NA, pd.NA
            
        final_mal_ids.append(m_id)
        final_mal_titles.append(mal_title)
        final_match_scores.append(round(score, 3) if pd.notna(score) else pd.NA)
        
    df_output = df_ranobe.copy()
    df_output['MAL_ID_Matched'] = final_mal_ids
    df_output['MAL_Title_Matched'] = final_mal_titles
    df_output['Match_Score'] = final_match_scores
    
    # Summary stats
    new_match_count = len(bipartite_mappings)
    total_match_count = df_output['MAL_ID_Matched'].notna().sum()
    
    print("\n" + "="*40)
    print("MATCHING COMPLETION SUMMARY")
    print(f"Pre-existing mappings: {len(existing_mappings)}")
    print(f"New automated mappings: {new_match_count}")
    print(f"Total matched Ranobe series: {total_match_count} / {total_records} ({total_match_count/total_records*100:.2f}%)")
    print("="*40)
    
    print(f"Saving output to: {output_path}")
    df_output.to_excel(output_path, index=False)
    print("Done! Mapping completed successfully.")

if __name__ == "__main__":
    main()
