import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, 
                            QTextEdit, QFileDialog, QLabel, QComboBox, QProgressBar, 
                            QLineEdit, QMessageBox, QFrame, QTabWidget, QTableWidget,
                            QTableWidgetItem, QSplitter, QDialog, QFormLayout, QSpinBox,
                            QHeaderView)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor
import os
from datetime import datetime
from translation_manager import TranslationManager
from docx_translator import DocxTranslator

class SegmentComparisonDialog(QDialog):
    """Dialog pour comparer les segments similaires"""
    def __init__(self, original, similar_segments, parent=None):
        super().__init__(parent)
        self.init_ui(original, similar_segments)

    def init_ui(self, original, similar_segments):
        layout = QVBoxLayout()
        
        # Texte original
        layout.addWidget(QLabel("Texte original:"))
        original_text = QTextEdit()
        original_text.setPlainText(original)
        original_text.setReadOnly(True)
        layout.addWidget(original_text)
        
        # Segments similaires
        layout.addWidget(QLabel("Segments similaires trouvés:"))
        self.segments_table = QTableWidget()
        self.segments_table.setColumnCount(3)
        self.segments_table.setHorizontalHeaderLabels(["Segment", "Traduction", "Similarité"])
        
        for segment in similar_segments:
            row = self.segments_table.rowCount()
            self.segments_table.insertRow(row)
            self.segments_table.setItem(row, 0, QTableWidgetItem(segment['source']))
            self.segments_table.setItem(row, 1, QTableWidgetItem(segment['translated']))
            self.segments_table.setItem(row, 2, QTableWidgetItem(f"{segment['similarity']*100:.1f}%"))
        
        layout.addWidget(self.segments_table)
        
        # Boutons
        button_box = QHBoxLayout()
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        button_box.addWidget(close_btn)
        layout.addLayout(button_box)
        
        self.setLayout(layout)
        self.setWindowTitle("Segments similaires")
        self.resize(800, 600)

class EnhancedTranslationApp(QWidget):
    def __init__(self, days_left, license_type="standard"):
        super().__init__()
        self.days_left = days_left
        self.license_type = license_type
        self.translation_manager = TranslationManager()
        self.docx_translator = DocxTranslator(self.translation_manager)
        self.selected_file = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Création des onglets
        self.tabs = QTabWidget()
        
        # Onglet de traduction
        translation_tab = self.create_translation_tab()
        self.tabs.addTab(translation_tab, "Traduction")
        
        # Onglet historique
        history_tab = self.create_history_tab()
        self.tabs.addTab(history_tab, "Historique")
        
        # Onglet statistiques
        stats_tab = self.create_stats_tab()
        self.tabs.addTab(stats_tab, "Statistiques")
        
        main_layout.addWidget(self.tabs)
        
        # Barre de statut
        status_bar = self.create_status_bar()
        main_layout.addWidget(status_bar)
        
        self.setLayout(main_layout)
        self.setWindowTitle("SecuredTrad - Traducteur Professionnel")
        self.resize(1200, 800)

    def create_translation_tab(self):
        """Crée l'onglet principal de traduction"""
        tab = QWidget()
        layout = QHBoxLayout()
        
        # Panneau gauche
        left_panel = QVBoxLayout()
        
        # Sélection de la langue
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "Français vers Anglais",
            "Anglais vers Français",
            "Anglais vers Espagnol",
            "Espagnol vers Anglais"
        ])
        left_panel.addWidget(self.lang_combo)
        
        # Bouton de sélection de fichier
        file_layout = QHBoxLayout()
        self.btn_select = QPushButton('Sélectionner un fichier')
        self.btn_select.clicked.connect(self.select_file)
        file_layout.addWidget(self.btn_select)
        
        self.file_label = QLabel("Aucun fichier sélectionné")
        file_layout.addWidget(self.file_label)
        left_panel.addLayout(file_layout)
        
        # Zone de texte source
        left_panel.addWidget(QLabel("Texte source:"))
        self.source_text = QTextEdit()
        left_panel.addWidget(self.source_text)
        
        # Tableau des segments similaires
        left_panel.addWidget(QLabel("Segments similaires:"))
        self.similar_segments_table = QTableWidget()
        self.similar_segments_table.setColumnCount(3)
        self.similar_segments_table.setHorizontalHeaderLabels(["Texte", "Similarité", "Actions"])
        self.similar_segments_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        left_panel.addWidget(self.similar_segments_table)
        
        # Panneau droit
        right_panel = QVBoxLayout()
        
        # Zone de traduction
        right_panel.addWidget(QLabel("Traduction:"))
        self.translation_text = QTextEdit()
        self.translation_text.setReadOnly(True)
        right_panel.addWidget(self.translation_text)
        
        # Boutons d'action
        buttons_layout = QHBoxLayout()
        
        self.btn_translate = QPushButton('Traduire')
        self.btn_translate.clicked.connect(self.translate_content)
        buttons_layout.addWidget(self.btn_translate)
        
        self.btn_save = QPushButton('Sauvegarder')
        self.btn_save.clicked.connect(self.save_translation)
        buttons_layout.addWidget(self.btn_save)
        
        right_panel.addLayout(buttons_layout)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        right_panel.addWidget(self.progress_bar)
        
        # Ajout des panneaux au layout principal
        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 1)
        
        tab.setLayout(layout)
        return tab

    def create_history_tab(self):
        """Crée l'onglet d'historique"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Tableau d'historique
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Document", "Date", "Langue", "État",
            "Qualité", "Actions"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.history_table)
        
        # Boutons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Rafraîchir")
        refresh_btn.clicked.connect(self.refresh_history)
        button_layout.addWidget(refresh_btn)
        
        export_btn = QPushButton("Exporter")
        export_btn.clicked.connect(self.export_history)
        button_layout.addWidget(export_btn)
        
        layout.addLayout(button_layout)
        
        tab.setLayout(layout)
        self.refresh_history()  # Charger l'historique initial
        return tab

    def create_stats_tab(self):
        """Crée l'onglet de statistiques"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Statistiques générales
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.StyledPanel)
        stats_layout = QFormLayout()
        
        self.total_docs_label = QLabel("0")
        self.total_translations_label = QLabel("0")
        self.reuse_rate_label = QLabel("0%")
        self.avg_quality_label = QLabel("0/10")
        
        stats_layout.addRow("Documents totaux:", self.total_docs_label)
        stats_layout.addRow("Traductions:", self.total_translations_label)
        stats_layout.addRow("Taux de réutilisation:", self.reuse_rate_label)
        stats_layout.addRow("Qualité moyenne:", self.avg_quality_label)
        
        stats_frame.setLayout(stats_layout)
        layout.addWidget(stats_frame)
        
        # Bouton de mise à jour
        update_btn = QPushButton("Mettre à jour les statistiques")
        update_btn.clicked.connect(self.update_statistics)
        layout.addWidget(update_btn)
        
        tab.setLayout(layout)
        self.update_statistics()  # Charger les stats initiales
        return tab

    def create_status_bar(self):
        """Crée la barre de statut"""
        status_bar = QFrame()
        status_bar.setFrameStyle(QFrame.StyledPanel)
        
        layout = QHBoxLayout()
        
        # Information de licence
        license_info = QLabel(f"Licence {self.license_type} - {self.days_left} jours restants")
        layout.addWidget(license_info)
        
        # Espace
        layout.addStretch()
        
        # Version
        version_label = QLabel("v1.2.0")
        layout.addWidget(version_label)
        
        status_bar.setLayout(layout)
        return status_bar

    def select_file(self):
        """Gère la sélection de fichier"""
        fname = QFileDialog.getOpenFileName(
            self,
            'Sélectionner un fichier',
            '',
            'Documents (*.txt *.md *.docx)'
        )
        
        if fname[0]:
            self.selected_file = fname[0]
            self.file_label.setText(os.path.basename(fname[0]))
            
            # Charger le contenu du fichier
            try:
                if fname[0].endswith('.docx'):
                    # Utiliser python-docx pour lire le contenu
                    from docx import Document
                    doc = Document(fname[0])
                    content = '\n'.join(paragraph.text for paragraph in doc.paragraphs)
                else:
                    with open(fname[0], 'r', encoding='utf-8') as f:
                        content = f.read()
                
                self.source_text.setPlainText(content)
                self.find_similar_segments(content)
                
            except Exception as e:
                QMessageBox.critical(self, 'Erreur',
                                   f"Erreur lors de la lecture du fichier: {str(e)}")

    def find_similar_segments(self, content):
        """Recherche les segments similaires"""
        try:
            segments = self.translation_manager.db_manager.split_into_segments(content)
            self.similar_segments_table.setRowCount(0)
            
            for segment in segments:
                if len(segment.strip()) > 10:  # Ignorer les segments trop courts
                    similar = self.translation_manager.db_manager.find_matching_segments(
                        segment,
                        self.get_lang_pair()
                    )
                    
                    if similar:
                        row = self.similar_segments_table.rowCount()
                        self.similar_segments_table.insertRow(row)
                        
                        # Texte tronqué
                        text = segment[:50] + "..." if len(segment) > 50 else segment
                        self.similar_segments_table.setItem(row, 0, QTableWidgetItem(text))
                        
                        # Meilleure similarité
                        similarity = similar[0]['similarity']
                        self.similar_segments_table.setItem(
                            row, 1,
                            QTableWidgetItem(f"{similarity*100:.1f}%")
                        )
                        
                        # Bouton pour voir les détails
                        view_btn = QPushButton("Voir")
                        view_btn.clicked.connect(
                            lambda s=segment, sim=similar: self.show_similar_segments(s, sim)
                        )
                        self.similar_segments_table.setCellWidget(row, 2, view_btn)
            
        except Exception as e:
            QMessageBox.warning(self, 'Attention',
                              f"Erreur lors de la recherche de segments similaires: {str(e)}")

    def show_similar_segments(self, segment, similar_segments):
        """Affiche les segments similaires dans une boîte de dialogue"""
        dialog = SegmentComparisonDialog(segment, similar_segments, self)
        dialog.exec_()

    def translate_content(self):
        """Gère la traduction du contenu"""
        content = self.source_text.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, 'Attention', 'Aucun texte à traduire.')
            return
            
        try:
            # Traduction avec gestion de la progression
            if self.selected_file:
                translated = self.translation_manager.translate_document(
                    self.selected_file,
                    content,
                    self.get_lang_pair(),
                    lambda p: self.progress_bar.setValue(p)
                )
            else:
                translated = self.translation_manager.translate(
                    content,
                    self.get_lang_pair()
                )
            
            self.translation_text.setPlainText(translated)
            self.progress_bar.setValue(100)
            
        except Exception as e:
            QMessageBox.critical(self, 'Erreur',
                               f"Erreur lors de la traduction: {str(e)}")
            self.progress_bar.setValue(0)

    def save_translation(self):
        """Sauvegarde la traduction"""
        if not self.translation_text.toPlainText():
            QMessageBox.warning(self, 'Attention',
                              'Aucune traduction à sauvegarder.')
            return
            
        fname = QFileDialog.getSaveFileName(
            self,
            'Sauvegarder la traduction',
            '',
            'Documents (*.txt *.md *.docx)'
        )
        
        if fname[0]:
            try:
                with open(fname[0], 'w', encoding='utf-8') as f:
                    f.write(self.translation_text.toPlainText())
                QMessageBox.information(self, 'Succès',
                                      'Traduction sauvegardée avec succès.')
            except Exception as e:
                QMessageBox.critical(self, 'Erreur',
                                   f"Erreur lors de la sauvegarde: {str(e)}")

    def refresh_history(self):
        """Met à jour le tableau d'historique"""
        try:
            history = self.translation_manager.get_translation_history()
            self.history_table.setRowCount(len(history))
            
            for row, entry in enumerate(history):
                # Document
                self.history_table.setItem(
                    row, 0,
                    QTableWidgetItem(entry['file_name'])
                )
                
                # Date
                date = datetime.fromisoformat(entry['date'])
                self.history_table.setItem(
                    row, 1,
                    QTableWidgetItem(date.strftime("%Y-%m-%d %H:%M"))
                )
                
                # Langue
                self.history_table.setItem(
                    row, 2,
                    QTableWidgetItem(self.get_language_pair_name(entry['lang_pair']))
                )
                
                # État
                self.history_table.setItem(
                    row, 3,
                    QTableWidgetItem(entry['status'])
                )
                
                # Qualité
                self.history_table.setItem(
                    row, 4,
                    QTableWidgetItem(str(entry['score']))
                )
                
                # Boutons d'action
                actions_widget = QWidget()
                actions_layout = QHBoxLayout()
                actions_layout.setContentsMargins(0, 0, 0, 0)
                
                view_btn = QPushButton("Voir")
                view_btn.clicked.connect(lambda checked, e=entry: self.view_translation(e))
                actions_layout.addWidget(view_btn)
                
                if self.license_type in ['premium', 'admin']:
                    edit_btn = QPushButton("Modifier")
                    edit_btn.clicked.connect(lambda checked, e=entry: self.edit_translation(e))
                    actions_layout.addWidget(edit_btn)
                
                actions_widget.setLayout(actions_layout)
                self.history_table.setCellWidget(row, 5, actions_widget)
            
            self.history_table.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.warning(self, 'Attention',
                              f"Erreur lors du rafraîchissement de l'historique: {str(e)}")

    def export_history(self):
        """Exporte l'historique des traductions"""
        fname = QFileDialog.getSaveFileName(
            self,
            'Exporter l\'historique',
            '',
            'CSV (*.csv);;Excel (*.xlsx)'
        )
        
        if fname[0]:
            try:
                self.translation_manager.db_manager.export_history(fname[0])
                QMessageBox.information(self, 'Succès',
                                      'Historique exporté avec succès.')
            except Exception as e:
                QMessageBox.critical(self, 'Erreur',
                                   f"Erreur lors de l'export: {str(e)}")

    def update_statistics(self):
        """Met à jour les statistiques affichées"""
        try:
            stats = self.translation_manager.get_statistics()
            
            self.total_docs_label.setText(str(stats['total_documents']))
            self.total_translations_label.setText(str(stats['total_translations']))
            self.reuse_rate_label.setText(f"{stats['reuse_rate']:.1f}%")
            
            # Calcul de la qualité moyenne si disponible
            if 'average_quality' in stats:
                self.avg_quality_label.setText(f"{stats['average_quality']:.1f}/10")
            
        except Exception as e:
            QMessageBox.warning(self, 'Attention',
                              f"Erreur lors de la mise à jour des statistiques: {str(e)}")

    def view_translation(self, entry):
        """Affiche une traduction de l'historique"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Détails de la traduction")
        layout = QVBoxLayout()
        
        # Informations
        info_layout = QFormLayout()
        info_layout.addRow("Document:", QLabel(entry['file_name']))
        info_layout.addRow("Date:", QLabel(entry['date']))
        info_layout.addRow("Langues:", QLabel(self.get_language_pair_name(entry['lang_pair'])))
        info_layout.addRow("État:", QLabel(entry['status']))
        info_layout.addRow("Score:", QLabel(str(entry['score'])))
        
        layout.addLayout(info_layout)
        
        # Contenu
        content_label = QLabel("Contenu de la traduction:")
        layout.addWidget(content_label)
        
        text_edit = QTextEdit()
        text_edit.setPlainText(entry.get('translated_content', ''))
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        # Bouton fermer
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.resize(600, 400)
        dialog.exec_()

    def edit_translation(self, entry):
        """Permet de modifier une traduction (utilisateurs premium/admin uniquement)"""
        if self.license_type not in ['premium', 'admin']:
            QMessageBox.warning(self, 'Accès refusé',
                              'Cette fonctionnalité est réservée aux licences premium.')
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Modifier la traduction")
        layout = QVBoxLayout()
        
        # Zone d'édition
        text_edit = QTextEdit()
        text_edit.setPlainText(entry.get('translated_content', ''))
        layout.addWidget(text_edit)
        
        # Boutons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Sauvegarder")
        save_btn.clicked.connect(lambda: self.save_edited_translation(
            entry, text_edit.toPlainText(), dialog
        ))
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.resize(600, 400)
        dialog.exec_()

    def save_edited_translation(self, entry, new_content, dialog):
        """Sauvegarde une traduction modifiée"""
        try:
            # Mise à jour dans la base de données
            self.translation_manager.db_manager.update_translation(
                entry['file_name'],
                new_content,
                entry['lang_pair']
            )
            
            QMessageBox.information(dialog, 'Succès',
                                  'Traduction mise à jour avec succès.')
            dialog.accept()
            self.refresh_history()
            
        except Exception as e:
            QMessageBox.critical(dialog, 'Erreur',
                               f"Erreur lors de la mise à jour: {str(e)}")

    def get_lang_pair(self):
        """Obtient la paire de langues sélectionnée"""
        index = self.lang_combo.currentIndex()
        pairs = ["fr-en", "en-fr", "en-es", "es-en"]
        return pairs[index]

    def get_language_pair_name(self, pair_code):
        """Convertit le code de la paire de langues en nom lisible"""
        pairs = {
            "fr-en": "Français → Anglais",
            "en-fr": "Anglais → Français",
            "en-es": "Anglais → Espagnol",
            "es-en": "Espagnol → Anglais"
        }
        return pairs.get(pair_code, pair_code)

    def closeEvent(self, event):
        """Gestion de la fermeture de l'application"""
        try:
            # Nettoyage des ressources
            self.translation_manager.cleanup()
            event.accept()
        except Exception as e:
            logging.error(f"Erreur lors de la fermeture: {str(e)}")
            event.accept()