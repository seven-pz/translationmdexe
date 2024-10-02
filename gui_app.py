import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QTextEdit, QFileDialog, QLabel
from PyQt5.QtCore import Qt
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import re

class TranslationApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        
        # Charger le tokenizer et le modèle de traduction
        self.tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-fr-en")
        self.model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-fr-en")

    def initUI(self):
        layout = QVBoxLayout()

        self.label = QLabel("Sélectionnez un fichier .md à traduire:")
        layout.addWidget(self.label)

        self.btn_select = QPushButton('Sélectionner un fichier', self)
        self.btn_select.clicked.connect(self.select_file)
        layout.addWidget(self.btn_select)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)

        self.btn_translate = QPushButton('Traduire', self)
        self.btn_translate.clicked.connect(self.translate_file)
        layout.addWidget(self.btn_translate)

        self.setLayout(layout)
        self.setGeometry(300, 300, 500, 400)
        self.setWindowTitle('Traducteur de Markdown')
        self.show()

    def select_file(self):
        fname = QFileDialog.getOpenFileName(self, 'Ouvrir un fichier', '', 'Markdown Files (*.md)')
        if fname[0]:
            with open(fname[0], 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_edit.setText(content)
            self.selected_file = fname[0]

    def translate(self, text: str) -> str:
        inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        outputs = self.model.generate(**inputs, max_length=512, num_beams=5, early_stopping=True)
        translated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return translated_text

    def extract_paths(self, text: str) -> (str, list):
        path_pattern = re.compile(r'\[.*?\]\(.*?\.(?:jpg|png|html|pdf)(?:#.*?)?\)')
        paths = path_pattern.findall(text)
        placeholder_text = path_pattern.sub('FILE_PLACEHOLDER', text)
        return placeholder_text, paths

    def replace_paths(self, text: str, paths: list) -> str:
        for path in paths:
            text = text.replace('FILE_PLACEHOLDER', path, 1)
        return text

    def translate_file(self):
        if hasattr(self, 'selected_file'):
            with open(self.selected_file, 'r', encoding='utf-8') as f:
                markdown_text = f.read()
            
            translated_lines = []
            for line in markdown_text.split('\n'):
                if not line.strip():
                    translated_lines.append('')  # Conserver les lignes vides
                else:
                    placeholder_text, paths = self.extract_paths(line)
                    if paths:
                        translated_text = self.translate(placeholder_text.strip())
                        translated_line = self.replace_paths(translated_text, paths)
                        translated_lines.append(translated_line)
                    else:
                        translated_lines.append(self.translate(line.strip()))
            
            translated_content = '\n'.join(translated_lines)
            self.text_edit.setText(translated_content)
            
            # Sauvegarder le fichier traduit
            base_name = os.path.splitext(self.selected_file)[0]
            translated_file = f"{base_name}_translated.md"
            with open(translated_file, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            
            self.label.setText(f"Traduction sauvegardée dans : {translated_file}")
        else:
            self.label.setText("Veuillez d'abord sélectionner un fichier.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TranslationApp()
    sys.exit(app.exec_())