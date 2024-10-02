from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import os
import re

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Charger le tokenizer et le modèle de traduction
tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-fr-en")
model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-fr-en")

def translate(text: str) -> str:
    """Fonction pour traduire du français vers l'anglais."""
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    outputs = model.generate(**inputs, max_length=512, num_beams=5, early_stopping=True)
    translated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return translated_text

def extract_paths(text: str) -> (str, list):
    """Extrait les chemins d'image et de fichiers du texte et les remplace par des tokens."""
    path_pattern = re.compile(r'\[.*?\]\(.*?\.(?:jpg|png|html|pdf)(?:#.*?)?\)')
    paths = path_pattern.findall(text)
    placeholder_text = path_pattern.sub('FILE_PLACEHOLDER', text)
    return placeholder_text, paths

def replace_paths(text: str, paths: list) -> str:
    """Remplace les tokens par les chemins d'image et de fichiers originaux."""
    for path in paths:
        text = text.replace('FILE_PLACEHOLDER', path, 1)
    return text

@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request):
    """Route pour afficher le formulaire de soumission du document."""
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/translate", response_class=HTMLResponse)
async def translate_doc(request: Request, file: UploadFile = File(...)):
    """Route pour traduire le document téléchargé et afficher les résultats."""
    content = await file.read()
    markdown_text = content.decode("utf-8")
    translated_lines = []

    for line in markdown_text.split('\n'):
        if not line.strip():
            translated_lines.append('')  # Conserver les lignes vides
        else:
            placeholder_text, paths = extract_paths(line)
            if paths:
                translated_text = translate(placeholder_text.strip())
                translated_line = replace_paths(translated_text, paths)
                translated_lines.append(translated_line)
            else:
                translated_lines.append(translate(line.strip()))

    # Générer le nom du fichier traduit
    original_filename = file.filename
    translated_filename = os.path.splitext(original_filename)[0] + "_translated.md"

    # Sauvegarde du document traduit pour le téléchargement
    with open(translated_filename, "w", encoding="utf-8") as f:
        f.write('\n'.join(translated_lines))

    return templates.TemplateResponse("translated.html", {
        "request": request,
        "translated_paragraphs": translated_lines,
        "translated_document_path": translated_filename
    })

@app.get("/download/{filename}", response_class=FileResponse)
async def download_translated(filename: str):
    """Route pour télécharger le document traduit."""
    file_path = filename
    return FileResponse(path=file_path, filename=file_path, media_type='text/markdown')
