"""
Q&A over a small knowledge graph using OpenAI's Responses API.

Setup:
  pip install --upgrade openai
  export OPENAI_API_KEY=sk-...
  # Optionally:
  export OPENAI_MODEL=gpt-5.1  # or another available model
Docs:
  - OpenAI Python SDK + Responses API examples:
    https://github.com/openai/openai-python
  - API reference:
    https://platform.openai.com/docs/api-reference
"""

import os
import json, pdb, datetime as dt
from openai import OpenAI
from snowflake_utils import query_snowflake
from dotenv import load_dotenv

load_dotenv()

#get relevant nodes
nodes = query_snowflake("SELECT ENTITY_ID, NAME, ENTITY_TYPES FROM RDH.PUBLIC.ENTITIES_RESOLVED WHERE 1=1")
nodes = nodes.to_dict('records')

edges = query_snowflake("SELECT SOURCE, TARGET, RELATIONSHIP, RELATIONSHIP_STRENGTH FROM RDH.PUBLIC.knowledge_graph WHERE 1=1")
edges = edges.to_dict('records')

#question = "Does Aron know Leland Brewster?"
#question = "How well does Aron know Leland Brewster?"
question = "What types of companies does Redsign Health like to invest in? Are there any companies they are not directly affiliated with but could be interested in?"

# ---- Serialize graph ----------------------------------------------------
graph_payload = {
    "schema": {
        "nodes": {"ENTITY_ID": "string", "NAME": "string", "ENTITY_TYPE": "string"},
        "edges": {"SOURCE": "string", "TARGET": "string", "RELATIONSHIP_TYPE": "string", "RELATIONSHIP_STRENGTH": "decimal"},
    },
    "data": {"nodes": nodes, "edges": edges},
}

# ---- Compose instructions ----------------------------------------------
system_instructions = (
    "You are a helpful researcher. You can use BOTH: "
    "(1) the small knowledge graph provided (as JSON) and "
    "(2) your general world knowledge. "
    "When answering:\n"
    "- Prefer facts supported by the graph; augment with general knowledge as needed.\n"
    #"- Briefly cite which graph nodes/edges you used by id (e.g., n1→n3).\n"
    "- Answer strictly in simple terms. Never reference the graph itself, edges, nodes or other technical terms.\n"
    "- Keep the answer under 200 words."

)

user_prompt = (
    "Answer the user's question using the graph and general knowledge.\n\n"
    f"Question: {question}\n\n"
    "Knowledge Graph (JSON):\n"
    f"{json.dumps(graph_payload, ensure_ascii=False)}"
)

# ---- Call OpenAI Responses API -----------------------------------------
client = OpenAI(api_key=os.getenv("OPEN_AI_API_KEY"))
model = os.getenv("OPENAI_MODEL", "gpt-4.1")  # set to a model you have access to

print('Prompt sent to GPT. Waiting for response...')
prompt_sent = dt.datetime.now()


response = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": "Return only valid JSON. No prose, no markdown."},
        {"role": "user", "content": user_prompt}
    ])
print( 'GPT executed in :' + str(dt.datetime.now() - prompt_sent))

raw_text = response.choices[0].message.content

print("\n=== Answer ===\n")
try:
    json_output = json.loads(raw_text)
    print(json.dumps(json_output, indent=2, ensure_ascii=False))
except json.JSONDecodeError as e:
    print("Raw text:", raw_text)
    print("❌ Failed to parse JSON:", e)

