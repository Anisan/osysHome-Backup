import os  
import json  
import shutil  
from datetime import datetime  
from app.configuration import Config  
from app.database import session_scope  
from .database_handlers import get_database_handler  
from .storage import get_storage_handler  
from .utils.compression import compress_backup  
from .utils.encryption import encrypt_backup, decrypt_backup  
  
class BackupManager:  
    def __init__(self, config):  
        self.config = config  
        self.db_handler = get_database_handler(Config.SQLALCHEMY_DATABASE_URI)  
        self.storage_handler = get_storage_handler(config)  
          
    def create_backup(self, backup_name=None, include_files=True):  
        """Создание резервной копии"""  
        if not backup_name:  
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"  
              
        backup_path = os.path.join(self.config.get('backup_directory', 'backups'), backup_name)  
        os.makedirs(backup_path, exist_ok=True)  
          
        # Создание резервной копии базы данных  
        db_backup_path = os.path.join(backup_path, 'database')  
        self.db_handler.create_backup(db_backup_path)  
          
        # Резервное копирование файлов системы  
        if include_files:  
            self._backup_system_files(backup_path)  
              
        # Создание метаданных  
        metadata = {  
            'name': backup_name,  
            'created_at': datetime.now().isoformat(),  
            'database_type': self.db_handler.db_type,  
            'includes_files': include_files,  
            'osyshome_version': self._get_system_version()  
        }  
          
        with open(os.path.join(backup_path, 'metadata.json'), 'w') as f:  
            json.dump(metadata, f, indent=2)  
              
        # Сжатие и шифрование  
        if self.config.get('compress_backups', True):  
            backup_path = compress_backup(backup_path)  
              
        if self.config.get('encrypt_backups', False):  
            backup_path = encrypt_backup(backup_path, self.config.get('encryption_key'))  
              
        return backup_path  
          
    def _backup_system_files(self, backup_path):  
        """Резервное копирование системных файлов"""  
        files_backup_path = os.path.join(backup_path, 'files')  
        os.makedirs(files_backup_path, exist_ok=True)  
          
        # Копирование конфигурационных файлов  
        config_files = ['config.yaml', 'sample_config.yaml']  
        for config_file in config_files:  
            if os.path.exists(config_file):  
                shutil.copy2(config_file, files_backup_path)  
                  
        # Копирование пользовательских данных  
        #user_dirs = ['uploads', 'logs', 'static/user']  
        #for user_dir in user_dirs:  
        #    if os.path.exists(user_dir):  
        #        dest_path = os.path.join(files_backup_path, user_dir)  
        #        if os.path.isdir(user_dir):  
        #            shutil.copytree(user_dir, dest_path)  
        #        else:  
        #            shutil.copy2(user_dir, dest_path)  
                      
        # Копирование плагинов (если требуется)  
        if self.config.get('backup_plugins', False):  
            plugins_dir = 'plugins'  
            if os.path.exists(plugins_dir):  
                shutil.copytree(plugins_dir, os.path.join(files_backup_path, 'plugins'))  
                  
    def _get_system_version(self):  
        """Получение версии системы osysHome"""  
        try:  
            import subprocess  
            result = subprocess.run(['git', 'describe', '--tags'],   
                                  capture_output=True, text=True)  
            if result.returncode == 0:  
                return result.stdout.strip()  
        except:  
            pass  
        return "unknown"  
          
    def restore_backup(self, backup_name):  
        """Восстановление из резервной копии"""  
        backup_path = os.path.join(self.config.get('backup_directory', 'backups'), backup_name)  
          
        # Проверка на зашифрованную резервную копию  
        if backup_name.endswith('.encrypted.tar.gz'):  
            if not self.config.get('encryption_key'):  
                raise ValueError("Encryption key required for encrypted backup")  
            backup_path = decrypt_backup(backup_path, self.config.get('encryption_key'))  
              
        if not os.path.exists(backup_path):  
            raise FileNotFoundError(f"Backup {backup_name} not found")  
              
        # Загрузка метаданных  
        metadata_file = os.path.join(backup_path, 'metadata.json')  
        if not os.path.exists(metadata_file):  
            raise ValueError("Backup metadata not found")  
              
        with open(metadata_file, 'r') as f:  
            metadata = json.load(f)  
              
        # Восстановление базы данных  
        db_backup_path = os.path.join(backup_path, 'database')  
        self.db_handler.restore_backup(db_backup_path)  
          
        # Восстановление файлов системы  
        if metadata.get('includes_files', False):  
            self._restore_system_files(backup_path)  
              
        # Очистка кэша объектов после восстановления  
        from app.core.main.ObjectsStorage import objects_storage  
        objects_storage.clear()  
          
        return True  
          
    def _restore_system_files(self, backup_path):  
        """Восстановление системных файлов"""  
        files_backup_path = os.path.join(backup_path, 'files')  
          
        if os.path.exists(files_backup_path):  
            # Восстановление конфигурационных файлов  
            for item in os.listdir(files_backup_path):  
                item_path = os.path.join(files_backup_path, item)  
                if os.path.isfile(item_path) and item.endswith('.yaml'):  
                    shutil.copy2(item_path, item)  
                elif os.path.isdir(item_path):  
                    if os.path.exists(item):  
                        shutil.rmtree(item)  
                    shutil.copytree(item_path, item)  
                      
    # ДЕЛЕГИРОВАНИЕ К STORAGE_HANDLER  
    def list_backups(self):  
        """Получение списка резервных копий - делегирование к storage_handler"""  
        return self.storage_handler.list_backups()  
          
    def delete_backup(self, backup_name):  
        """Удаление резервной копии - делегирование к storage_handler"""  
        return self.storage_handler.delete_backup(backup_name)  
          
    def cleanup_old_backups(self):  
        """Очистка старых резервных копий - делегирование к storage_handler"""  
        return self.storage_handler.cleanup_old_backups()  
          
    def get_backup_size(self, backup_name):  
        """Получение размера резервной копии - делегирование к storage_handler"""  
        return self.storage_handler.get_backup_size(backup_name)  
          
    def create_auto_backup(self):  
        """Автоматическое создание резервной копии"""  
        try:  
            backup_name = f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"  
            backup_path = self.create_backup(backup_name, include_files=True)  
              
            # Очистка старых автоматических резервных копий через storage_handler  
            self.cleanup_old_backups()  
              
            return backup_path  
        except Exception as e:  
            print(f"Auto backup failed: {e}")  
            return None  
              
    def get_backup_info(self, backup_name):  
        """Получение информации о резервной копии - делегирование к storage_handler"""  
        return self.storage_handler.get_backup_info(backup_name)  
          
    def verify_backup(self, backup_name):  
        """Проверка целостности резервной копии - делегирование к storage_handler"""  
        return self.storage_handler.verify_backup(backup_name)