"""
Q&A over a small knowledge graph using OpenAI's Responses API.
"""

import os
import json, pdb, datetime as dt, sys
from openai import OpenAI
from snowflake_utils import query_snowflake
from dotenv import load_dotenv

load_dotenv()

question = sys.argv[1]
#question = "Can you create a professional biography of leland brewster?"

prompt_sent = dt.datetime.now()

#get relevant nodes
nodes = query_snowflake("""
        SELECT r.ENTITY_ID
                , r.NAME
                , r.WEBSITE
                --, PROFILE:"metadata":"key_topics" as key_topics
        FROM RDH.PUBLIC.ENTITIES_RESOLVED r
        LEFT JOIN RDH.PUBLIC.ENTITIES m on r.entity_id = m.entity_id
        WHERE 1=1
        AND NOT ( WEBSITE IS NULL AND LINKEDIN_URL IS NULL AND EMAIL IS NULL )
""")
nodes = nodes.to_dict('records')

# ---- Call OpenAI Responses API -----------------------------------------
client = OpenAI(api_key=os.getenv("OPEN_AI_API_KEY"))
model = os.getenv("OPENAI_MODEL", "gpt-4.1")  # set to a model you have access to

#step 1: find relevant nodes
prompt = f"""
            Which of the entities listed below are relevant to the question?\n
            {question}
            Entities:\n
            {nodes}
        """
system_instructions = """
    Return a list of comma-separated entity ids on 1 line that are likely to be relevant to the question. 
"""

response = client.chat.completions.create(
    model='gpt-4o-mini',
    messages=[
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": prompt}
    ])
raw_text = response.choices[0].message.content
relevant_node_entities = ','.join(f"'{x.strip()}'" for x in raw_text.split(','))

if(not len(relevant_node_entities)):
    print( 'No relevant information found in knowledge graph.')
    exit(0)

edges = query_snowflake(f"""
            SELECT SOURCE, TARGET, RELATIONSHIP, RELATIONSHIP_STRENGTH
            FROM RDH.PUBLIC.knowledge_graph
            WHERE 1=1
            --AND ( SOURCE IN ({relevant_node_entities}) OR TARGET IN ({relevant_node_entities}))
    """)
edges = edges.to_dict('records')

#full details on relevant nodes
relevant_nodes = query_snowflake(f"""
        SELECT r.ENTITY_ID
                , r.NAME
                , r.WEBSITE
                , r.LINKEDIN_URL
                , m.PROFILE
        FROM RDH.PUBLIC.ENTITIES_RESOLVED r
        LEFT JOIN RDH.PUBLIC.ENTITIES m on r.entity_id = m.entity_id
        WHERE 1=1
        --AND r.entity_id IN ({relevant_node_entities})
""")
relevant_nodes = relevant_nodes.to_dict('records')

# ---- Serialize graph ----------------------------------------------------
graph_payload = {
    "schema": {
        "nodes": {"ENTITY_ID": "string", "PAYLOAD": "string"},
        "edges": {"SOURCE": "string", "TARGET": "string", "RELATIONSHIP_TYPE": "string", "RELATIONSHIP_STRENGTH": "decimal"},
    },
    "data": {"nodes": relevant_nodes, "edges": edges},
}

# ---- Compose instructions ----------------------------------------------
system_instructions = (
    "You are a helpful researcher. You can use BOTH: "
    "(1) the small knowledge graph provided (as JSON) and "
    "(2) your general world knowledge. "
    "When answering:\n"
    "- Prefer facts supported by the graph; augment with general knowledge as needed.\n"
#    "- Return only valid JSON. No prose, no markdown."
    "- Answer strictly in simple terms. Never reference the graph itself, edges, nodes or other technical terms.\n"
    "- Entities can be connected indirectly, not just with direct connections between their nodes.\n"
    "- Keep the answer under 200 words."

)

user_prompt = (
    "Answer the user's question using the graph and general knowledge.\n\n"
    f"Question: {question}\n\n"
    "Knowledge Graph (JSON):\n"
    f"{json.dumps(graph_payload, ensure_ascii=False)}"
)

#print('Prompt sent to GPT. Waiting for response...')


response = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_prompt}
    ])
elapsed = dt.datetime.now() - prompt_sent
total_seconds = int(elapsed.total_seconds())
minutes, seconds = divmod(total_seconds, 60)

print(f"Query executed in: {minutes}m:{seconds:02d}s")

raw_text = response.choices[0].message.content

print("Answer:", raw_text)

