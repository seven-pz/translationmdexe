# Standard library imports
import sys
import os
import time
import re
from datetime import datetime
import logging

# Third party imports
from PyQt5.QtWidgets import (
    QApplication, 
    QWidget, 
    QPushButton, 
    QVBoxLayout, 
    QHBoxLayout, 
    QTextEdit, 
    QFileDialog, 
    QLabel, 
    QComboBox, 
    QProgressBar, 
    QLineEdit, 
    QMessageBox, 
    QFrame
)
from PyQt5.QtCore import (
    Qt, 
    QThread, 
    pyqtSignal, 
    QSize, 
    QEvent
)
from PyQt5.QtGui import (
    QIcon, 
    QFont, 
    QColor, 
    QPalette
)
from transformers import (
    AutoTokenizer, 
    AutoModelForSeq2SeqLM
)
import torch

# Local application imports
from credential_manager import CredentialManager
from machine_lock import MachineLock
from docx_translator import DocxTranslator
from translation_database import TranslationDatabaseManager
from enhanced_gui import EnhancedTranslationApp


VERSION = "2.0.0"
APP_NAME = "SecuredTrad"
ICON_PATH = "icone.jpg"

class StyleManager:
    @staticmethod
    def apply_style(app):
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(palette)

        app.setStyleSheet("""
        QWidget {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
        }
        QPushButton {
            background-color: #2a82da;
            color: white;
            border: none;
            padding: 8px 15px;
            text-align: center;
            font-size: 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #3a92ea;
        }
        QLineEdit, QTextEdit {
            border: 1px solid #3a92ea;
            border-radius: 4px;
            padding: 5px;
            background-color: #2a2a2a;
            font-size: 15px;
        }
        QComboBox {
            border: 1px solid #3a92ea;
            border-radius: 4px;
            padding: 5px;
            background-color: #2a2a2a;
            font-size: 15px;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 15px;
            border-left-width: 1px;
            border-left-color: #3a92ea;
            border-left-style: solid;
        }
        QComboBox::down-arrow {
            image: url(down_arrow.png);
        }
        QComboBox QAbstractItemView {
            border: 1px solid #3a92ea;
            background-color: #2a2a2a;
            selection-background-color: #3a92ea;
        }
        QComboBox QAbstractItemView::item {
            padding: 5px;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: #3a92ea;
            color: white;
        }
        QProgressBar {
            border: 2px solid #3a92ea;
            border-radius: 5px;
            text-align: center;
            font-size: 14px;
            color: white;
            background-color: #2a2a2a;
        }
        QProgressBar::chunk {
            background-color: #2a82da;
            width: 10px;
            margin: 0.5px;
        }
        QLabel {
            font-size: 15px;
        }
        """)



class TranslationManager:
    def __init__(self):
        """
        Initialise le gestionnaire de traduction avec les modèles et la base de données.
        """
        self.models = {}
        self.tokenizers = {}
        self.db_manager = TranslationDatabaseManager()
        
        # Configuration du logging
        logging.basicConfig(
            filename='translation_manager.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Définition des paires de langues supportées
        self.supported_pairs = {
            "fr-en": "Helsinki-NLP/opus-mt-fr-en",
            "en-fr": "Helsinki-NLP/opus-mt-en-fr",
            "en-es": "Helsinki-NLP/opus-mt-en-es",
            "es-en": "Helsinki-NLP/opus-mt-es-en"
        }
        
        # Configuration des paramètres de traduction
        self.translation_config = {
            'max_length': 512,
            'num_beams': 5,
            'length_penalty': 1.0,
            'early_stopping': True
        }

    def load_model(self, lang_pair):
        """
        Charge un modèle de traduction pour une paire de langues spécifique.
        """
        try:
            if lang_pair not in self.models:
                if lang_pair not in self.supported_pairs:
                    raise ValueError(f"Paire de langues non supportée : {lang_pair}")
                
                model_name = self.supported_pairs[lang_pair]
                logging.info(f"Chargement du modèle pour {lang_pair}: {model_name}")
                
                self.tokenizers[lang_pair] = AutoTokenizer.from_pretrained(model_name)
                self.models[lang_pair] = AutoModelForSeq2SeqLM.from_pretrained(model_name)
                
                # Passage du modèle en mode évaluation
                self.models[lang_pair].eval()
                
                # Utilisation du GPU si disponible
                if torch.cuda.is_available():
                    self.models[lang_pair].to('cuda')
                    logging.info(f"Modèle {lang_pair} chargé sur GPU")
                else:
                    logging.info(f"Modèle {lang_pair} chargé sur CPU")
                
        except Exception as e:
            logging.error(f"Erreur lors du chargement du modèle {lang_pair}: {str(e)}")
            raise

    def translate_segment(self, text, lang_pair):
        """
        Traduit un segment de texte individuel.
        """
        try:
            # Nettoyage du texte d'entrée
            text = text.strip()
            if not text or all(not c.isalnum() for c in text):
                return text
            
            # Chargement du modèle si nécessaire
            self.load_model(lang_pair)
            
            # Tokenization avec gestion de la longueur maximale
            inputs = self.tokenizers[lang_pair](
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.translation_config['max_length']
            )
            
            # Déplacement des tenseurs sur GPU si disponible
            if torch.cuda.is_available():
                inputs = {k: v.to('cuda') for k, v in inputs.items()}
            
            # Génération de la traduction
            with torch.no_grad():
                outputs = self.models[lang_pair].generate(
                    **inputs,
                    max_length=self.translation_config['max_length'],
                    num_beams=self.translation_config['num_beams'],
                    length_penalty=self.translation_config['length_penalty'],
                    early_stopping=self.translation_config['early_stopping']
                )
            
            # Décodage de la sortie
            translated_text = self.tokenizers[lang_pair].decode(
                outputs[0],
                skip_special_tokens=True
            )
            
            # Nettoyage post-traduction
            translated_text = self.clean_translation(translated_text)
            
            return translated_text.strip()
            
        except Exception as e:
            logging.error(f"Erreur lors de la traduction du segment: {str(e)}")
            raise

    def clean_translation(self, text):
        """
        Nettoie une traduction des artéfacts courants.
        """
        # Suppression des "I'm sorry" et variantes
        text = re.sub(r"I'm sorry,?\s*", "", text)
        text = re.sub(r"I apologize,?\s*", "", text)
        
        # Nettoyage des espaces multiples
        text = re.sub(r'\s+', ' ', text)
        
        # Correction de la ponctuation
        text = re.sub(r'\s+([.,!?])', r'\1', text)
        
        return text.strip()

    def translate_document(self, file_path, content, lang_pair, progress_callback=None):
        """
        Traduit un document complet avec gestion de la mémoire de traduction.
        """
        try:
            # Stockage du document
            doc_id, exists = self.db_manager.store_document(
                file_path,
                content,
                file_type=file_path.split('.')[-1]
            )
            
            # Vérification des traductions existantes
            if exists:
                existing_translation = self.check_existing_translation(doc_id, lang_pair)
                if existing_translation:
                    logging.info(f"Traduction existante trouvée pour {file_path}")
                    return existing_translation
            
            # Recherche de documents similaires
            similar_docs = self.db_manager.find_similar_documents(content)
            
            # Segmentation du contenu
            segments = self.db_manager.split_into_segments(content)
            total_segments = len(segments)
            translated_segments = []
            
            for i, segment in enumerate(segments):
                # Mise à jour de la progression
                if progress_callback:
                    progress = int((i + 1) * 100 / total_segments)
                    progress_callback(progress)
                
                # Recherche de segments similaires
                matches = self.db_manager.find_matching_segments(segment, lang_pair)
                
                if matches and matches[0]['similarity'] > 0.95:
                    # Réutilisation d'une traduction existante
                    translated_segments.append(matches[0]['translated'])
                    logging.info(f"Segment réutilisé avec similarité {matches[0]['similarity']}")
                else:
                    # Nouvelle traduction
                    translated = self.translate_segment(segment, lang_pair)
                    translated_segments.append(translated)
            
            # Assemblage de la traduction complète
            translated_content = '\n'.join(translated_segments)
            
            # Stockage de la traduction
            self.db_manager.store_translation(
                doc_id,
                lang_pair,
                translated_content,
                list(zip(segments, translated_segments))
            )
            
            logging.info(f"Document traduit avec succès: {file_path}")
            return translated_content
            
        except Exception as e:
            logging.error(f"Erreur lors de la traduction du document: {str(e)}")
            raise

    def check_existing_translation(self, doc_id, lang_pair):
        """
        Vérifie si une traduction existe déjà pour le document.
        """
        try:
            history = self.db_manager.get_document_history(doc_id)
            if history:
                for entry in history:
                    if entry['lang_pair'] == lang_pair:
                        # Vérifier si la traduction est récente (moins de 24h)
                        translation_date = datetime.fromisoformat(entry['translation_date'])
                        if (datetime.now() - translation_date).days < 1:
                            return entry['translated_content']
            return None
            
        except Exception as e:
            logging.error(f"Erreur lors de la vérification des traductions existantes: {str(e)}")
            return None

    def translate_text(self, text, lang_pair):
        """
        Traduit un texte simple sans stockage en base de données.
        """
        try:
            if not text.strip():
                return text
                
            # Vérifier si le texte nécessite une segmentation
            if len(text) > self.translation_config['max_length']:
                segments = self.db_manager.split_into_segments(text)
                translated_segments = [
                    self.translate_segment(segment, lang_pair)
                    for segment in segments
                ]
                return '\n'.join(translated_segments)
            else:
                return self.translate_segment(text, lang_pair)
                
        except Exception as e:
            logging.error(f"Erreur lors de la traduction du texte: {str(e)}")
            raise

    def get_model_name(self, lang_pair):
        """
        Retourne le nom du modèle pour une paire de langues.
        """
        return self.supported_pairs.get(lang_pair)

    def get_supported_languages(self):
        """
        Retourne la liste des paires de langues supportées.
        """
        return list(self.supported_pairs.keys())

    def cleanup(self):
        """
        Nettoie les ressources utilisées par le gestionnaire.
        """
        try:
            # Libération de la mémoire GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Fermeture de la base de données
            self.db_manager.close()
            
            # Suppression des références aux modèles
            self.models.clear()
            self.tokenizers.clear()
            
            logging.info("Nettoyage des ressources effectué avec succès")
            
        except Exception as e:
            logging.error(f"Erreur lors du nettoyage des ressources: {str(e)}")

class LoadingThread(QThread):
    finished = pyqtSignal()

    def run(self):
        time.sleep(3)
        self.finished.emit()

class LoginWindow(QWidget):
    def __init__(self, cred_manager, machine_lock):
        super().__init__()
        self.cred_manager = cred_manager
        self.machine_lock = machine_lock
        self.initUI()
        self.setWindowIcon(QIcon(ICON_PATH))
        self.check_machine_lock()

    def initUI(self):
        layout = QVBoxLayout()

        title_label = QLabel(f"{APP_NAME} - Connexion")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        layout.addWidget(title_label)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nom d'utilisateur")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Mot de passe")
        self.password_input.setEchoMode(QLineEdit.Password)
        
        self.auth_code_input = QLineEdit()
        self.auth_code_input.setPlaceholderText("Code d'autorisation")
        self.auth_code_input.hide()  # Caché par défaut

        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.auth_code_input)

        self.login_button = QPushButton('Se connecter')
        self.login_button.clicked.connect(self.login)
        layout.addWidget(self.login_button)

        self.setLayout(layout)
        self.setWindowTitle(f'{APP_NAME} - Connexion')
        self.setGeometry(300, 300, 300, 200)

    def check_machine_lock(self):
        if not self.machine_lock.check_lock():
            reply = QMessageBox.question(self, 'Nouvelle machine', 
                                         "C'est la première fois que l'application est lancée sur cette machine. Voulez-vous l'installer ici ?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                self.auth_code_input.show()
                self.login_button.setText("Installer et se connecter")
                QMessageBox.information(self, 'Code d autorisation requis', 
                                        "Veuillez entrer le code d'autorisation fourni pour installer l'application sur cette machine.")
            else:
                QMessageBox.warning(self, 'Installation annulée', "L'application ne peut pas être utilisée sans installation.")
                self.close()

    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        auth_code = self.auth_code_input.text()

        if self.auth_code_input.isVisible():
            if not self.machine_lock.install_on_new_machine(auth_code):
                QMessageBox.critical(self, 'Erreur', "Code d'autorisation invalide. Installation impossible.")
                return
            else:
                QMessageBox.information(self, 'Succès', "L'application a été installée avec succès sur cette machine.")
                self.auth_code_input.hide()
                self.login_button.setText("Se connecter")

        success, days_left, license_type = self.cred_manager.check_credentials(username, password)
        
        if success:
            self.loading_thread = LoadingThread()
            self.loading_thread.finished.connect(lambda: self.on_loaded(days_left, license_type))
            self.loading_thread.start()
        else:
            QMessageBox.warning(self, 'Erreur', 'Identifiants incorrects ou licence expirée')

    def on_loaded(self, days_left, license_type):
        self.main_app = EnhancedTranslationApp(days_left, license_type)
        self.main_app.show()
        self.close()

class TranslationApp(QWidget):
    def __init__(self, days_left, license_type="standard"):
        super().__init__()
        self.days_left = days_left
        self.license_type = license_type
        self.translation_manager = TranslationManager()
        self.docx_translator = DocxTranslator(self.translation_manager)
        self.MAX_CHARS = 500
        self.initUI()
        self.setWindowIcon(QIcon(ICON_PATH))

    def initUI(self):
        main_layout = QHBoxLayout()
        
        # Partie gauche pour la traduction de fichiers
        left_layout = QVBoxLayout()

        self.label = QLabel(f"Licence {self.license_type} valide pour {self.days_left} jours")
        self.label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.label)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Français vers Anglais", "Anglais vers Français", "Anglais vers Espagnol", "Espagnol vers Anglais"])
        left_layout.addWidget(self.lang_combo)

        self.btn_select = QPushButton('Sélectionner un fichier', self)
        self.btn_select.clicked.connect(self.select_file)
        left_layout.addWidget(self.btn_select)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        left_layout.addWidget(self.text_edit)

        self.btn_translate = QPushButton('Traduire', self)
        self.btn_translate.clicked.connect(self.translate_file)
        left_layout.addWidget(self.btn_translate)

        self.progress_bar = QProgressBar()
        left_layout.addWidget(self.progress_bar)

        # Partie droite pour la traduction en direct
        right_layout = QVBoxLayout()
        
        right_layout.addWidget(QLabel("Traduction en direct"))
        
        self.live_lang_combo = QComboBox()
        self.live_lang_combo.addItems(["Français vers Anglais", "Anglais vers Français", "Anglais vers Espagnol", "Espagnol vers Anglais"])
        right_layout.addWidget(self.live_lang_combo)
        
        self.live_input = QTextEdit()
        self.live_input.setPlaceholderText("Entrez le texte à traduire ici...")
        self.live_input.textChanged.connect(self.update_char_count)
        self.live_input.installEventFilter(self)
        right_layout.addWidget(self.live_input)
        
        self.char_count_label = QLabel(f"0 / {self.MAX_CHARS} caractères")
        self.char_count_label.setAlignment(Qt.AlignRight)
        right_layout.addWidget(self.char_count_label)
        
        self.live_output = QTextEdit()
        self.live_output.setReadOnly(True)
        self.live_output.setPlaceholderText("La traduction apparaîtra ici...")
        right_layout.addWidget(self.live_output)
        
        self.btn_live_translate = QPushButton('Traduire', self)
        self.btn_live_translate.clicked.connect(self.translate_live)
        right_layout.addWidget(self.btn_live_translate)

        # Ajout des layouts gauche et droit au layout principal
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        # Layout du bas pour le copyright et la version
        bottom_layout = QHBoxLayout()
        copyright_label = QLabel("© sevenlemonnier7@gmail.com")
        bottom_layout.addWidget(copyright_label)
        bottom_layout.addStretch()
        version_label = QLabel(f"Version {VERSION}")
        version_label.setAlignment(Qt.AlignRight)
        bottom_layout.addWidget(version_label)

        # Layout final
        final_layout = QVBoxLayout()
        final_layout.addLayout(main_layout)
        final_layout.addWidget(QFrame(frameShape=QFrame.HLine))
        final_layout.addLayout(bottom_layout)

        self.setLayout(final_layout)
        self.setGeometry(100, 100, 1000, 600)
        self.setWindowTitle(f'{APP_NAME} - Traducteur')

    def select_file(self):
        fname = QFileDialog.getOpenFileName(
            self, 
            'Ouvrir un fichier', 
            '', 
            'Documents (*.md *.docx)'
        )
        if fname[0]:
            self.selected_file = fname[0]
            if fname[0].endswith('.md'):
                with open(fname[0], 'r', encoding='utf-8') as f:
                    content = f.read()
                self.text_edit.setText(content)
            elif fname[0].endswith('.docx'):
                self.text_edit.setText(f"Document Word sélectionné : {os.path.basename(fname[0])}")

    def get_lang_pair(self, combo):
        index = combo.currentIndex()
        pairs = ["fr-en", "en-fr", "en-es", "es-en"]
        return pairs[index]

    def translate_markdown_file(self, lang_pair):
        """Gère la traduction des fichiers Markdown."""
        with open(self.selected_file, 'r', encoding='utf-8') as f:
            markdown_text = f.read()
        
        lines = markdown_text.split('\n')
        translated_lines = []
        self.progress_bar.setMaximum(len(lines))
        
        image_pattern = r'(!\[.*?\]\(.*?\))'
        table_header_pattern = r'^\s*\|.*\|\s*$'
        table_separator_pattern = r'^\s*\|[\s\-:]+\|\s*$'
        code_block_pattern = r'^```'
        
        in_table = False
        in_code_block = False
        table_headers = []
        
        for i, line in enumerate(lines):
            # Gestion des blocs de code
            if re.match(code_block_pattern, line):
                in_code_block = not in_code_block
                translated_lines.append(line)
                continue
                
            if in_code_block:
                translated_lines.append(line)  # Ne pas traduire le code
                continue

            # Gestion des tableaux
            if re.match(table_header_pattern, line):
                in_table = True
                table_headers = [cell.strip() for cell in line.split('|')[1:-1]]
                translated_headers = [self.translation_manager.translate(header, lang_pair) 
                                   for header in table_headers if header]
                translated_line = '| ' + ' | '.join(translated_headers) + ' |'
                translated_lines.append(translated_line)
            elif re.match(table_separator_pattern, line):
                translated_lines.append(line)  # Garder la ligne de séparation telle quelle
            elif in_table and line.strip().startswith('|') and line.strip().endswith('|'):
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                translated_cells = [self.translation_manager.translate(cell, lang_pair) 
                                  if cell else '' for cell in cells]
                translated_line = '| ' + ' | '.join(translated_cells) + ' |'
                translated_lines.append(translated_line)
            else:
                in_table = False
                if line.strip():
                    # Gestion des titres et listes
                    if line.startswith(('#', '-', '*', '>')):
                        indent = re.match(r'^[#\-*> ]+', line).group()
                        content = line[len(indent):]
                        translated_text = self.translation_manager.translate(content.strip(), lang_pair)
                        translated_line = indent + translated_text
                        translated_lines.append(translated_line)
                    else:
                        # Gestion des images et du texte normal
                        parts = re.split(image_pattern, line)
                        translated_parts = []
                        for part in parts:
                            if re.match(image_pattern, part):
                                translated_parts.append(part)
                            elif part.strip():
                                translated_text = self.translation_manager.translate(part.strip(), lang_pair)
                                translated_parts.append(translated_text)
                            else:
                                translated_parts.append(part)
                        translated_line = ''.join(translated_parts)
                        translated_lines.append(translated_line)
                else:
                    translated_lines.append('')
            
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()
        
        translated_content = '\n'.join(translated_lines)
        self.text_edit.setText(translated_content)
        
        base_name = os.path.splitext(self.selected_file)[0]
        translated_file = f"{base_name}_translated.md"
        with open(translated_file, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        
        self.label.setText(f"Traduction sauvegardée dans : {translated_file}")
        return translated_file

    def translate_file(self):
        """Fonction principale de traduction qui gère tous les types de fichiers."""
        if not hasattr(self, 'selected_file'):
            self.label.setText("Veuillez d'abord sélectionner un fichier.")
            return

        try:
            lang_pair = self.get_lang_pair(self.lang_combo)
            file_extension = os.path.splitext(self.selected_file)[1].lower()
            
            # Réinitialiser la barre de progression
            self.progress_bar.setValue(0)
            
            # Gérer les différents types de fichiers
            if file_extension == '.md':
                translated_file = self.translate_markdown_file(lang_pair)
                success_message = f"Fichier Markdown traduit avec succès :\n{translated_file}"
            elif file_extension == '.docx':
                translated_file = self.docx_translator.translate_docx(
                    self.selected_file,
                    lang_pair,
                    progress_callback=lambda value: (
                        self.progress_bar.setValue(value),
                        QApplication.processEvents()
                    )
                )
                success_message = f"Document Word traduit avec succès :\n{translated_file}"
            else:
                QMessageBox.warning(self, 'Format non supporté',
                                  f"Le format de fichier {file_extension} n'est pas supporté.")
                return

            # Afficher un message de succès
            QMessageBox.information(self, 'Traduction terminée', success_message)
            self.label.setText(f"Traduction sauvegardée dans : {translated_file}")
            
        except Exception as e:
            QMessageBox.critical(self, 'Erreur',
                               f"Une erreur est survenue lors de la traduction :\n{str(e)}")
            logging.error(f"Erreur de traduction: {str(e)}", exc_info=True)

    def translate_file(self):
        """Fonction principale de traduction qui gère tous les types de fichiers."""
        if not hasattr(self, 'selected_file'):
            self.label.setText("Veuillez d'abord sélectionner un fichier.")
            return

        try:
            lang_pair = self.get_lang_pair(self.lang_combo)
            file_extension = os.path.splitext(self.selected_file)[1].lower()
        
            # Réinitialiser la barre de progression
            self.progress_bar.setValue(0)
        
            # Gérer les différents types de fichiers
            if file_extension == '.md':
                translated_file = self.translate_markdown_file(lang_pair)
                success_message = f"Fichier Markdown traduit avec succès :\n{translated_file}"
            elif file_extension == '.docx':
                translated_file = self.docx_translator.translate_docx(
                    self.selected_file,
                    lang_pair,
                    progress_callback=lambda value: (
                        self.progress_bar.setValue(value),
                        QApplication.processEvents()
                    )
                )
                success_message = f"Document Word traduit avec succès :\n{translated_file}"
            else:
                QMessageBox.warning(self, 'Format non supporté',
                                f"Le format de fichier {file_extension} n'est pas supporté.")
                return

            # Afficher un message de succès
            QMessageBox.information(self, 'Traduction terminée', success_message)
            self.label.setText(f"Traduction sauvegardée dans : {translated_file}")
        
        except Exception as e:
            QMessageBox.critical(self, 'Erreur',
                            f"Une erreur est survenue lors de la traduction :\n{str(e)}")
            logging.error(f"Erreur de traduction: {str(e)}", exc_info=True)

    def update_char_count(self):
        text = self.live_input.toPlainText()
        char_count = len(text)
        self.char_count_label.setText(f"{char_count} / {self.MAX_CHARS} caractères")
        
        if char_count > self.MAX_CHARS:
            excess = char_count - self.MAX_CHARS
            self.live_input.setPlainText(text[:self.MAX_CHARS])
            cursor = self.live_input.textCursor()
            cursor.setPosition(self.MAX_CHARS)
            self.live_input.setTextCursor(cursor)
            self.char_count_label.setStyleSheet("color: #ff5555;")
        else:
            self.char_count_label.setStyleSheet("color: white;")

    def translate_live(self):
        text = self.live_input.toPlainText()
        if text:
            lang_pair = self.get_lang_pair(self.live_lang_combo)
            translated_text = self.translation_manager.translate(text, lang_pair)
            self.live_output.setPlainText(translated_text)
            
    def eventFilter(self, source, event):
        if (source is self.live_input and 
            event.type() == QEvent.KeyPress and 
            event.key() == Qt.Key_Return and 
            event.modifiers() != Qt.ShiftModifier):
            self.translate_live()
            return True
        return super().eventFilter(source, event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    StyleManager.apply_style(app)
    app.setWindowIcon(QIcon(ICON_PATH))
    cred_manager = CredentialManager()
    machine_lock = MachineLock()
    login_window = LoginWindow(cred_manager, machine_lock)
    login_window.show()
    sys.exit(app.exec_())