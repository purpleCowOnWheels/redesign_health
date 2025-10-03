import json, pdb, pandas as pd, shutil
from pathlib import Path
from entity_fns import ingest_entities
root_dir = r'C:\Users\danie\Dropbox\Personal\Jobs\Company Specific Docs\Redesign_Health'
directory_path = Path(root_dir) / 'new_entities'
processed_dir = Path(root_dir) / 'parsed_entities'

# Load all JSON files and flatten into single list
all_entities = []
for json_file in Path(directory_path).glob("*.json"):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        all_entities.extend(data if isinstance(data, list) else [data])

ingest_entities(all_entities)

#move processed entities into the processed folder
for json_file in Path(directory_path).glob("*.json"):
    shutil.move(str(json_file), processed_dir / json_file.name)