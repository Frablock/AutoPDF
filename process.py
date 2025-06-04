# Imports des libs
import markdown
import os 
import dotenv

import os
from mistralai import Mistral

from preprompt import PREPROMPT

from langchain_community.tools import DuckDuckGoSearchRun

from md2pdf.core import md2pdf

import re

from time import sleep

search = DuckDuckGoSearchRun()


# Constantes
## sujet
SUBJECT = "Conquête Spaciale du point de vue soviétique"
## Chargement de l'environnement
ENV = dotenv.dotenv_values(".env")
## Chargement clé API Mistral
API_KEY = ENV.get("MISTRAL_API_KEY" , "PAS DE CLÉ")
## Client Mistral
CLIENT = Mistral(api_key=API_KEY)
## Modèle Mistral
MODEL = "mistral-large-latest"
## Nom d'auteur
AUTHOR = ENV.get("AUTHOR_NAME", "")

def generer_contenu(prompt: str) -> str:
    """Génération de contenu via Mistral"""
    response = CLIENT.chat.complete(
        model=MODEL,
        messages=[{"role": "system", "content": prompt}]
    )
    return response.choices[0].message.content

def generer_plan():
    prompt = PREPROMPT["plan"].replace("[@SUBJECT@]", SUBJECT)
    prompt = prompt.replace("[@SOURCES@]", SOURCES)
    return generer_contenu(prompt)

def generer_redaction(partie, all_parts_except):
    prompt = PREPROMPT["redaction"].replace("[@SUBJECT@]", SUBJECT)
    prompt = prompt.replace("[@NOT_CURRENT_CHAPTER@]", all_parts_except)
    prompt = prompt.replace("[@CURRENT_CHAPTER@]", partie)
    prompt = prompt.replace("[@SOURCES@]", SOURCES)
    return generer_contenu(prompt)

def generer_redac_correct(partie, all_parts_except, text):
    prompt = PREPROMPT["redaction_after_correction"].replace("[@SUBJECT@]", SUBJECT)
    prompt = prompt.replace("[@NOT_CURRENT_CHAPTER@]", all_parts_except)
    prompt = prompt.replace("[@CURRENT_CHAPTER@]", partie)
    prompt = prompt.replace("[@SOURCES@]", SOURCES)
    
    response = CLIENT.chat.complete(
        model=MODEL,
        messages=[{"role": "system", "content": prompt},
        {"role":"user", "content":remove_think_tags(text)}]
    )
    return response.choices[0].message.content

def generer_correction(partie, all_parts_except, text):
    prompt = PREPROMPT["corrector"].replace("[@SUBJECT@]", SUBJECT)
    prompt = prompt.replace("[@NOT_CURRENT_CHAPTER@]", all_parts_except)
    prompt = prompt.replace("[@CURRENT_CHAPTER@]", partie)
    prompt = prompt.replace("[@SOURCES@]", SOURCES)

    response = CLIENT.chat.complete(
        model=MODEL,
        messages=[{"role": "system", "content": prompt},
        {"role":"user", "content":remove_think_tags(text)}]
    )
    return response.choices[0].message.content

def remove_think_tags(text):
    # Use regular expression to remove <think> and </think> tags and the text in between
    return text.split("</think>")[-1]

# Nombre max de corrections
MAX_CORR = 2

SOURCES = search.invoke(SUBJECT)
parties = []
plan = remove_think_tags(generer_plan())
print(plan)
plan = plan.split("\n")
plan = [string for string in plan if string != ""]
print(plan)


try:
    for i, partie in enumerate(plan):
        print("> "+partie)

        if ("[IMAGE" in partie or "[VIDEO" in partie or "[SCHEMA" in partie):
            parties.append("")
            continue

        all_parts_except = ", ".join([partie if j != partie else "" for j in plan])

        redaction = generer_redaction(partie, all_parts_except)
        correction = generer_correction(partie, all_parts_except, redaction)
        corr_count = 1
        while "CONTIENT_FAUTES=TRUE" in correction and MAX_CORR > corr_count:
            print(redaction, correction)
            redaction = generer_redac_correct(partie, all_parts_except, correction)
            if not MAX_CORR >= corr_count:
                correction = generer_correction(partie, all_parts_except, redaction)
            corr_count += 1
            sleep(20)
        parties.append(remove_think_tags(redaction))
        print(redaction)
        with open("./cache/"+ partie +".md", 'w') as file:
            file.write(remove_think_tags(redaction))
        
        sleep(60) # On ralentit un peu pour limiter la rates de Token par minutes

    markdown_output = ""
    for i, titre in enumerate(plan):
        markdown_output += "# "+ titre + "\n" + parties[i]
    print(markdown_output)

    with open("./out.md", 'w') as file:
            file.write(markdown_output)

    md2pdf("./out.pdf",
        raw=markdown_output
    )
except Exception as e:
    markdown_output = ""
    markdown_output.join(parties)

    with open("./unfinished.md", 'w') as file:
            file.write(markdown_output)

    md2pdf("./unfinished.pdf",
        raw=markdown_output
    )
