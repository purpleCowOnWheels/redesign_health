from openai import OpenAI
from dotenv import load_dotenv
import os, pdb, json, pandas as pd, datetime as dt
from entity_fns import ingest_entities
from snowflake_utils import upsert_to_snowflake

load_dotenv()

client = OpenAI(api_key=os.getenv('OPEN_AI_API_KEY'))

artifact = 'https://www.linkedin.com/in/lelandbrewster/'

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

For every entity you find, please also extend the graph by 1 degree of separation

"""

response = client.chat.completions.create(
    model="gpt-4.1",  # full
    # model = 'gpt-4o-mini', #light
    messages=[
        {"role": "system", "content": "You are an assistant that outputs structured JSON only."},
        {"role": "user", "content": prompt}
    ],
    temperature=0  # deterministic, good for structured output
)
raw_text = response.choices[0].message.content
# parse it into Python dict
try:
    json_output = json.loads(raw_text)
except json.JSONDecodeError as e:
    print("❌ Failed to parse JSON:", e)
    print("Raw output:", raw_text)
resolved_entities = ingest_entities(json_output['nodes'])

#swap in the entity id for each node and edge

name_to_id = {v["name"]: v["entity_id"] for v in resolved_entities.values()}
# replace edge endpoints with ids

edges = json_output["edges"].copy()
for e in edges:
    if e['source'] not in name_to_id or e['target'] not in name_to_id: continue
    e[source] = name_to_id[e['source']]
    e[target] = name_to_id[e['target']]

edges_df = pd.DataFrame(edges)
edges_df.columns = edges_df.columns.str.upper()
upsert_to_snowflake(edges_df, table_name='KNOWLEDGE_GRAPH', key_columns=['SOURCE', 'TARGET', 'RELATIONSHIP', 'ARTIFACT'], database='RDH', schema='PUBLIC')

pdb.set_trace()