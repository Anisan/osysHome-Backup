import json
import tarfile  
import os  
import shutil  

def read_metadata_from_archive(archive_path):
    """Прочитать metadata.json из tar.gz без полной распаковки."""
    with tarfile.open(archive_path, 'r:gz') as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            parts = member.name.replace('\\', '/').split('/')
            if len(parts) == 2 and parts[1] == 'metadata.json':
                fileobj = tar.extractfile(member)
                if fileobj:
                    return json.load(fileobj)
    return None

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