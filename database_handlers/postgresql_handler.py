import subprocess
import os
from urllib.parse import urlparse

class PostgreSQLHandler:
    def __init__(self, database_uri, logger, config=None):
        self.db_type = 'postgresql'
        self.logger = logger
        self.config = config or {}
        self.parse_uri(database_uri)  
          
    def parse_uri(self, uri):  
        parsed = urlparse(uri)  
        self.host = parsed.hostname  
        self.port = parsed.port or 5432  
        self.database = parsed.path[1:]  
        self.username = parsed.username  
        self.password = parsed.password  
          
    def create_backup(self, backup_path):  
        """Создание резервной копии PostgreSQL"""  
        os.makedirs(backup_path, exist_ok=True)  
        backup_file = os.path.join(backup_path, 'database.sql')  
        
        # Получаем путь к pg_dump из конфига или используем значение по умолчанию
        pg_dump_path = self.config.get('pg_dump_path', 'pg_dump')
          
        env = os.environ.copy()  
        if self.password:  
            env['PGPASSWORD'] = self.password
        # Устанавливаем UTF-8 кодировку для клиента PostgreSQL
        env['PGCLIENTENCODING'] = 'UTF8'
              
        cmd = [  
            pg_dump_path,  
            '-h', self.host,  
            '-p', str(self.port),  
            '-U', self.username,  
            '-f', backup_file,  
            self.database  
        ]  
          
        self.logger.info("PostgreSQLHandler: running pg_dump for database '%s'", self.database)
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
        ) 
        if result.returncode == 0:
            self.logger.debug("PostgreSQLHandler: backup created at %s", backup_file)
            return backup_file
        else:
            self.logger.error("PostgreSQLHandler: backup failed: %s", result.stderr)
            raise RuntimeError(f"PostgreSQL backup failed: {result.stderr}")
    
    def restore_backup(self, backup_path):
        """Восстановление из резервной копии PostgreSQL"""
        backup_file = os.path.join(backup_path, 'database.sql')
        if not os.path.exists(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
        
        # Получаем путь к psql из конфига или используем значение по умолчанию
        psql_path = self.config.get('psql_path', 'psql')
        
        env = os.environ.copy()
        if self.password:
            env['PGPASSWORD'] = self.password
        # Устанавливаем UTF-8 кодировку для клиента PostgreSQL
        env['PGCLIENTENCODING'] = 'UTF8'
        
        # Сначала очищаем базу данных (удаляем все объекты)
        # Используем psql для выполнения SQL команд
        cmd_drop = [
            psql_path,
            '-h', self.host,
            '-p', str(self.port),
            '-U', self.username,
            '-d', self.database,
            '-c', 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
        ]
        
        self.logger.debug("PostgreSQLHandler: dropping schema public before restore")
        result_drop = subprocess.run(
            cmd_drop,
            env=env,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False
        )
        if result_drop.returncode != 0:
            self.logger.warning("PostgreSQLHandler: failed to drop schema public: %s", result_drop.stderr)
        
        # Восстанавливаем из дампа
        cmd_restore = [
            psql_path,
            '-h', self.host,
            '-p', str(self.port),
            '-U', self.username,
            '-d', self.database,
            '-f', backup_file
        ]
        
        self.logger.info("PostgreSQLHandler: restoring database '%s' from %s", self.database, backup_file)
        result_restore = subprocess.run(
            cmd_restore,
            env=env,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
        )
        if result_restore.returncode == 0:
            self.logger.debug("PostgreSQLHandler: restore completed successfully")
            return True
        else:
            self.logger.error("PostgreSQLHandler: restore failed: %s", result_restore.stderr)
            raise RuntimeError(f"PostgreSQL restore failed: {result_restore.stderr}")