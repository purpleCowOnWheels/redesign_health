from openai import OpenAI
from dotenv import load_dotenv
import os, pdb, json, pandas as pd, datetime as dt
from snowflake_utils import query_snowflake, upsert_to_snowflake

load_dotenv()
model = os.getenv("OPENAI_MODEL", "gpt-4.1")  # set to a model you have access to

entities = query_snowflake(
    f"""SELECT *
FROM RDH.PUBLIC.ENTITIES_RESOLVED r
LEFT JOIN RDH.PUBLIC.ENTITIES m on r.entity_id = m.entity_id
WHERE M.ENTITY_ID IS NULL""")

if not len(entities): exit(0)

entities = entities.to_dict(orient = 'records')

client = OpenAI(api_key=os.getenv('OPEN_AI_API_KEY'))
entity_results = {}

for indx, entity in enumerate(entities):
    print(f'Querying chatgpt for {indx} of {len(entities)}')
    prompt = f"""
    Summarize publicly available information about {entity}.
    Output strictly in JSON with this schema:

    {{
    "entity_type": string, -> prefer "company" or "person" or "school" or "investment_fund" or "investment_manager" if applicable
      "metadata": {{
        "full_name": string,
        "known_as": string or null,
        "wikipedia_page": string or null,
        "linkedin_profile": string or null,
        "entity_subtype": string -> max 1-2 words
        "key_topics": [
          {{
            "topic": string,
            "importance": float,   // between 0 and 1
            "evidence": string
          }}
        ],
        "keywords_associated": [string],
        "contact_information": {{
          "address": string or null,
          "phone": string or null,
          "email": string or null
        }},
        "recent_news": [
          {{
            "title": string,
            "date": string,   // YYYY or YYYY-MM-DD
            "themes": [string],
            "sentiment_score": float   // -1.0 to 1.0
          }}
        ]
      }}
    }}

    if entity type is "person" add the following:

    "entity_details": {{
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
      ]
    }}

    if the entity type is company, include the following:
    "entity_details": {{
      "founded_year": int or null,
      "founders": [string],
      "key_employees": [
        {{
          "name": string,
          "linkedin_url": string,
          "short_bio": string
        }}
      ],
      "description": string,
      "number_of_employees_estimated": string,
      "industry": string,
      "sub_industry": string,
      "lifecycle_stage": string -> prefer the options: Seed, Growth_Stage, Mature_Private, Mature_Public
    }}

    Rules:
    - Populate fields with the best available public info.
    - Use null when no information is available, do not invent.
    - Dates should be ISO-like strings (YYYY or YYYY-MM-DD).
    - sentiment_score must be numeric between -1.0 and +1.0.
    - Return only the JSON object, no explanation or extra text.

    """

    response = client.chat.completions.create(
        model=model,  #full
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
    entity_results[entity['ENTITY_ID']] = json_output

# Convert dict → DataFrame
df = pd.DataFrame([
    {"ENTITY_ID": k, "PROFILE": v}  # stringify the value
    for k, v in entity_results.items()
])
df['UPDATE_TS'] = dt.datetime.now(dt.timezone.utc)

#upsert to Snowflake
upsert_to_snowflake(df, table_name = 'ENTITIES', key_columns = ['ENTITY_ID'], database = 'RDH', schema = 'PUBLIC')

