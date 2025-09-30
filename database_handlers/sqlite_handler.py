import sqlite3  
import shutil  
import os  
from app.configuration import Config  
  
class SQLiteHandler:  
    def __init__(self, database_uri):  
        self.db_type = 'sqlite'  
        self.db_path = database_uri.replace('sqlite:///', '')  
          
    def create_backup(self, backup_path):  
        """Создание резервной копии SQLite"""  
        os.makedirs(backup_path, exist_ok=True)  
        backup_file = os.path.join(backup_path, 'database.db')  
        shutil.copy2(self.db_path, backup_file)  
        return backup_file  
          
    def restore_backup(self, backup_path):  
        """Восстановление из резервной копии SQLite"""  
        backup_file = os.path.join(backup_path, 'database.db')  
        if os.path.exists(backup_file):  
            shutil.copy2(backup_file, self.db_path)  
            return True  
        return False