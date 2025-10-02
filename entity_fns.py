import pandas as pd, pdb
import recordlinkage
from recordlinkage.preprocessing import clean, phonetic
from typing import List, Dict, Optional
import re


def _clean_text(text: str) -> str:
    """Helper function to clean text strings"""
    if not text or pd.isna(text):
        return ''
    text = str(text).lower().strip()
    # Remove special characters and extra spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _clean_string_generic(text: str) -> str:
    """Generic string cleanup for emails, phones, addresses, and URLs"""
    if not text or pd.isna(text):
        return ''
    text = str(text).lower().strip()
    
    # For URLs: remove protocol and www subdomain
    text = re.sub(r'^https?://', '', text)
    text = re.sub(r'^www\.', '', text)
    
    # Remove all non-alphanumeric characters (keeps letters and numbers only)
    text = re.sub(r'[^a-z0-9]', '', text)
    
    return text


def resolve_entity(
    entity: Dict[str, Optional[str]], 
    known_entities: List[Dict[str, Optional[str]]],
    threshold: float = 0.7
) -> Dict:
    """
    Resolves a entity's metadata against a list of known people using recordlinkage library.
    
    Args:
        entity: Dictionary with keys: name, phone, email, linkedin_url, address
        known_entities: List of known entity dictionaries with same structure
        threshold: Minimum similarity score to consider a match (0.0 to 1.0)
        
    Returns:
        Dictionary containing:
        - matches: List of matched people with confidence scores
        - best_match: The highest scoring match (if any)
        - is_new: Boolean indicating if this is likely a new entity
        - confidence: Confidence score of best match
    """
    
    if not known_entities:
        return {
            'matches': [],
            'best_match': None,
            'is_new': True,
            'confidence': 0.0
        }
    
    # Convert to DataFrames
    df_new = pd.DataFrame([entity], index=[0])
    df_known = pd.DataFrame(known_entities)
    df_known.index = df_known.index.astype(str)
    
    # Clean and preprocess data
    for df in [df_new, df_known]:
        if 'name' in df.columns:
            df['name_clean'] = df['name'].fillna('').apply(_clean_text)
        if 'email' in df.columns:
            df['email_clean'] = df['email'].fillna('').apply(_clean_string_generic)
        if 'phone' in df.columns:
            df['phone_clean'] = df['phone'].fillna('').apply(_clean_string_generic)
        if 'linkedin_url' in df.columns:
            df['linkedin_clean'] = df['linkedin_url'].fillna('').apply(_clean_string_generic)
        if 'address' in df.columns:
            df['address_clean'] = df['address'].fillna('').apply(_clean_string_generic)
    
    # Create indexer
    indexer = recordlinkage.Index()
    indexer.full()
    
    # Generate candidate pairs
    candidate_pairs = indexer.index(df_new, df_known)
    
    if len(candidate_pairs) == 0:
        return {
            'matches': [],
            'best_match': None,
            'is_new': True,
            'confidence': 0.0
        }
    
    # Create comparison object
    compare = recordlinkage.Compare()
    
    # Add comparison rules
    if 'name' in df_new.columns and 'name' in df_known.columns:
        compare.string('name_clean', 'name_clean', method='jarowinkler', label='name')
    
    if 'email' in df_new.columns and 'email' in df_known.columns:
        compare.exact('email_clean', 'email_clean', label='email')
    
    if 'phone' in df_new.columns and 'phone' in df_known.columns:
        compare.exact('phone_clean', 'phone_clean', label='phone')
    
    if 'linkedin_url' in df_new.columns and 'linkedin_url' in df_known.columns:
        compare.exact('linkedin_clean', 'linkedin_clean', label='linkedin_url')
    
    if 'address' in df_new.columns and 'address' in df_known.columns:
        compare.string('address_clean', 'address_clean', method='jarowinkler', label='address')
    
    # Compute comparison scores
    features = compare.compute(candidate_pairs, df_new, df_known)
    
    # Calculate weighted scores
    weights = {
        'email': 0.35,
        'phone': 0.30,
        'linkedin_url': 0.25,
        'name': 0.07,
        'address': 0.03
    }
    perfect_matches = ['phone', 'email', 'linkedin_url']

    # Calculate total score for each match
    matches = []
    for idx, row in features.iterrows():
        score_dict = row.to_dict()
        known_idx = int(idx[1])
        known_entity = known_entities[known_idx]
        null_fields = [k for k, v in entity.items() if v is None and known_entity.get(k) is None]
        filtered_scores = {k: v for k, v in score_dict.items() if k not in null_fields}

        perfect_match_helper = [score_dict[x] for x in perfect_matches if x in filtered_scores.keys()]
        if len(perfect_match_helper) and max(perfect_match_helper) == 1:
            confidence = 1
        else:
            compared_weights = max(sum(weights.get(col, 0) for col in filtered_scores.keys()), 0.25) # Require at least 25% of total weight to be compared
            confidence = sum(filtered_scores.get(col, 0) * weights.get(col, 0) for col in weights.keys()) / compared_weights
        
        if confidence >= threshold:
            matches.append({
                'entity': known_entities[known_idx],
                'confidence': round(confidence, 3),
                'matching_fields': {k: round(v, 3) for k, v in filtered_scores.items() if v > 0}
            })

    # Sort by confidence
    matches.sort(key=lambda x: x['confidence'], reverse=True)

    best_match = matches[0] if matches else None
    is_new = len(matches) == 0

    return {
        'matches': matches,
        'best_match': best_match,
        'is_new': is_new,
        'confidence': best_match['confidence'] if best_match else 0.0
    }