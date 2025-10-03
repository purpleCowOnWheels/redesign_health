import json, pdb
import pandas as pd
from entity_fns import resolve_entity

companies_path = r'C:\Users\danie\Downloads\LinkedIn_company_information.json'
with open(companies_path, 'r', encoding='utf-8') as f:
    companies = json.load(f)

entities = [ ]
for indx, company in enumerate(companies):
    print(str(indx))
    this_entity = { 'website': company['website'],
                    'name': company['name'],
                    'linkedin_url': company['url'],
                   }
    entity_resolved = resolve_entity( this_entity, entities)

    if( entity_resolved['is_new'] ):
        this_entity['entity_id'] = entity_resolved['entity_id']
        entities.append(this_entity)
        print('Added new entity')
    else:
        #TODO: if the entity exists, update it to ensure it has company as an entity type
        print('Found existing entity')
new_entities = pd.DataFrame(entities)
new_entities.to_csv(r'C:\Users\danie\Dropbox\Personal\Jobs\Company Specific Docs\Redesign_Health\new_entities\new_entities.csv')

