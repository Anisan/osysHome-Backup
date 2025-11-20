from urllib.parse import urlparse  
from .sqlite_handler import SQLiteHandler  
from .mysql_handler import MySQLHandler  
from .postgresql_handler import PostgreSQLHandler  
  
def get_database_handler(database_uri, logger):  
    """Фабрика для создания обработчика базы данных"""  
    parsed = urlparse(database_uri)  
    scheme = parsed.scheme.lower()  
      
    if scheme == 'sqlite':  
        return SQLiteHandler(database_uri, logger)  
    elif scheme == 'mysql':  
        return MySQLHandler(database_uri, logger)  
    elif scheme == 'postgresql':  
        return PostgreSQLHandler(database_uri, logger)  
    else:  
        raise ValueError(f"Unsupported database type: {scheme}")