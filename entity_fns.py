import pandas as pd, pdb, json
import recordlinkage
from typing import List, Dict, Optional
import re
import uuid
import snowflake.connector
from snowflake_utils import query_snowflake, upsert_to_snowflake, write_to_snowflake
import datetime as dt

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
        - entity_id: a GUID for the entity
    """
    
    if not known_entities:
        return {
            'matches': [],
            'best_match': None,
            'is_new': True,
            'confidence': 0.0,
            'entity_id': str(uuid.uuid4())  # Generate new UUID for new entity
        }

    entity = {k: v for k, v in entity.items() if v is not None and len(v)}
    assert len(entity.keys())
    known_entities = [{k: v for k, v in e.items() if k in entity.keys() or k in ['entity_id']} for e in known_entities]

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
        if 'website' in df.columns:
            df['website_clean'] = df['website'].fillna('').apply(_clean_string_generic)
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
    if 'name' in df_new.columns:
        compare.string('name_clean', 'name_clean', method='jarowinkler', label='name')
    
    if 'email' in df_new.columns:
        compare.exact('email_clean', 'email_clean', label='email')

    if 'phone' in df_new.columns:
        compare.exact('phone_clean', 'phone_clean', label='phone')
    
    if 'linkedin_url' in df_new.columns:
        compare.exact('linkedin_clean', 'linkedin_clean', label='linkedin_url')
    
    if 'website' in df_new.columns:
        compare.exact('website_clean', 'website_clean', label='website')
    
    if 'address' in df_new.columns:
        compare.string('address_clean', 'address_clean', method='jarowinkler', label='address')
    
    # Compute comparison scores
    features = compare.compute(candidate_pairs, df_new, df_known)
    # Calculate weighted scores
    weights = {
        'email': 0.35,
        'phone': 0.30,
        'linkedin_url': 0.25,
        'name': 0.07,
        'address': 0.03,
        'website': 0.25,
    }
    perfect_matches = ['phone', 'email', 'linkedin_url', 'website']

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

    if is_new or 'id' not in best_match['entity']:
        entity_id = str(uuid.uuid4())  # Convert to string
    else:
        entity_id = best_match['entity']['id']
    
    return {
        'matches': matches,
        'best_match': best_match,
        'is_new': is_new,
        'confidence': best_match['confidence'] if best_match else 0.0,
        'entity_id': entity_id
    }

def get_existing_entities(conn: Optional[snowflake.connector.SnowflakeConnection] = None) -> List[Dict]:
    """
    Get existing entities from Snowflake as a list of dictionaries
    
    Args:
        conn: Optional Snowflake connection
        
    Returns:
        List of entity dictionaries
    """
    df = query_snowflake('SELECT * FROM RDH.PUBLIC.ENTITIES_RESOLVED', conn=conn)
    df.columns = df.columns.str.lower()
    # Convert to list of dicts and replace NaN with None
    entities = df.replace({pd.NA: None}).to_dict('records')

    for entity in entities:
        try:
            entity['entity_types'] = [ ] if( entity['entity_types'] is None) else json.loads(entity['entity_types'])
        except:
            pdb.set_trace()

    #print(f"✓ Loaded {len(entities)} existing entities from Snowflake")
    return entities

def _validate_entity(entity: dict) -> bool:
    """
    Validate that an entity has required fields

    Args:
        entity: Dictionary representing an entity

    Returns:
        True if valid, False otherwise
    """
    # Check for entity_type
    if 'entity_type' not in entity or not entity['entity_type']:
        return False

    # Check for at least one identifier field
    identifier_fields = ['name', 'email', 'phone', 'website', 'linkedin_url']
    has_identifier = any(
        field in entity and entity[field] and str(entity[field]).strip()
        for field in identifier_fields
    )
    return has_identifier


def ingest_entities(entities: List[Dict]) -> List[Dict]:
    """
    Ingest a list of entities by resolving them against existing entities and upserting to Snowflake.

    This function validates entities, performs entity resolution to identify matches with existing entities,
    merges entity information, and persists updates to Snowflake. It handles both new entities and updates
    to existing ones, consolidating entity_types and merging field values.

    Args:
        entities: List of entity dictionaries to ingest. Each must have 'entity_type' and at least
                 one identifier field (name, email, phone, website, linkedin_url)
        existing_entities: List of known entity dictionaries from Snowflake. Will be mutated to include
                          new entities and updates

    Returns:
        None. Side effects include:
        - Updates to existing_entities list (mutates in place)
        - Upserts to RDH.PUBLIC.ENTITIES_RESOLVED table in Snowflake
        - Writes processing log to RDH.PUBLIC.ENTITY_RESOLUTION_LOG table
    """
    existing_entities = get_existing_entities()
    valid_entities = [x for x in entities if _validate_entity(x)]
    invalid_entities = [x for x in entities if not _validate_entity(x)]

    entity_matching_fields = ['entity_id', 'name', 'email', 'phone', 'website', 'linkedin_url', 'address']

    # compare valid entities vs. existing
    updates = {}
    for this_entity in valid_entities:
        this_resolved = resolve_entity(this_entity, existing_entities, threshold=0.7)
        if 'best_match' not in this_resolved.keys(): continue

        for field in entity_matching_fields:
            this_entity.setdefault(field, None)
        this_entity.setdefault('entity_types', [])

        if this_resolved['is_new']:
            new_entity = this_entity
            new_entity['entity_id'] = this_resolved['entity_id']
            new_entity['entity_types'] = [this_entity['entity_type']]
            new_entity.pop('entity_type', None)
            new_entity['event_type'] = 'CREATE'
            updates[new_entity['entity_id']] = new_entity
            existing_entities.append(new_entity)
        else:
            existing_entity = \
            [x for x in existing_entities if x['entity_id'] == this_resolved['best_match']['entity']['entity_id']][0]
            existing_entity['name'] = existing_entity['name'] if 'name' in existing_entity.keys() and existing_entity[
                'name'] is not None else this_entity['name']
            existing_entity['email'] = existing_entity['email'] or this_entity['email']
            existing_entity['phone'] = existing_entity['phone'] or this_entity['phone']
            existing_entity['website'] = existing_entity['website'] or this_entity['website']
            existing_entity['linkedin_url'] = existing_entity['linkedin_url'] or this_entity['linkedin_url']
            if not this_entity['entity_type'] in existing_entity['entity_types']:
                existing_entity['entity_types'].append(this_entity['entity_type'])
            existing_entity['event_type'] = 'UPDATE'
            updates[existing_entity[
                'entity_id']] = existing_entity  # this will overwrite each time through if more info gets added

    # make updates to snowflake
    updates_df = pd.DataFrame([x for x in updates.values()])
    updates_df.columns = updates_df.columns.str.upper()
    upsert_to_snowflake(updates_df, table_name='ENTITIES_RESOLVED', key_columns=['entity_id'], database='RDH',
                        schema='PUBLIC')

    # write processed entities to a log
    log_entries = pd.concat([
        pd.DataFrame({
            'entry': valid_entities,
            'is_valid': [1] * len(valid_entities),
            'update_ts': [dt.datetime.now(dt.timezone.utc)] * len(valid_entities)
        }),
        pd.DataFrame({
            'entry': invalid_entities,
            'is_valid': [0] * len(invalid_entities),
            'update_ts': [dt.datetime.now(dt.timezone.utc)] * len(invalid_entities)
        })
    ], ignore_index=True)

    write_to_snowflake(
        df=log_entries,
        table_name='ENTITY_RESOLUTION_LOG',
        database='RDH',
        schema='PUBLIC',
        auto_create_table=True
    )
    return(updates)