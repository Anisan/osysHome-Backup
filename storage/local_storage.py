import os  
import shutil  
import json  
from datetime import datetime  
  
class LocalStorage:  
    def __init__(self, config):  
        self.backup_dir = config.get('backup_directory', 'backups')  
        self.max_backups = config.get('max_backups', 10)  
          
    def list_backups(self):  
        """Получение списка резервных копий"""  
        if not os.path.exists(self.backup_dir):  
            return []  
              
        backups = []  
        for item in os.listdir(self.backup_dir):  
            backup_path = os.path.join(self.backup_dir, item)  
              
            if os.path.isdir(backup_path):  
                metadata_file = os.path.join(backup_path, 'metadata.json')  
                if os.path.exists(metadata_file):  
                    try:  
                        with open(metadata_file, 'r') as f:  
                            metadata = json.load(f)  
                            metadata['size'] = self._get_backup_size(backup_path)  
                            metadata['type'] = 'directory'  
                            backups.append(metadata)  
                    except Exception:  
                        continue  
            elif item.endswith(('.tar.gz', '.encrypted.tar.gz')):  
                stat = os.stat(backup_path)  
                metadata = {  
                    'name': item,  
                    'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),  
                    'size': stat.st_size,  
                    'type': 'archive',  
                    'encrypted': item.endswith('.encrypted.tar.gz')  
                }  
                backups.append(metadata)  
                  
        return sorted(backups, key=lambda x: x.get('created_at', ''), reverse=True)  
          
    def delete_backup(self, backup_name):  
        """Удаление резервной копии"""  
        backup_path = os.path.join(self.backup_dir, backup_name)  
          
        if os.path.exists(backup_path):  
            if os.path.isdir(backup_path):  
                shutil.rmtree(backup_path)  
            else:  
                os.remove(backup_path)  
            return True  
        return False  
          
    def cleanup_old_backups(self):  
        """Удаление старых резервных копий"""  
        backups = self.list_backups()  
        if len(backups) > self.max_backups:  
            for backup in backups[self.max_backups:]:  
                self.delete_backup(backup['name'])  
                  
    def _get_backup_size(self, backup_path):  
        """Вычисление размера резервной копии"""  
        if os.path.isfile(backup_path):  
            return os.path.getsize(backup_path)  
              
        total_size = 0  
        for dirpath, dirnames, filenames in os.walk(backup_path):  
            for filename in filenames:  
                filepath = os.path.join(dirpath, filename)  
                if os.path.exists(filepath):  
                    total_size += os.path.getsize(filepath)  
        return total_size  
          
    def get_backup_size(self, backup_name):  
        """Получение размера конкретной резервной копии"""  
        backup_path = os.path.join(self.backup_dir, backup_name)  
        return self._get_backup_size(backup_path)  
          
    def get_backup_info(self, backup_name):  
        """Получение информации о конкретной резервной копии"""  
        backup_path = os.path.join(self.backup_dir, backup_name)  
          
        if not os.path.exists(backup_path):  
            return None  
              
        if os.path.isdir(backup_path):  
            metadata_file = os.path.join(backup_path, 'metadata.json')  
            if os.path.exists(metadata_file):  
                with open(metadata_file, 'r') as f:  
                    return json.load(f)  
          
        # Для архивов возвращаем базовую информацию  
        stat = os.stat(backup_path)  
        return {  
            'name': backup_name,  
            'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),  
            'size': stat.st_size,  
            'type': 'archive'  
        }  
          
    def verify_backup(self, backup_name):  
        """Проверка целостности резервной копии"""  
        backup_info = self.get_backup_info(backup_name)  
        if not backup_info:  
            return False  
              
        backup_path = os.path.join(self.backup_dir, backup_name)  
          
        if os.path.isdir(backup_path):  
            required_files = ['metadata.json']  
            if backup_info.get('includes_files'):  
                required_files.append('files')  
            required_files.append('database')  
              
            for required_file in required_files:  
                if not os.path.exists(os.path.join(backup_path, required_file)):  
                    return False  
                      
        return True