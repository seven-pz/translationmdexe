import winreg
import uuid
import os
from cryptography.fernet import Fernet

class MachineLock:
    def __init__(self, key_file='machine_key.key'):
        self.key_file = key_file
        self.key = self.load_or_generate_key()
        self.fernet = Fernet(self.key)
        self.lock_file = os.path.join(os.getenv('APPDATA'), '.securedtrad_lock')
        self.valid_auth_codes = [
            "INSTALL-123456",
            "SETUP-ABCDEF",
            "AUTH-XYZQWE",
            "ACTIVATE-789012",
            "ST24-ALPHA-7X9K2", #utilisé
            "ST24-BETA-M5N8P",
            "ST24-GAMMA-Q4W6R",
            "ST24-DELTA-H2J5L",
            "ST24-EPSILON-T8V3B",
            "ST24-ZETA-Y6C9D",
            "ST24-ETA-F4G7H",
            "ST24-THETA-U1I8O",
            "ST24-IOTA-A5S2D",
            "ST24-KAPPA-X7M4N"
            "UNLOCK-MNBVCX"
        ]

    def load_or_generate_key(self):
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as file:
                return file.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as file:
                file.write(key)
            return key

    def get_machine_id(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Cryptography")
            machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            return machine_guid
        except:
            return str(uuid.getnode())

    def encrypt_machine_id(self):
        machine_id = self.get_machine_id()
        return self.fernet.encrypt(machine_id.encode()).decode()

    def verify_machine_id(self, encrypted_id):
        try:
            decrypted_id = self.fernet.decrypt(encrypted_id.encode()).decode()
            return decrypted_id == self.get_machine_id()
        except:
            return False

    def lock_to_machine(self):
        encrypted_id = self.encrypt_machine_id()
        with open(self.lock_file, 'w') as file:
            file.write(encrypted_id)

    def check_lock(self):
        if not os.path.exists(self.lock_file):
            return False
        with open(self.lock_file, 'r') as file:
            encrypted_id = file.read()
        return self.verify_machine_id(encrypted_id)

    def is_valid_authorization_code(self, code):
        return code in self.valid_auth_codes

    def install_on_new_machine(self, authorization_code):
        if self.is_valid_authorization_code(authorization_code):
            self.lock_to_machine()
            # Optionnel : Supprimer le code utilisé pour éviter sa réutilisation
            self.valid_auth_codes.remove(authorization_code)
            return True
        return False