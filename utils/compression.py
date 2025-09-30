import tarfile  
import os  
import shutil  
  
def compress_backup(backup_path):  
    """Сжатие резервной копии в tar.gz архив"""  
    archive_path = f"{backup_path}.tar.gz"  
      
    with tarfile.open(archive_path, 'w:gz') as tar:  
        tar.add(backup_path, arcname=os.path.basename(backup_path))  
          
    # Удаление исходной директории  
    shutil.rmtree(backup_path)  
      
    return archive_path  
  
def decompress_backup(archive_path, extract_to):  
    """Распаковка архива резервной копии"""  
    with tarfile.open(archive_path, 'r:gz') as tar:  
        tar.extractall(extract_to)  
          
    return os.path.join(extract_to, os.path.basename(archive_path).replace('.tar.gz', ''))