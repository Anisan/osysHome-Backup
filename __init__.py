from app.core.main.BasePlugin import BasePlugin  
from app.database import session_scope  
from plugins.Backup.backup_manager import BackupManager  
import os  
  
class Backup(BasePlugin):  
    def __init__(self, app):  
        super().__init__(app, __name__)  
        self.name = "Backup"  
        self.title = "Система резервного копирования"  
        self.description = "Модуль для создания и восстановления резервных копий системы"  
        self.category = "Система"  
        self.actions = ["cycle", "widget"]  
          
        self.backup_manager = BackupManager(self.config)  
          
    def initialization(self):  
        """Инициализация плагина"""  
        # Создание директорий для резервных копий  
        backup_dir = self.config.get('backup_directory', 'backups')  
        os.makedirs(backup_dir, exist_ok=True)  
          
        self.logger.info("Backup plugin initialized")  
          
    def admin(self, request):  
        """Административный интерфейс"""  
        if request.method == 'POST':  
            action = request.form.get('action')  
              
            if action == 'create_backup':  
                return self._create_backup(request)  
            elif action == 'restore_backup':  
                return self._restore_backup(request)  
            elif action == 'delete_backup':  
                return self._delete_backup(request)  
                  
        # Получение списка резервных копий  
        backups = self.backup_manager.list_backups()  
          
        return self.render('backup_main.html',{
                                  'backups':backups,  
                                  'settings':self.config
                            })  
      
    def cyclic_task(self):  
        """Автоматическое создание резервных копий по расписанию"""  
        if self.config.get('auto_backup_enabled', False):  
            self.backup_manager.create_auto_backup()

    def _create_backup(self, request):  
        """Создание резервной копии через веб-интерфейс"""  
        try:  
            backup_name = request.form.get('backup_name')  
            include_files = request.form.get('include_files') == 'on'  
            
            backup_path = self.backup_manager.create_backup(  
                backup_name=backup_name,  
                include_files=include_files  
            )  
            
            return {'success': True, 'backup_path': backup_path}  
        except Exception as e:  
            self.logger.error(f"Error creating backup: {e}")  
            return {'success': False, 'error': str(e)}  
    
    def _restore_backup(self, request):  
        """Восстановление из резервной копии через веб-интерфейс"""  
        try:  
            backup_name = request.form.get('backup_name')  
            
            result = self.backup_manager.restore_backup(backup_name)  
            
            return {'success': True, 'restored': result}  
        except Exception as e:  
            self.logger.error(f"Error restoring backup: {e}")  
            return {'success': False, 'error': str(e)}  
    
    def _delete_backup(self, request):  
        """Удаление резервной копии через веб-интерфейс"""  
        try:  
            backup_name = request.form.get('backup_name')  
            
            result = self.backup_manager.deletre_backup(backup_name)  
            
            return {'success': True}  
        
                
        except Exception as e:  
            self.logger.error(f"Error deleting backup: {e}")  
            return {'success': False, 'error': str(e)}