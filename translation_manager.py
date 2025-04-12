from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import re
from datetime import datetime
import logging
import os
from translation_database import TranslationDatabaseManager

class TranslationManager:
    def __init__(self):
        """
        Initialise le gestionnaire de traduction avec les modèles et la base de données.
        """
        self.models = {}
        self.tokenizers = {}
        
        # Création du dossier data si nécessaire
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        # Initialisation de la base de données
        db_path = os.path.join(data_dir, 'translations.db')
        self.db_manager = TranslationDatabaseManager(db_path)
        
        # Configuration du logging
        log_path = os.path.join(data_dir, 'translation_manager.log')
        logging.basicConfig(
            filename=log_path,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        self.supported_pairs = {
            "fr-en": "Helsinki-NLP/opus-mt-fr-en",
            "en-fr": "Helsinki-NLP/opus-mt-en-fr",
            "en-es": "Helsinki-NLP/opus-mt-en-es",
            "es-en": "Helsinki-NLP/opus-mt-es-en"
        }
        
        self.translation_config = {
            'max_length': 512,
            'num_beams': 4,
            'length_penalty': 1.0,
            'early_stopping': True
        }

    def load_model(self, lang_pair):
        """
        Charge un modèle de traduction pour une paire de langues spécifique.
        """
        try:
            if lang_pair not in self.models:
                model_name = self.supported_pairs.get(lang_pair)
                if not model_name:
                    raise ValueError(f"Paire de langues non supportée : {lang_pair}")
                
                logging.info(f"Chargement du modèle {lang_pair}")
                self.tokenizers[lang_pair] = AutoTokenizer.from_pretrained(model_name)
                self.models[lang_pair] = AutoModelForSeq2SeqLM.from_pretrained(model_name)
                
                # Passage en mode évaluation
                self.models[lang_pair].eval()
                
                # Utilisation du GPU si disponible
                if torch.cuda.is_available():
                    self.models[lang_pair].to('cuda')
                    logging.info(f"Modèle {lang_pair} chargé sur GPU")
                
        except Exception as e:
            logging.error(f"Erreur lors du chargement du modèle: {str(e)}")
            raise

    def translate(self, text, lang_pair):
        """
        Méthode principale de traduction, compatible avec l'ancienne interface.
        """
        try:
            # Vérification des entrées
            if not text or not text.strip():
                return text
                
            # Recherche de traductions existantes
            similar_segments = self.db_manager.find_matching_segments(text, lang_pair)
            if similar_segments and similar_segments[0]['similarity'] > 0.95:
                logging.info("Utilisation d'une traduction existante")
                return similar_segments[0]['translated']
            
            # Nouvelle traduction
            translated_text = self._perform_translation(text, lang_pair)
            
            # Stockage de la nouvelle traduction
            self.db_manager.store_translation(
                None, lang_pair, translated_text,
                [(text, translated_text)]
            )
            
            return translated_text
            
        except Exception as e:
            logging.error(f"Erreur de traduction: {str(e)}")
            return text  # Retourne le texte original en cas d'erreur

    def _perform_translation(self, text, lang_pair):
        """
        Effectue la traduction avec le modèle.
        """
        self.load_model(lang_pair)
        
        # Préparation des entrées
        inputs = self.tokenizers[lang_pair](
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.translation_config['max_length']
        )
        
        # Déplacement sur GPU si disponible
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
        
        # Décodage et nettoyage
        translated_text = self.tokenizers[lang_pair].decode(outputs[0], skip_special_tokens=True)
        return self._clean_translation(translated_text)

    def _clean_translation(self, text):
        """
        Nettoie la sortie de traduction.
        """
        # Suppression des préfixes courants
        text = re.sub(r"^(I'm sorry|I apologize|Translation:|Translated text:)\s*", "", text)
        
        # Nettoyage des espaces et de la ponctuation
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s+([.,!?])', r'\1', text)
        
        return text.strip()

    def translate_document(self, file_path, content, lang_pair, progress_callback=None):
        """
        Traduit un document complet.
        """
        try:
            # Stockage du document
            doc_id, exists = self.db_manager.store_document(
                file_path, content, os.path.splitext(file_path)[1][1:]
            )
            
            # Segmentation du document
            segments = self.db_manager.split_into_segments(content)
            total_segments = len(segments)
            translated_segments = []
            
            for i, segment in enumerate(segments):
                # Traduction du segment
                translated = self.translate(segment, lang_pair)
                translated_segments.append(translated)
                
                # Mise à jour de la progression
                if progress_callback and total_segments > 0:
                    progress = int((i + 1) * 100 / total_segments)
                    progress_callback(progress)
            
            # Assemblage de la traduction
            translated_content = '\n'.join(translated_segments)
            
            # Stockage de la traduction complète
            self.db_manager.store_translation(
                doc_id, 
                lang_pair, 
                translated_content,
                list(zip(segments, translated_segments))
            )
            
            return translated_content
            
        except Exception as e:
            logging.error(f"Erreur lors de la traduction du document: {str(e)}")
            raise

    def get_statistics(self):
        """
        Récupère les statistiques de traduction.
        """
        return self.db_manager.get_statistics()

    def get_translation_history(self):
        """
        Récupère l'historique des traductions.
        """
        return self.db_manager.get_translation_history()

    def cleanup(self):
        """
        Nettoie les ressources.
        """
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.db_manager.close()
            self.models.clear()
            self.tokenizers.clear()
            logging.info("Nettoyage effectué avec succès")
        except Exception as e:
            logging.error(f"Erreur lors du nettoyage: {str(e)}")

    def get_model_name(self, lang_pair):
        """Maintient la compatibilité avec l'ancien code."""
        return self.supported_pairs.get(lang_pair)