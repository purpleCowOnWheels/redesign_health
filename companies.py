from openai import OpenAI
from dotenv import load_dotenv
import os, pdb, json, pandas as pd, datetime as dt
from snowflake_utils import query_snowflake, upsert_to_snowflake

load_dotenv()

company_entities = []
if( len( company_entities ) ):
    ids_sql = ",".join(f"'{x}'" for x in company_entities)
    companies = query_snowflake(f"SELECT * from RDH.PUBLIC.ENTITIES_RESOLVED WHERE entity_id IN ({ids_sql}) and ARRAY_CONTAINS('company'::variant, entity_types)").to_dict('records')
else:
    companies = query_snowflake(
        f"SELECT * from RDH.PUBLIC.ENTITIES_RESOLVED WHERE ARRAY_CONTAINS('company'::variant, entity_types)").to_dict(
        'records')

client = OpenAI(api_key=os.getenv('OPEN_AI_API_KEY'))
company_results = {}

for indx, company in enumerate(companies):
    print(f'Querying chatgpt for {indx} of {len(companies)}')
    prompt = f"""
    Summarize publicly available information about {company}.
    Output strictly in JSON with this schema:

    {{
      "name": string,
      "type": string,
      "website": string,
      "linkedin_url": string or null,
      "headquarters": {{
        "primary": string,
        "other_offices": [string]
      }},
      "founded_year": int or null,
      "founders": [string],
      "description": string,
      "investment_focus": {{
        "stage": string or null,
        "sectors": [string]
      }},
      "recent_news": [
        {{
          "title": string,
          "date": string,   // YYYY or YYYY-MM-DD
          "themes": [string],
          "sentiment_score": float   // -1.0 to 1.0
        }}
      ],
      "number_of_employees_estimated": {{
        "range": string,
        "source": string or null,
        "alternate_estimate": int or null,
        "source_alternate": string or null
      }},
      "keywords_associated": [string],
      "notable_portfolio": [string],
      "contact": {{
        "address": string or null
      }}
    }}

    Rules:
    - Populate fields with the best available public info.
    - Use null when no information is available, do not invent.
    - Dates should be ISO-like strings (YYYY or YYYY-MM-DD).
    - sentiment_score must be numeric between -1.0 and +1.0.
    - Return only the JSON object, no explanation or extra text.
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
    company_results[company['ENTITY_ID']] = json_output

# Convert dict → DataFrame
df = pd.DataFrame([
    {"ENTITY_ID": k, "BASIC_PROFILE": v}  # stringify the value
    for k, v in company_results.items()
])
df['UPDATE_TS'] = dt.datetime.now(dt.timezone.utc)

# upsert to Snowflake
upsert_to_snowflake(df, table_name='COMPANIES', key_columns=['ENTITY_ID'], database='RDH', schema='PUBLIC')

