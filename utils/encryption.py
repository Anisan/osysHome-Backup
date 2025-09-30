import os  
import base64  
import hashlib  
from cryptography.fernet import Fernet  
from cryptography.hazmat.primitives import hashes  
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  
from cryptography.hazmat.backends import default_backend  
import tarfile  
import shutil  
  
class BackupEncryption:  
    """Класс для шифрования и дешифрования резервных копий"""  
      
    def __init__(self, password=None):  
        self.password = password  
        self.backend = default_backend()  
          
    def generate_key_from_password(self, password, salt=None):  
        """Генерация ключа шифрования из пароля"""  
        if salt is None:  
            salt = os.urandom(16)  
              
        kdf = PBKDF2HMAC(  
            algorithm=hashes.SHA256(),  
            length=32,  
            salt=salt,  
            iterations=100000,  
            backend=self.backend  
        )  
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))  
        return key, salt  
          
    def generate_random_key(self):  
        """Генерация случайного ключа шифрования"""  
        return Fernet.generate_key()  
          
    def encrypt_file(self, file_path, key, output_path=None):  
        """Шифрование отдельного файла"""  
        if output_path is None:  
            output_path = file_path + '.encrypted'  
              
        fernet = Fernet(key)  
          
        with open(file_path, 'rb') as file:  
            file_data = file.read()  
              
        encrypted_data = fernet.encrypt(file_data)  
          
        with open(output_path, 'wb') as file:  
            file.write(encrypted_data)  
              
        return output_path  
          
    def decrypt_file(self, encrypted_file_path, key, output_path=None):  
        """Дешифрование отдельного файла"""  
        if output_path is None:  
            output_path = encrypted_file_path.replace('.encrypted', '')  
              
        fernet = Fernet(key)  
          
        with open(encrypted_file_path, 'rb') as file:  
            encrypted_data = file.read()  
              
        try:  
            decrypted_data = fernet.decrypt(encrypted_data)  
        except Exception as e:  
            raise ValueError(f"Ошибка дешифрования: неверный ключ или поврежденные данные - {e}")  
              
        with open(output_path, 'wb') as file:  
            file.write(decrypted_data)  
              
        return output_path  
          
    def encrypt_directory(self, directory_path, key, output_path=None):  
        """Шифрование всей директории"""  
        if output_path is None:  
            output_path = directory_path + '.encrypted.tar.gz'  
              
        # Создание архива  
        temp_archive = directory_path + '.temp.tar.gz'  
        with tarfile.open(temp_archive, 'w:gz') as tar:  
            tar.add(directory_path, arcname=os.path.basename(directory_path))  
              
        # Шифрование архива  
        encrypted_path = self.encrypt_file(temp_archive, key, output_path)  
          
        # Удаление временного архива  
        os.remove(temp_archive)  
          
        return encrypted_path  
          
    def decrypt_directory(self, encrypted_path, key, output_directory=None):  
        """Дешифрование директории"""  
        if output_directory is None:  
            output_directory = os.path.dirname(encrypted_path)  
              
        # Дешифрование архива  
        temp_archive = encrypted_path.replace('.encrypted.tar.gz', '.temp.tar.gz')  
        self.decrypt_file(encrypted_path, key, temp_archive)  
          
        # Извлечение архива  
        with tarfile.open(temp_archive, 'r:gz') as tar:  
            tar.extractall(output_directory)  
              
        # Удаление временного архива  
        os.remove(temp_archive)  
          
        # Возвращение пути к извлеченной директории  
        extracted_name = os.path.basename(encrypted_path).replace('.encrypted.tar.gz', '')  
        return os.path.join(output_directory, extracted_name)  
  
class AESEncryption:  
    """Альтернативная реализация с использованием AES"""  
      
    def __init__(self):  
        self.backend = default_backend()  
          
    def generate_key(self):  
        """Генерация 256-битного ключа AES"""  
        return os.urandom(32)  
          
    def encrypt_data(self, data, key):  
        """Шифрование данных с использованием AES-GCM"""  
        # Генерация случайного IV  
        iv = os.urandom(12)  
          
        # Создание шифра  
        cipher = Cipher(  
            algorithms.AES(key),  
            modes.GCM(iv),  
            backend=self.backend  
        )  
        encryptor = cipher.encryptor()  
          
        # Шифрование  
        ciphertext = encryptor.update(data) + encryptor.finalize()  
          
        # Возвращение IV + tag + зашифрованные данные  
        return iv + encryptor.tag + ciphertext  
          
    def decrypt_data(self, encrypted_data, key):  
        """Дешифрование данных AES-GCM"""  
        # Извлечение IV, tag и зашифрованных данных  
        iv = encrypted_data[:12]  
        tag = encrypted_data[12:28]  
        ciphertext = encrypted_data[28:]  
          
        # Создание дешифратора  
        cipher = Cipher(  
            algorithms.AES(key),  
            modes.GCM(iv, tag),  
            backend=self.backend  
        )  
        decryptor = cipher.decryptor()  
          
        # Дешифрование  
        try:  
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()  
            return plaintext  
        except Exception as e:  
            raise ValueError(f"Ошибка дешифрования AES: {e}")  
  
def encrypt_backup(backup_path, encryption_key=None, method='fernet'):  
    """  
    Основная функция для шифрования резервной копии  
      
    Args:  
        backup_path: Путь к резервной копии  
        encryption_key: Ключ шифрования (если None, будет сгенерирован)  
        method: Метод шифрования ('fernet' или 'aes')  
      
    Returns:  
        tuple: (путь к зашифрованному файлу, ключ шифрования)  
    """  
    if method == 'fernet':  
        encryptor = BackupEncryption()  
          
        if encryption_key is None:  
            encryption_key = encryptor.generate_random_key()  
        elif isinstance(encryption_key, str):  
            # Если передан пароль, генерируем ключ  
            encryption_key, salt = encryptor.generate_key_from_password(encryption_key)  
            # Сохраняем соль для последующего дешифрования  
            salt_file = backup_path + '.salt'  
            with open(salt_file, 'wb') as f:  
                f.write(salt)  
                  
        if os.path.isdir(backup_path):  
            encrypted_path = encryptor.encrypt_directory(backup_path, encryption_key)  
            # Удаление исходной директории после шифрования  
            shutil.rmtree(backup_path)  
        else:  
            encrypted_path = encryptor.encrypt_file(backup_path, encryption_key)  
            # Удаление исходного файла после шифрования  
            os.remove(backup_path)  
              
    elif method == 'aes':  
        encryptor = AESEncryption()  
          
        if encryption_key is None:  
            encryption_key = encryptor.generate_key()  
              
        # Для AES сначала создаем архив, если это директория  
        if os.path.isdir(backup_path):  
            archive_path = backup_path + '.tar.gz'  
            with tarfile.open(archive_path, 'w:gz') as tar:  
                tar.add(backup_path, arcname=os.path.basename(backup_path))  
            shutil.rmtree(backup_path)  
            backup_path = archive_path  
              
        # Шифрование файла  
        with open(backup_path, 'rb') as f:  
            data = f.read()  
              
        encrypted_data = encryptor.encrypt_data(data, encryption_key)  
        encrypted_path = backup_path + '.aes'  
          
        with open(encrypted_path, 'wb') as f:  
            f.write(encrypted_data)  
              
        os.remove(backup_path)  
    else:  
        raise ValueError(f"Неподдерживаемый метод шифрования: {method}")  
          
    return encrypted_path, encryption_key  
  
def decrypt_backup(encrypted_path, encryption_key, method='fernet'):  
    """  
    Основная функция для дешифрования резервной копии  
      
    Args:  
        encrypted_path: Путь к зашифрованному файлу  
        encryption_key: Ключ дешифрования  
        method: Метод дешифрования ('fernet' или 'aes')  
      
    Returns:  
        str: Путь к дешифрованной резервной копии  
    """  
    if method == 'fernet':  
        encryptor = BackupEncryption()  
          
        if isinstance(encryption_key, str):  
            # Если передан пароль, восстанавливаем ключ из соли  
            salt_file = encrypted_path.replace('.encrypted.tar.gz', '.salt')  
            if os.path.exists(salt_file):  
                with open(salt_file, 'rb') as f:  
                    salt = f.read()  
                encryption_key, _ = encryptor.generate_key_from_password(encryption_key, salt)  
            else:  
                raise ValueError("Файл соли не найден для восстановления ключа")  
                  
        if encrypted_path.endswith('.encrypted.tar.gz'):  
            decrypted_path = encryptor.decrypt_directory(encrypted_path, encryption_key)  
        else:  
            decrypted_path = encryptor.decrypt_file(encrypted_path, encryption_key)  
              
    elif method == 'aes':  
        encryptor = AESEncryption()  
          
        with open(encrypted_path, 'rb') as f:  
            encrypted_data = f.read()  
              
        decrypted_data = encryptor.decrypt_data(encrypted_data, encryption_key)  
          
        # Восстановление исходного файла  
        decrypted_path = encrypted_path.replace('.aes', '')  
        with open(decrypted_path, 'wb') as f:  
            f.write(decrypted_data)  
              
        # Если это был архив, извлекаем его  
        if decrypted_path.endswith('.tar.gz'):  
            extract_dir = decrypted_path.replace('.tar.gz', '')  
            with tarfile.open(decrypted_path, 'r:gz') as tar:  
                tar.extractall(os.path.dirname(decrypted_path))  
            os.remove(decrypted_path)  
            decrypted_path = extract_dir  
    else:  
        raise ValueError(f"Неподдерживаемый метод дешифрования: {method}")  
          
    return decrypted_path  
  
def generate_encryption_key(password=None):  
    """Утилита для генерации ключа шифрования"""  
    encryptor = BackupEncryption()  
      
    if password:  
        key, salt = encryptor.generate_key_from_password(password)  
        return key, salt  
    else:  
        return encryptor.generate_random_key(), None  
  
def verify_encryption_key(encrypted_path, key, method='fernet'):  
    """Проверка корректности ключа шифрования"""  
    try:  
        if method == 'fernet':  
            fernet = Fernet(key)  
            # Пытаемся прочитать и дешифровать небольшую часть файла  
            with open(encrypted_path, 'rb') as f:  
                sample_data = f.read(1024)  # Читаем первые 1024 байта  
            fernet.decrypt(sample_data)  
            return True  
        elif method == 'aes':  
            # Для AES проверяем, можем ли мы дешифровать заголовок  
            with open(encrypted_path, 'rb') as f:  
                sample_data = f.read(1024)  
            encryptor = AESEncryption()  
            encryptor.decrypt_data(sample_data, key)  
            return True  
    except:  
        return False