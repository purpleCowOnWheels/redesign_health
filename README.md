This is a library used for creating and augmenting a knowledge graph for Resdesign Health data.

There are two critical scripts:
1. main.py runs the user interface for querying the graph (calling the underlying script question_answer.py)
2. ingest_artifacts reads artifacts from a local folder and adds relevant information from them to the graph

Critical helper scripts:
1. entity_fns contains helper functions relating to entities, particularly entity resolution
2. snowflake_utils are simple wrappers of functions for querying snowflake data. This should be separated into a class for a snowflake connector in the future

Optional / less critical:
entity_metadata gets public information on entities from ChatGPT. This has NOT been a reliable source of information and should be replaced by creating node-level data that just summarizes information available in the eisting knowledge graph
ingest_entities allows for manual creation of entities in the knowledge graph (with appropriate resolution against existing entities)
