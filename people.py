from openai import OpenAI
from dotenv import load_dotenv
import os, pdb, json, pandas as pd, datetime as dt
from snowflake_utils import query_snowflake, upsert_to_snowflake

load_dotenv()

person_entities = []
if( len( person_entities ) ):
    ids_sql = ",".join(f"'{x}'" for x in person_entities)
    people = query_snowflake(f"SELECT * from RDH.PUBLIC.ENTITIES_RESOLVED WHERE entity_id IN ({ids_sql}) and ARRAY_CONTAINS('person'::variant, entity_types)").to_dict('records')
else:
    people = query_snowflake(
        f"SELECT * from RDH.PUBLIC.ENTITIES_RESOLVED WHERE ARRAY_CONTAINS('person'::variant, entity_types)").to_dict(
        'records')

client = OpenAI(api_key=os.getenv('OPEN_AI_API_KEY'))
people_results = {}

for indx, person in enumerate(people):
    print(f'Querying chatgpt for {indx} of {len(people)}')
    prompt = f"""
    Summarize publicly available information about {person}.
    Output strictly in JSON with this schema:
    
    {{
      "full_name": string,
      "known_as": string or null,
      "current_role": {{
        "title": string,
        "company": string,
        "company_linkedin": string or null,
        "start_year": int or null,
        "location": string or null
      }},
      "past_roles": [
        {{
          "title": string,
          "company": string,
          "company_linkedin": string or null,
          "years_active": string or null
        }}
      ],
      "education": {{
        "institution": string,
        "degree": string or null,
        "fields_of_study": [string],
        "institution_link": string or null
      }},
      "recognition": [
        {{
          "title": string,
          "year": int or null,
          "source": string
        }}
      ],
      "notable_mentions": [
        {{
          "title": string,
          "publisher": string,
          "url": string
        }}
      ],
      "wikipedia_page": string or null,
      "linkedin_profile": string or null,
      "key_topics": [
        {{
          "topic": string,
          "importance": float,   // between 0 and 1
          "evidence": string
        }}
      ]
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4.1",  #full
        #model = 'gpt-4o-mini', #light
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
    people_results[person['ENTITY_ID']] = json_output

# Convert dict → DataFrame
df = pd.DataFrame([
    {"ENTITY_ID": k, "BASIC_PROFILE": v}  # stringify the value
    for k, v in people_results.items()
])
df['UPDATE_TS'] = dt.datetime.now(dt.timezone.utc)

#upsert to Snowflake
upsert_to_snowflake(df, table_name = 'PEOPLE', key_columns = ['ENTITY_ID'], database = 'RDH', schema = 'PUBLIC')

