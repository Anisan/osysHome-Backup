import subprocess  
import os  
from urllib.parse import urlparse  
  
class PostgreSQLHandler:  
    def __init__(self, database_uri):  
        self.db_type = 'postgresql'  
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
          
        env = os.environ.copy()  
        if self.password:  
            env['PGPASSWORD'] = self.password  
              
        cmd = [  
            'pg_dump',  
            '-h', self.host,  
            '-p', str(self.port),  
            '-U', self.username,  
            '-f', backup_file,  
            self.database  
        ]  
          
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)  
        if result.returncode == 0:  
            return backup_file  
        else:  
            raise Exception(f"PostgreSQL backup failed: {result.stderr}")