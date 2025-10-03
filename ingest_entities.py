import json, pdb, pandas as pd, shutil, datetime as dt
from pathlib import Path
from entity_fns import get_existing_entities, resolve_entity
from snowflake_utils import upsert_to_snowflake, write_to_snowflake

existing_entities = get_existing_entities()
root_dir = r'C:\Users\danie\Dropbox\Personal\Jobs\Company Specific Docs\Redesign_Health'
directory_path = Path(root_dir) / 'new_entities'
processed_dir = Path(root_dir) / 'parsed_entities'

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

# Load all JSON files and flatten into single list
all_entities = []
for json_file in Path(directory_path).glob("*.json"):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        all_entities.extend(data if isinstance(data, list) else [data])

valid_entities = [x for x in all_entities if _validate_entity(x)]
invalid_entities = [x for x in all_entities if not _validate_entity(x)]

entity_matching_fields = ['entity_id', 'name', 'email', 'phone', 'website', 'linkedin_url', 'address']

#compare valid entities vs. existing
updates = {}
for this_entity in valid_entities:
    this_resolved = resolve_entity(this_entity, existing_entities, threshold = 0.7)

    for field in entity_matching_fields:
        this_entity.setdefault(field, None)
    this_entity.setdefault('entity_types', [])

    if( this_resolved['is_new'] ):
        new_entity = this_entity
        new_entity['entity_id'] = this_resolved['entity_id']
        new_entity['entity_types'] = [this_entity['entity_type']]
        new_entity.pop('entity_type', None)
        updates[new_entity['entity_id']] = new_entity
        existing_entities.append(new_entity)
    else:
        existing_entity = [x for x in existing_entities if x['entity_id'] == this_resolved['best_match']['entity']['entity_id']][0]
        existing_entity['name'] = existing_entity['name'] if 'name' in existing_entity.keys() and existing_entity['name'] is not None else this_entity['name']
        existing_entity['email'] = existing_entity['email'] or this_entity['email']
        existing_entity['phone'] = existing_entity['phone'] or this_entity['phone']
        existing_entity['website'] = existing_entity['website'] or this_entity['website']
        existing_entity['linkedin_url'] = existing_entity['linkedin_url'] or this_entity['linkedin_url']
        if not this_entity['entity_type'] in existing_entity['entity_types']:
            existing_entity['entity_types'].append(this_entity['entity_type'])
        updates[existing_entity['entity_id']] = existing_entity #this will overwrite each time through if more info gets added

#make updates to snowflake
updates_df = pd.DataFrame([x for x in updates.values()])
updates_df.columns = updates_df.columns.str.upper()
upsert_to_snowflake(updates_df, table_name = 'ENTITIES_RESOLVED', key_columns = ['entity_id'], database = 'RDH', schema = 'PUBLIC')

#write processed entities to a log
log_entries = pd.concat([
    pd.DataFrame({
        'entry': valid_entities,
        'is_valid': [1] * len(valid_entities),
        'update_ts': [dt.datetime.now()] * len(valid_entities)
    }),
    pd.DataFrame({
        'entry': invalid_entities,
        'is_valid': [0] * len(invalid_entities),
        'update_ts': [dt.datetime.now()] * len(invalid_entities)
    })
], ignore_index=True)

write_to_snowflake(
    df = log_entries,
    table_name ='ENTITY_RESOLUTION_LOG',
    database = 'RDH',
    schema = 'PUBLIC',
    auto_create_table = True
)

#move processed entities into the processed folder
for json_file in Path(directory_path).glob("*.json"):
    shutil.move(str(json_file), processed_dir / json_file.name)