from openai import OpenAI
from dotenv import load_dotenv
import os, uuid, datetime as dt
import requests
from bs4 import BeautifulSoup
import trafilatura

load_dotenv()

client = OpenAI(api_key=os.getenv('OPEN_AI_API_KEY'))
model = os.getenv("OPENAI_MODEL", "gpt-4.1")  # set to a model you have access to

urls =  [
"https://www.findanomaly.com",
"https://www.batonhealth.com",
"https://beanstalkbenefits.com",
"https://www.joincalibrate.com",
"https://www.cardioone.com",
"https://cascalahealth.com",
"https://www.getduos.com",
"https://www.everbody.com",
"https://eversethealth.com",
"https://www.forthealth.com",
"https://glimmer-health.com",
"https://www.harmonichealth.com",
"https://wearehelpful.com",
"https://www.huddlepediatrics.com",
"https://www.intrinsic.us",
"https://www.tryiolite.com",
"https://www.ironhealth.io",
"https://www.hellojasper.com",
"https://www.choosekeen.com",
"https://www.kins.com",
"https://www.latitudehealth.com",
"https://www.lineacare.com",
"https://www.jabraenhance.com",
"https://www.medarrive.com",
"https://withmotiv.com",
"https://www.nomatherapy.com",
"https://getoveralls.com",
"https://www.pipcare.com",
"https://www.primum.co",
"https://scriptologyhealth.com",
"https://www.shakeiq.ai",
"https://www.sidebycare.com",
"https://www.sounderbenefits.com",
"https://www.soundryhealth.com",
"https://www.corticacare.com",
"https://www.getsteadywell.com",
"https://stitchpeo.com",
"https://www.meetsyntax.com",
"https://thrivory.com",
"https://www.togetherseniorhealth.com",
"https://jointownsquare.com",
"https://www.trampolineai.com",
"https://www.translucent.co",
"https://troupehealth.com",
"https://www.joinuplift.co",
"https://www.uptivhealth.com",
"https://www.vaulthealth.com",
"https://vedatrials.com",
"https://www.vitalichealth.co",
"https://www.meetvividhealth.com",
    'https://aronszanto.com/'
]

def fetch_page_text(url):
    resp = requests.get(url, timeout=10)
    html = resp.text
    text = trafilatura.extract(html) or BeautifulSoup(html, "html.parser").get_text()

    try:
        resp = requests.get(url + '/about-us', timeout=10)
        html = resp.text
        about_us = trafilatura.extract(html) or BeautifulSoup(html, "html.parser").get_text()
    except:
        about_us = ''
        print( '< About us not found >')
    return text + '\n' + about_us

for indx, url in enumerate(urls):
        print(f'Creating artifact for url {indx} of {len(urls)}')

        print('  >> Fetching page text...')
        page_text = fetch_page_text(url)

        print('  >> Getting GPT entity summary...')
        prompt = f"""
        - Identify the entity that this website represents:
        ++++++++++++++++++++++
        {page_text}
        ++++++++++++++++++++++
        - The entity's website is {url}. You can use this to find its Wikipedia page.
        - Once you have identified the entity, summarize its public information using information in the text provided, and other public information about the entity including its wikipedia page, its linkedin page, its news articles, its patents, etc.
        - Output strictly in JSON with this schema:

        {{
        "entity_type": string, -> prefer "company" or "person" or "school" or "investment_fund" or "investment_manager" if applicable
          "metadata": {{
            "full_name": string,
            "known_as": string or null,
            "website": string,
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
        - Use all readable sections of the website.
        - Also include any relevant information that can be found on LinkedIn, Wikipedia, news articles, patents or any other public sources.
        - Populate fields with the best available public info.
        - Use null when no information is available, do not invent.
        - Dates should be ISO-like strings (YYYY or YYYY-MM-DD).
        - sentiment_score must be numeric between -1.0 and +1.0.
        - Return only the JSON object, no explanation or extra text.
        """

        prompt_sent = dt.datetime.now()
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},  # or json_schema (best)
            messages=[
                {"role": "system", "content": "Return only valid JSON. Please validate it. No prose, no markdown."},
                {"role": "user", "content": prompt}
            ],
            seed=1,
            n=1
        )

        print('  >> GPT executed in :' + str(dt.datetime.now() - prompt_sent))

        raw_text = response.choices[0].message.content
        file_path = rf"C:\Users\danie\Dropbox\Personal\Jobs\Company Specific Docs\Redesign_Health\artifacts\new_artifacts\entities_{uuid.uuid4()}.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(raw_text)

        print(f"Saved successfully to: {file_path}")