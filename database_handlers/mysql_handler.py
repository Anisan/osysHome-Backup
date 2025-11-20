import subprocess
import os
from urllib.parse import urlparse

class MySQLHandler:
    def __init__(self, database_uri, logger, config=None):
        self.db_type = 'mysql'
        self.logger = logger
        self.config = config or {}
        self.parse_uri(database_uri)  
          
    def parse_uri(self, uri):  
        parsed = urlparse(uri)  
        self.host = parsed.hostname or 'localhost'  
        self.port = parsed.port or 3306  
        self.database = parsed.path[1:]  
        self.username = parsed.username  
        self.password = parsed.password  
          
    def create_backup(self, backup_path):  
        """Создание резервной копии MySQL"""  
        os.makedirs(backup_path, exist_ok=True)  
        backup_file = os.path.join(backup_path, 'database.sql')  
        
        # Получаем путь к mysqldump из конфига или используем значение по умолчанию
        mysqldump_path = self.config.get('mysqldump_path', 'mysqldump')
          
        cmd = [  
            mysqldump_path,  
            f'--host={self.host}',  
            f'--port={self.port}',  
            f'--user={self.username}',  
            '--single-transaction',  
            '--routines',  
            '--triggers',  
            self.database  
        ]  
          
        if self.password:  
            cmd.insert(-1, f'--password={self.password}')  
              
        self.logger.info("MySQLHandler: running mysqldump for database '%s'", self.database)
        with open(backup_file, 'w', encoding='utf-8') as f:  
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=False
            )  
              
        if result.returncode == 0:  
            self.logger.debug("MySQLHandler: backup created at %s", backup_file)
            return backup_file  
        else:  
            self.logger.error("MySQLHandler: backup failed: %s", result.stderr)
            raise RuntimeError(f"MySQL backup failed: {result.stderr}")
    
    def restore_backup(self, backup_path):
        """Восстановление из резервной копии MySQL"""
        backup_file = os.path.join(backup_path, 'database.sql')
        if not os.path.exists(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
        
        # Получаем путь к mysql из конфига или используем значение по умолчанию
        mysql_path = self.config.get('mysql_path', 'mysql')
        
        cmd = [
            mysql_path,
            f'--host={self.host}',
            f'--port={self.port}',
            f'--user={self.username}',
            self.database
        ]
        
        if self.password:
            cmd.insert(-1, f'--password={self.password}')
        
        self.logger.info("MySQLHandler: restoring database '%s' from %s", self.database, backup_file)
        with open(backup_file, 'r', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=False
            )
        
        if result.returncode == 0:
            self.logger.debug("MySQLHandler: restore completed successfully")
            return True
        else:
            self.logger.error("MySQLHandler: restore failed: %s", result.stderr)
            raise RuntimeError(f"MySQL restore failed: {result.stderr}")