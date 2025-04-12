import json
import os
import sys
import logging
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

class CredentialManager:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            # Exécutable
            self.app_dir = os.path.dirname(sys.executable)
        else:
            # Script Python
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.data_dir = os.path.join(os.path.expanduser('~'), '.securedtrad')
        self.key_file = os.path.join(self.data_dir, 'secret.key')
        self.cred_file = os.path.join(self.data_dir, 'credentials.enc')
        
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        logging.basicConfig(filename=os.path.join(self.data_dir, 'securedtrad.log'),
                          level=logging.INFO,
                          format='%(asctime)s - %(levelname)s - %(message)s')
        
        self.key = self.load_or_generate_key()
        self.fernet = Fernet(self.key)
        self.initialize_credentials()

    def load_or_generate_key(self):
        try:
            with open(self.key_file, 'rb') as file:
                return file.read()
        except FileNotFoundError:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as file:
                file.write(key)
            return key

    def load_credentials(self):
        try:
            with open(self.cred_file, 'rb') as file:
                encrypted = file.read()
            decrypted = self.fernet.decrypt(encrypted)
            credentials = json.loads(decrypted)
            return credentials
        except FileNotFoundError:
            return {}
        except Exception as e:
            logging.error(f"Erreur lors du chargement des credentials: {str(e)}")
            return {}

    def save_credentials(self, credentials):
        try:
            encrypted = self.fernet.encrypt(json.dumps(credentials).encode())
            with open(self.cred_file, 'wb') as file:
                file.write(encrypted)
            logging.info("Credentials sauvegardés avec succès")
            return True
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde des credentials: {str(e)}")
            return False

    def initialize_credentials(self):
        credentials = self.load_credentials()
        changed = False
        
        # Définition de la date d'expiration (90 jours)
        expiration = (datetime.now() + timedelta(days=90)).isoformat()
        
        if 'admin' not in credentials:
            credentials['admin'] = {
                'password': 'password123',  
                'expiration': expiration,
                'license_type': 'admin'
            }
            changed = True
            logging.info("Utilisateur admin ajouté")
        
        if 'jyga' not in credentials:
            credentials['jyga'] = {
                'password': 'jygatech',  
                'expiration': expiration,
                'license_type': 'premium'
            }
            changed = True
            logging.info("Utilisateur jyga ajouté")
        
        if changed:
            self.save_credentials(credentials)

    def check_credentials(self, username, password):
        credentials = self.load_credentials()
        logging.info(f"Vérification des credentials pour l'utilisateur: {username}")
        
        if username in credentials:
            user_data = credentials[username]
            if user_data['password'] == password:
                expiration = datetime.fromisoformat(user_data['expiration'])
                if expiration > datetime.now():
                    license_type = user_data.get('license_type', 'standard')
                    logging.info(f"Connexion réussie pour l'utilisateur: {username}")
                    return True, (expiration - datetime.now()).days, license_type
                else:
                    logging.warning(f"Licence expirée pour l'utilisateur: {username}")
            else:
                logging.warning(f"Mot de passe incorrect pour l'utilisateur: {username}")
        else:
            logging.warning(f"Utilisateur non trouvé: {username}")
        return False, 0, 'invalid'

    def extend_license(self, username, days=90):
        """Prolonge la licence d'un utilisateur."""
        credentials = self.load_credentials()
        if username in credentials:
            current_expiration = datetime.fromisoformat(credentials[username]['expiration'])
            new_expiration = max(current_expiration, datetime.now()) + timedelta(days=days)
            credentials[username]['expiration'] = new_expiration.isoformat()
            if self.save_credentials(credentials):
                logging.info(f"Licence prolongée pour {username} de {days} jours")
                return True
        return False