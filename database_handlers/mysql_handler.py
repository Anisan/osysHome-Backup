import subprocess  
import os  
from urllib.parse import urlparse  
  
class MySQLHandler:  
    def __init__(self, database_uri):  
        self.db_type = 'mysql'  
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
          
        cmd = [  
            'mysqldump',  
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
              
        with open(backup_file, 'w') as f:  
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)  
              
        if result.returncode == 0:  
            return backup_file  
        else:  
            raise Exception(f"MySQL backup failed: {result.stderr}")