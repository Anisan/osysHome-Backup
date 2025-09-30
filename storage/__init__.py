from plugins.Backup.storage.local_storage import LocalStorage  
  
def get_storage_handler(config):  
    """Фабрика для создания обработчика хранилища"""  
    storage_type = config.get('storage_type', 'local')  
      
    if storage_type == 'local':  
        return LocalStorage(config)  
    else:  
        raise ValueError(f"Unsupported storage type: {storage_type}")