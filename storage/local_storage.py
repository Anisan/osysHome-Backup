import os  
import shutil  
import json
from datetime import datetime, timedelta  
  
class LocalStorage:  
    def __init__(self, config):  
        self.config = config
        self.backup_dir = config.get('backup_directory', 'backups')  
        self.max_backups = config.get('max_backups', 10)
        self.storage_duration_days = config.get('storage_duration_days', 30)
    
    def update_config(self, config):
        """Обновление конфигурации storage handler"""
        self.config = config
        self.backup_dir = config.get('backup_directory', 'backups')
        self.max_backups = config.get('max_backups', 10)
        self.storage_duration_days = config.get('storage_duration_days', 30)  
          
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
                        with open(metadata_file, 'r', encoding='utf-8') as f:  
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
                
                # Читаем только из внешнего .metadata.json (быстро)
                # Если файла нет - метаданные содержимого не показываем
                external_metadata_path = backup_path + '.metadata.json'
                if os.path.exists(external_metadata_path):
                    try:
                        with open(external_metadata_path, 'r', encoding='utf-8') as f:
                            archive_metadata = json.load(f)
                            metadata.update({
                                'database_type': archive_metadata.get('database_type'),
                                'includes_database': archive_metadata.get('includes_database', True),
                                'includes_cache': archive_metadata.get('includes_cache', False),
                                'includes_files': archive_metadata.get('includes_files', False),
                                'includes_user_files': archive_metadata.get('includes_user_files', False),
                                'backup_resources': archive_metadata.get('backup_resources', []),
                                'osyshome_version': archive_metadata.get('osyshome_version')
                            })
                    except Exception:
                        pass
                
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
                # Также удаляем внешний файл метаданных
                external_metadata = backup_path + '.metadata.json'
                if os.path.exists(external_metadata):
                    try:
                        os.remove(external_metadata)
                    except Exception:
                        pass
            return True  
        return False  
          
    def cleanup_old_backups(self):  
        """Удаление старых резервных копий с учетом количества и длительности хранения"""  
        backups = self.list_backups()  
        if not backups:
            return
        
        # Вычисляем дату истечения срока хранения
        expiration_date = datetime.now() - timedelta(days=self.storage_duration_days)
        
        # Список копий для удаления
        to_delete = []
        
        # Обновляем значения из конфигурации на случай, если они изменились
        if hasattr(self, 'config'):
            self.max_backups = self.config.get('max_backups', self.max_backups)
            self.storage_duration_days = self.config.get('storage_duration_days', self.storage_duration_days)
            expiration_date = datetime.now() - timedelta(days=self.storage_duration_days)
        
        # Проверяем каждую резервную копию
        for backup_index, backup in enumerate(backups):
            should_delete = False
            
            # Проверка по количеству (удаляем самые старые, если превышен лимит)
            if backup_index >= self.max_backups:
                should_delete = True
            
            # Проверка по длительности хранения
            try:
                created_at_str = backup.get('created_at', '')
                if created_at_str:
                    # Парсим дату создания
                    try:
                        # Пробуем ISO формат с временной зоной
                        if 'T' in created_at_str:
                            # Убираем Z и добавляем +00:00 для UTC
                            if created_at_str.endswith('Z'):
                                created_at_str = created_at_str.replace('Z', '+00:00')
                            created_at = datetime.fromisoformat(created_at_str)
                        else:
                            # Просто дата без времени
                            created_at = datetime.fromisoformat(created_at_str)
                        
                        # Если дата создания раньше даты истечения
                        if created_at.replace(tzinfo=None) < expiration_date:
                            should_delete = True
                    except (ValueError, AttributeError):
                        # Если не удалось распарсить дату, используем время модификации файла
                        backup_path = os.path.join(self.backup_dir, backup['name'])
                        if os.path.exists(backup_path):
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(backup_path))
                            if file_mtime < expiration_date:
                                should_delete = True
            except Exception:
                # Если не удалось распарсить дату, используем время модификации файла
                backup_path = os.path.join(self.backup_dir, backup['name'])
                if os.path.exists(backup_path):
                    try:
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(backup_path))
                        if file_mtime < expiration_date:
                            should_delete = True
                    except Exception:
                        pass
            
            if should_delete:
                to_delete.append(backup)
        
        # Удаляем найденные копии
        for backup in to_delete:
            try:
                self.delete_backup(backup['name'])
            except Exception as e:
                # Логируем ошибку, но продолжаем удаление других копий
                pass  
                  
    def _get_backup_size(self, backup_path):  
        """Вычисление размера резервной копии"""  
        if os.path.isfile(backup_path):  
            return os.path.getsize(backup_path)  
              
        total_size = 0  
        for dirpath, _dirnames, filenames in os.walk(backup_path):  
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
                with open(metadata_file, 'r', encoding='utf-8') as f:  
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