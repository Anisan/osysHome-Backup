import shutil
import os
  
class SQLiteHandler:
    def __init__(self, database_uri, logger):
        self.db_type = 'sqlite'
        self.db_path = database_uri.replace('sqlite:///', '')
        self.logger = logger
          
    def create_backup(self, backup_path):  
        """Создание резервной копии SQLite"""  
        os.makedirs(backup_path, exist_ok=True)
        backup_file = os.path.join(backup_path, 'database.db')
        shutil.copy2(self.db_path, backup_file)
        if self.logger:
            self.logger.debug("SQLiteHandler: backup copied to %s", backup_file)
        return backup_file  
          
    def restore_backup(self, backup_path):  
        """Восстановление из резервной копии SQLite"""  
        backup_file = os.path.join(backup_path, 'database.db')
        if os.path.exists(backup_file):
            shutil.copy2(backup_file, self.db_path)
            if self.logger:
                self.logger.debug("SQLiteHandler: restored from %s", backup_file)
            return True  
        return False