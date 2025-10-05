from openai import OpenAI
from dotenv import load_dotenv
import os, pdb, json, pandas as pd, datetime as dt, re, shutil
from entity_fns import ingest_entities
from pathlib import Path
from snowflake_utils import upsert_to_snowflake

load_dotenv()

client = OpenAI(api_key=os.getenv('OPEN_AI_API_KEY'))
model = os.getenv("OPENAI_MODEL", "gpt-4.1")  # set to a model you have access to

root_dir = r'C:\Users\danie\Dropbox\Personal\Jobs\Company Specific Docs\Redesign_Health\artifacts'
directory_path = Path(root_dir) / 'new_artifacts'
processed_dir = Path(root_dir) / 'parsed_artifacts'

for artifact_location in Path(directory_path).glob("*.txt"):
    print( f"Processing {artifact_location}...")
    with open(artifact_location, "r", encoding="utf-8") as f:
        artifact = f.read()
    dest = processed_dir / artifact_location.name
    stem, ext = dest.stem, dest.suffix
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_ts = processed_dir / f"{stem}_{timestamp}{ext}"
    shutil.move(str(artifact_location), dest_ts)

    prompt = f"""
    can you please parse this artifact:
    {artifact}
    
    from it, please extract any entities you can find and attempt to locate the following public information about them. Please do a deep, diligent search for these fields, especially the linkedin_url and website.
    {{
        entity_type: XYZ, #prefer these options: [company, person]
        linkedin_url: linkedin.com/XYZ,
        website: XYZ.com,
        name: XYZ,
        email: XYZ,
        phone: XYZ,
        address: XYZ
    }}
    
    Return these entities as a list. then generate the edges of a knowledge graph connecting the entities to each other in this general format:
    
    {{
        "source": "Redesign Health",
        "target": "Aron Szanto",
        "relationship": "Appointed as Head of Technology",
        "relationship_strength": 0.9,
        "other_info": [],
        "artifact_date": 12/31/2024
        "artifact": "www.linkedin.com/in/aronszanto/" #link to the artifact that generated this edge
    
    }}
    
    the final output should be structured as follows:
    {{
        nodes:[{{
        entity_type: XYZ,
        linkedin_url: linkedin.com/XYZ,
        website: XYZ.com,
        name: XYZ,
        email: XYZ,
        phone: XYZ,
        address: XYZ
    }}, {{
        entity_type: XYZ,
        linkedin_url: linkedin.com/XYZ,
        website: XYZ.com,
        name: XYZ,
        email: XYZ,
        phone: XYZ,
        address: XYZ
    }} ],
    edges:[{{
        "source": "Redesign Health",
        "target": "Aron Szanto",
        "relationship": "Appointed as Head of Technology",
        "relationship_strength": 0.9,
        "other_info": [],
        "artifact_date": 12/31/2024
        "artifact": "www.linkedin.com/in/aronszanto/" #link to the artifact that generated this edge
    
    }},{{
        "source": "Redesign Health",
        "target": "Aron Szanto",
        "relationship": "Appointed as Head of Technology",
        "relationship_strength": 0.9,
        "other_info": [],
        "artifact_date": 12/31/2024,
        "artifact": "www.linkedin.com/in/aronszanto/" #link to the artifact that generated this edge
    
    }}]}}
    
    Every Source and Target should appear as a Name in a Node.
    
    All Artifact Dates should be actual dates in the format YYYY-MM-DD. If you do not know the exact date pick a near-enough one.
    
    For every entity you find, please also extend the graph by 1 degrees of separation
    
    The final output should be a JSON object.
    
    """
    print('  >> Prompt sent to GPT. Waiting for response...')
    prompt_sent = dt.datetime.now()
    response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},  # or json_schema (best)
            messages=[
                {"role": "system", "content": "Return only valid JSON. Please validate it. No prose, no markdown."},
                {"role": "user", "content": prompt}
            ],
            seed=7,
            n=1
        )

    print( '  >> GPT executed in :' + str(dt.datetime.now() - prompt_sent))

    raw_text = response.choices[0].message.content
    clean_text = re.sub(r'[\x00-\x1f\x7f]', '', raw_text)

    try:
        json_output = json.loads(clean_text)
    except json.JSONDecodeError as e:
        print("Raw text:", raw_text)
        print("❌ Failed to parse JSON:", e)
    resolved_entities = ingest_entities(json_output['nodes'])

    #swap in the entity id for each node and edge
    name_to_id = {v["name"]: v["entity_id"] for v in resolved_entities.values()}

    edges = json_output["edges"].copy()
    for e in edges:
        if e['source'] not in name_to_id or e['target'] not in name_to_id: continue
        e['source'] = name_to_id[e['source']]
        e['target'] = name_to_id[e['target']]

    edges_df = pd.DataFrame(edges)
    edges_df.columns = edges_df.columns.str.upper()
    upsert_to_snowflake(edges_df, table_name='KNOWLEDGE_GRAPH', key_columns=['SOURCE', 'TARGET', 'RELATIONSHIP', 'ARTIFACT'], database='RDH', schema='PUBLIC')
pdb.set_trace()