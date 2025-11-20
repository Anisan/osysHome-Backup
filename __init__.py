from app.core.main.BasePlugin import BasePlugin
from app.core.main.PluginsHelper import plugins
from app.database import session_scope
from app.configuration import Config
from plugins.Backup.backup_manager import BackupManager
from flask import jsonify, send_file, request as flask_request
from threading import Thread
from werkzeug.utils import secure_filename
import os
  
class Backup(BasePlugin):  
    def __init__(self, app):  
        super().__init__(app, __name__)  
        self.name = "Backup"  
        self.title = "Система резервного копирования"  
        self.description = "Модуль для создания и восстановления резервных копий системы"  
        self.category = "Система"  
        self.actions = ["cycle", "widget"]  
          
        self._ensure_config_defaults()
        self.backup_manager = BackupManager(self.config, self.logger)  
          
    def initialization(self):  
        """Инициализация плагина"""  
        # Создание директорий для резервных копий  
        backup_dir = self.config.get('backup_directory', 'backups')  
        os.makedirs(backup_dir, exist_ok=True)  
          
        self.logger.info("Backup plugin initialized")  
    
    def admin(self, request):
        """Административный интерфейс"""  
        action = request.args.get('action') or request.form.get('action')

        if action == 'download':
            backup_name = request.args.get('backup_name')
            if backup_name:
                return self._download_backup(backup_name)
            
        if request.method == 'POST':  
              
            if action == 'create_backup':  
                return self._create_backup(request)  
            elif action == 'restore_backup':  
                return self._restore_backup(request)  
            elif action == 'delete_backup':  
                return self._delete_backup(request)
            elif action == 'upload_backup':
                return self._upload_backup(request)
                  
        # Получение списка резервных копий  
        backups = self.backup_manager.list_backups()  
          
        return self.render('backup_main.html',{
                                  'backups':backups,  
                                  'settings':self.config,
                                  'format_size': self._format_size
                            })  
      
    def cyclic_task(self):  
        """Автоматическое создание резервных копий по расписанию"""  
        if self.config.get('auto_backup_enabled', False):  
            self.backup_manager.create_auto_backup()
    
    @staticmethod
    def _format_size(size_bytes):
        """Форматирование размера в удобочитаемый формат"""
        if not size_bytes or size_bytes == 0:
            return "0 B"
        
        size_bytes = int(size_bytes)
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        if i == 0:
            return f"{size_bytes} {size_names[i]}"
        else:
            return f"{size_bytes:.2f} {size_names[i]}"

    def _create_backup(self, request):  
        """Создание резервной копии через веб-интерфейс"""  
        backup_name = request.form.get('backup_name')  
        include_database = bool(request.form.get('include_database'))
        include_cache = bool(request.form.get('include_cache'))
        include_files = request.form.get('include_files') == 'on'
        include_plugins = include_files and bool(request.form.get('include_plugins'))
        include_user_files = bool(request.form.get('include_user_files'))
        include_app_core = include_files and bool(request.form.get('include_app_core'))
        
        # Запускаем создание бэкапа в отдельном потоке
        def backup_thread():
            def progress_callback(progress, message):
                """Callback для отправки прогресса через WebSocket"""
                self.sendDataToWebsocket('backup_progress', {
                    'progress': progress,
                    'message': message,
                    'backup_name': backup_name or 'auto'
                })
            
            try:
                backup_path = self.backup_manager.create_backup(
                    backup_name=backup_name,
                    include_database=include_database,
                    include_cache=include_cache,
                    include_files=include_files,
                    include_plugins=include_plugins,
                    include_user_files=include_user_files,
                    include_app_core=include_app_core,
                    progress_callback=progress_callback
                )
                
                # Отправляем финальное сообщение об успехе
                self.sendDataToWebsocket('backup_progress', {
                    'progress': 100,
                    'message': 'Резервная копия успешно создана',
                    'backup_path': backup_path,
                    'success': True,
                    'backup_name': backup_name or 'auto'
                })
            except Exception as e:
                self.logger.error("Error creating backup: %s", e)
                # Отправляем сообщение об ошибке
                self.sendDataToWebsocket('backup_progress', {
                    'progress': 0,
                    'message': f'Ошибка создания резервной копии: {str(e)}',
                    'success': False,
                    'error': str(e),
                    'backup_name': backup_name or 'auto'
                })
        
        # Запускаем поток
        thread = Thread(target=backup_thread, daemon=True)
        thread.start()
        
        # Сразу возвращаем успешный ответ, что процесс запущен
        return jsonify({
            'success': True, 
            'message': 'Процесс создания резервной копии запущен',
            'started': True
        })  
    
    def _restore_backup(self, request):  
        """Восстановление из резервной копии через веб-интерфейс"""  
        backup_name = request.form.get('backup_name')  

        stopped_cycles = self._stop_all_cycles()
        
        # Запускаем восстановление в отдельном потоке
        def restore_thread():
            def progress_callback(progress, message):
                """Callback для отправки прогресса через WebSocket"""
                self.sendDataToWebsocket('restore_progress', {
                    'progress': progress,
                    'message': message,
                    'backup_name': backup_name
                })
            
            try:
                self.backup_manager.restore_backup(
                    backup_name=backup_name,
                    progress_callback=progress_callback
                )
                
                # Отправляем финальное сообщение об успехе
                self.sendDataToWebsocket('restore_progress', {
                    'progress': 100,
                    'message': 'Восстановление успешно завершено',
                    'success': True,
                    'backup_name': backup_name
                })
            except Exception as e:
                self.logger.error("Error restoring backup: %s", e)
                # Отправляем сообщение об ошибке
                self.sendDataToWebsocket('restore_progress', {
                    'progress': 0,
                    'message': f'Ошибка восстановления: {str(e)}',
                    'success': False,
                    'error': str(e),
                    'backup_name': backup_name
                })
            finally:
                self._resume_cycles(stopped_cycles)
        
        # Запускаем поток
        thread = Thread(target=restore_thread, daemon=True)
        thread.start()
        
        # Сразу возвращаем успешный ответ, что процесс запущен
        return jsonify({
            'success': True, 
            'message': 'Процесс восстановления запущен',
            'started': True
        })  
    
    def _delete_backup(self, request):  
        """Удаление резервной копии через веб-интерфейс"""  
        try:  
            backup_name = request.form.get('backup_name')  
            
            self.backup_manager.delete_backup(backup_name)  
            
            return jsonify({'success': True})  
        except Exception as e:  
            self.logger.error("Error deleting backup: %s", e)
            return jsonify({'success': False, 'error': str(e)})
    
    def _download_backup(self, backup_name):
        """Скачивание резервной копии"""
        try:
            backup_dir = self.config.get('backup_directory', 'backups')
            backup_path = os.path.join(Config.APP_DIR, backup_dir, backup_name)
            
            if not os.path.exists(backup_path):
                self.logger.error("Backup not found: %s", backup_name)
                return jsonify({'success': False, 'error': 'Backup not found'}), 404
            
            self.logger.info("Downloading backup: %s", backup_name)
            return send_file(
                backup_path,
                as_attachment=True,
                download_name=backup_name,
                mimetype='application/gzip'
            )
        except Exception as e:
            self.logger.error("Error downloading backup: %s", e)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def _upload_backup(self, request):
        """Загрузка резервной копии на сервер"""
        try:
            if 'backup_file' not in request.files:
                return jsonify({'success': False, 'error': 'No file provided'})
            
            file = request.files['backup_file']
            
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'})
            
            # Проверяем расширение файла
            if not (file.filename.endswith('.tar.gz') or file.filename.endswith('.encrypted.tar.gz')):
                return jsonify({'success': False, 'error': 'Invalid file format. Only .tar.gz or .encrypted.tar.gz files are allowed'})
            
            # Безопасное имя файла
            filename = secure_filename(file.filename)
            
            # Путь для сохранения
            backup_dir = self.config.get('backup_directory', 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, filename)
            
            # Проверяем, не существует ли уже файл с таким именем
            if os.path.exists(backup_path):
                return jsonify({'success': False, 'error': f'Backup with name "{filename}" already exists'})
            
            # Сохраняем файл
            file.save(backup_path)
            
            self.logger.info("Backup uploaded successfully: %s", filename)
            return jsonify({
                'success': True,
                'message': f'Backup "{filename}" uploaded successfully',
                'backup_name': filename
            })
            
        except Exception as e:
            self.logger.error("Error uploading backup: %s", e)
            return jsonify({'success': False, 'error': str(e)})

    def _stop_all_cycles(self):
        """Останавливаем циклы всех модулей перед восстановлением"""
        stopped = []
        for name, info in plugins.items():
            plugin = info["instance"]
            if 'cycle' not in getattr(plugin, 'actions', []):
                continue
            if plugin.is_alive():
                try:
                    self.logger.info("Stopping cycle for plugin '%s' before restore", name)
                    plugin.stop_cycle()
                    stopped.append(name)
                except Exception as exc:
                    self.logger.error("Failed to stop cycle for plugin '%s': %s", name, exc)
        return stopped

    def _resume_cycles(self, plugin_names):
        """Возвращаем в исходное состояние циклы после восстановления"""
        for name in plugin_names:
            info = plugins.get(name)
            if not info:
                continue
            plugin = info["instance"]
            try:
                self.logger.info("Restarting cycle for plugin '%s' after restore", name)
                plugin.start_cycle()
            except Exception as exc:
                self.logger.error("Failed to restart cycle for plugin '%s': %s", name, exc)

    def _ensure_config_defaults(self):
        """Вставка значений по умолчанию для новых параметров резервного копирования."""
        if self.config is None:
            self.config = {}

        defaults = {
            'backup_database': True,
            'backup_cache': False,
            'backup_plugins': False,
            'backup_user_files': False,
            'backup_app_core': False,
        }

        paths = {
            'cache_directory': Config.CACHE_FILE_PATH,
            'plugins_directory': Config.PLUGINS_FOLDER,
            'user_files_directory': Config.FILES_DIR,
            'app_core_directory': os.path.join(Config.APP_DIR, 'app'),
        }

        updated = False
        for key, value in defaults.items():
            if self.config.get(key) is None:
                self.config[key] = value
                updated = True
        for key, value in paths.items():
            if self.config.get(key) != value:
                self.config[key] = value
                updated = True

        if updated:
            self.logger.debug("Backup plugin config updated with defaults: %s", defaults)
            self.saveConfig()