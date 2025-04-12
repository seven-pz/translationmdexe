# translation_database.py

from datetime import datetime
import sqlite3
import hashlib
from difflib import SequenceMatcher
import json
import os
import getpass
import logging

class TranslationDatabaseManager:
    def __init__(self, db_path=None):
        """Initialise la connexion à la base de données et crée les tables si nécessaires."""
        if db_path is None:
            # Création du chemin vers le dossier data dans le répertoire de l'application
            app_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(app_dir, 'data')
            
            # Création du dossier data s'il n'existe pas
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            
            # Définition du chemin de la base de données
            self.db_path = os.path.join(data_dir, 'translations.db')
        else:
            self.db_path = db_path
        
        # S'assurer que le répertoire parent de la base de données existe
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        # Initialisation de la connexion
        self.conn = sqlite3.connect(self.db_path)
        
        # Configuration du logging
        log_dir = os.path.dirname(self.db_path)
        log_path = os.path.join(log_dir, 'database.log')
        
        logging.basicConfig(
            filename=log_path,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        logging.info(f"Base de données initialisée: {self.db_path}")
        
        # Création des tables
        self.create_tables()
        
    def create_tables(self):
        """Crée les tables nécessaires dans la base de données."""
        cursor = self.conn.cursor()
        
        # Table des documents
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            original_path TEXT NOT NULL,
            upload_date TIMESTAMP NOT NULL,
            file_type TEXT NOT NULL,
            status TEXT NOT NULL,
            metadata TEXT
        )''')
        
        # Table des versions de traduction
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            lang_pair TEXT NOT NULL,
            translated_content TEXT NOT NULL,
            translation_date TIMESTAMP NOT NULL,
            is_revised BOOLEAN DEFAULT FALSE,
            revised_by TEXT,
            revision_date TIMESTAMP,
            version INTEGER NOT NULL,
            revision_comments TEXT,
            quality_score INTEGER,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )''')
        
        # Table des segments de texte (pour la réutilisation)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_text TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            lang_pair TEXT NOT NULL,
            usage_count INTEGER DEFAULT 1,
            last_used TIMESTAMP,
            confidence_score FLOAT,
            hash TEXT NOT NULL,
            document_id INTEGER,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )''')
        
        # Index pour améliorer les performances
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON documents(file_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON documents(content_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_segment_hash ON segments(hash)')
        
        self.conn.commit()
        logging.info("Tables de base de données créées ou vérifiées avec succès")
    
    def calculate_hashes(self, file_path, content):
        """Calcule les hashes du fichier et de son contenu."""
        try:
            file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest()
            content_hash = hashlib.md5(content.encode()).hexdigest()
            return file_hash, content_hash
        except Exception as e:
            logging.error(f"Erreur lors du calcul des hashes: {str(e)}")
            raise
    
    def store_document(self, file_path, content, file_type, metadata=None):
        """Stocke un nouveau document dans la base de données."""
        cursor = self.conn.cursor()
        
        try:
            file_hash, content_hash = self.calculate_hashes(file_path, content)
            file_name = os.path.basename(file_path)
            
            # Vérifier si le document existe déjà
            cursor.execute('''
            SELECT id FROM documents 
            WHERE content_hash = ? OR file_hash = ?
            ''', (content_hash, file_hash))
            
            existing_doc = cursor.fetchone()
            if existing_doc:
                logging.info(f"Document existant trouvé: {file_name}")
                return existing_doc[0], True
                
            # Insérer le nouveau document
            cursor.execute('''
            INSERT INTO documents (
                file_name, file_hash, content_hash, original_path, 
                upload_date, file_type, status, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_name, file_hash, content_hash, file_path, 
                datetime.now().isoformat(), file_type, 'pending', 
                json.dumps(metadata) if metadata else None
            ))
            
            doc_id = cursor.lastrowid
            self.conn.commit()
            logging.info(f"Nouveau document stocké avec succès: {file_name}")
            return doc_id, False
            
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Erreur lors du stockage du document: {str(e)}")
            raise
    
    def find_similar_documents(self, content, threshold=0.8):
        """Trouve les documents similaires en utilisant SequenceMatcher."""
        cursor = self.conn.cursor()
        similar_docs = []
        
        try:
            cursor.execute('''
            SELECT id, original_path 
            FROM documents
            ORDER BY upload_date DESC
            LIMIT 50  -- Limiter la recherche aux 50 documents les plus récents
            ''')
            
            for doc_id, path in cursor.fetchall():
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        doc_content = f.read()
                    similarity = SequenceMatcher(None, content, doc_content).ratio()
                    
                    if similarity >= threshold:
                        similar_docs.append((doc_id, similarity))
            
            return sorted(similar_docs, key=lambda x: x[1], reverse=True)
            
        except Exception as e:
            logging.error(f"Erreur lors de la recherche de documents similaires: {str(e)}")
            return []
    
    def split_into_segments(self, content):
        """Découpe le contenu en segments logiques pour la traduction."""
        import re
        
        # Définir les règles de segmentation
        separators = r'(?<=[.!?])\s+(?=[A-Z])|(?<=\n)\s*(?=[A-Z])'
        segments = [seg.strip() for seg in re.split(separators, content) if seg.strip()]
        
        logging.info(f"Contenu découpé en {len(segments)} segments")
        return segments
    
    def find_matching_segments(self, segment, lang_pair, threshold=0.9):
        """Trouve les segments similaires déjà traduits."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
            SELECT source_text, translated_text, confidence_score 
            FROM segments 
            WHERE lang_pair = ?
            ORDER BY last_used DESC
            LIMIT 100  -- Limiter aux 100 segments les plus récents
            ''', (lang_pair,))
            
            matches = []
            segment_hash = hashlib.md5(segment.encode()).hexdigest()
            
            for source, translated, confidence in cursor.fetchall():
                similarity = SequenceMatcher(None, segment, source).ratio()
                if similarity >= threshold:
                    matches.append({
                        'source': source,
                        'translated': translated,
                        'similarity': similarity,
                        'confidence': confidence
                    })
            
            return sorted(matches, key=lambda x: x['similarity'], reverse=True)
            
        except Exception as e:
            logging.error(f"Erreur lors de la recherche de segments similaires: {str(e)}")
            return []
    
    def store_translation(self, document_id, lang_pair, translated_content, segments=None):
        """Stocke une traduction et ses segments."""
        cursor = self.conn.cursor()
        
        try:
            # Stocker la traduction complète
            cursor.execute('''
            INSERT INTO translations (
                document_id, lang_pair, translated_content, 
                translation_date, version
            )
            VALUES (?, ?, ?, ?,
                    (SELECT COALESCE(MAX(version), 0) + 1 
                     FROM translations 
                     WHERE document_id = ?))
            ''', (document_id, lang_pair, translated_content, 
                  datetime.now().isoformat(), document_id))
            
            translation_id = cursor.lastrowid
            
            # Stocker les segments individuels
            if segments:
                for source, translated in segments:
                    segment_hash = hashlib.md5(source.encode()).hexdigest()
                    
                    cursor.execute('''
                    INSERT INTO segments (
                        source_text, translated_text, lang_pair, hash,
                        usage_count, last_used, confidence_score, document_id
                    )
                    VALUES (?, ?, ?, ?,
                            (SELECT COALESCE(MAX(usage_count), 0) + 1 
                             FROM segments WHERE hash = ?),
                            ?, 1.0, ?)
                    ''', (source, translated, lang_pair, segment_hash,
                          segment_hash, datetime.now().isoformat(), document_id))
            
            self.conn.commit()
            logging.info(f"Traduction stockée avec succès pour le document {document_id}")
            return translation_id
            
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Erreur lors du stockage de la traduction: {str(e)}")
            raise
    
    def get_document_info(self, doc_id):
        """Récupère les informations d'un document."""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
            SELECT file_name, upload_date, status, metadata
            FROM documents
            WHERE id = ?
            ''', (doc_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'file_name': row[0],
                    'upload_date': datetime.fromisoformat(row[1]),
                    'status': row[2],
                    'metadata': json.loads(row[3]) if row[3] else {}
                }
            return None
            
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des informations du document: {str(e)}")
            return None

    def get_translation_history(self):
        """Récupère l'historique complet des traductions."""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
            SELECT 
                d.file_name,
                t.translation_date,
                t.lang_pair,
                CASE 
                    WHEN t.is_revised THEN 'Révisé'
                    ELSE 'Non révisé'
                END as status,
                t.revised_by,
                t.quality_score
            FROM translations t
            JOIN documents d ON t.document_id = d.id
            ORDER BY t.translation_date DESC
            ''')
            
            return [
                {
                    'file_name': row[0],
                    'date': row[1],
                    'lang_pair': row[2],
                    'status': row[3],
                    'revisor': row[4] or '-',
                    'score': row[5] or '-'
                }
                for row in cursor.fetchall()
            ]
            
        except Exception as e:
            logging.error(f"Erreur lors de la récupération de l'historique: {str(e)}")
            return []

    def get_statistics(self):
        """Calcule les statistiques globales."""
        cursor = self.conn.cursor()
        try:
            # Nombre total de documents
            cursor.execute('SELECT COUNT(*) FROM documents')
            total_docs = cursor.fetchone()[0]
            
            # Nombre total de traductions
            cursor.execute('SELECT COUNT(*) FROM translations')
            total_translations = cursor.fetchone()[0]
            
            # Taux de révision
            cursor.execute('SELECT COUNT(*) FROM translations WHERE is_revised = TRUE')
            revised_count = cursor.fetchone()[0]
            revision_rate = (revised_count / total_translations * 100) if total_translations > 0 else 0
            
            # Taux de réutilisation
            cursor.execute('SELECT COUNT(*) FROM segments WHERE usage_count > 1')
            reused_segments = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM segments')
            total_segments = cursor.fetchone()[0]
            reuse_rate = (reused_segments / total_segments * 100) if total_segments > 0 else 0
            
            stats = {
                'total_documents': total_docs,
                'total_translations': total_translations,
                'revision_rate': revision_rate,
                'reuse_rate': reuse_rate
            }
            
            logging.info("Statistiques calculées avec succès")
            return stats
            
        except Exception as e:
            logging.error(f"Erreur lors du calcul des statistiques: {str(e)}")
            return {
                'total_documents': 0,
                'total_translations': 0,
                'revision_rate': 0,
                'reuse_rate': 0
            }

    def close(self):
        """Ferme proprement la connexion à la base de données."""
        try:
            self.conn.close()
            logging.info("Connexion à la base de données fermée avec succès")
        except Exception as e:
            logging.error(f"Erreur lors de la fermeture de la connexion: {str(e)}")