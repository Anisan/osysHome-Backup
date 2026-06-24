from app import safe_translate as _
from app.core.main.BasePlugin import BasePlugin
from app.core.main.PluginsHelper import plugins
from app.core.lib.common import addNotify, CategoryNotify
from app.database import session_scope
from app.configuration import Config
from plugins.Backup.backup_manager import BackupManager
from plugins.Backup.database_handlers import get_database_handler
from plugins.Backup.storage import get_storage_handler
from flask import jsonify, send_file, request as flask_request
from threading import Thread
from werkzeug.utils import secure_filename
import os
  
class Backup(BasePlugin):  
    def __init__(self, app):  
        super().__init__(app, __name__)  
        self.name = "Backup"  
        self.title = "Backup"  
        self.description = "Module for creating and restoring system backups"  
        self.category = "System"  
        self.version = "1.4"
        self.actions = ["widget"]  
          
        self._ensure_config_defaults()
        self.backup_manager = BackupManager(self.config, self.logger)
        
        # Создаем или обновляем cron задачу при инициализации
        self._setup_auto_backup_task()  
          
    def initialization(self):  
        """Инициализация плагина"""  
        # Создание директорий для резервных копий  
        backup_dir = self.config.get('backup_directory', 'backups')  
        os.makedirs(backup_dir, exist_ok=True)  
        
        # Настраиваем автоматическое резервное копирование при инициализации
        self._setup_auto_backup_task()
          
        self.logger.info("Backup plugin initialized")
    
    def widget(self, name: str = None):
        """Виджет для отображения на панели управления"""
        from flask import render_template
        from app.core.lib.common import getJob
        
        content = {}
        
        # Получаем список резервных копий
        backups = self.backup_manager.list_backups()
        content['count'] = len(backups)
        
        # Информация о последней резервной копии
        if backups:
            latest_backup = backups[0]  # Первый элемент - самая последняя копия
            content['latest_backup'] = {
                'name': latest_backup.get('name', 'N/A'),
                'created_at': latest_backup.get('created_at', 'N/A'),
                'size': latest_backup.get('size', 0),
                'includes_database': latest_backup.get('includes_database', False),
                'includes_cache': latest_backup.get('includes_cache', False),
                'includes_files': latest_backup.get('includes_files', False),
                'includes_user_files': latest_backup.get('includes_user_files', False),
                'backup_resources': latest_backup.get('backup_resources', []),
                'encrypted': latest_backup.get('encrypted', False),
            }
        else:
            content['latest_backup'] = None
        
        # Статус автоматического резервного копирования
        job_info = getJob('Backup_auto_periodic')
        content['auto_backup_enabled'] = job_info is not None
        
        if job_info:
            runtime = job_info.get('runtime')
            if runtime:
                content['next_run'] = runtime.strftime('%Y-%m-%d %H:%M')
        
        content['format_size'] = self._format_size
        
        return render_template("widget_backup.html", **content)  
    
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
            elif action == 'save_settings':
                return self._save_settings(request)
            elif action == 'save_auto_backup_settings':
                return self._save_auto_backup_settings(request)
            elif action == 'get_auto_backup_settings':
                return self._get_auto_backup_settings()
            elif action == 'save_storage_settings':
                return self._save_storage_settings(request)
            elif action == 'get_backup_metadata':
                return self._get_backup_metadata(request)
                  
        # Получение списка резервных копий  
        backups = self.backup_manager.list_backups()  
        
        # Определяем тип текущей базы данных
        db_type = self.backup_manager.db_handler.db_type if self.backup_manager.db_handler else 'unknown'
        
        # Получаем информацию о cron задаче
        from app.core.lib.common import getJob
        job_info = getJob('Backup_auto_periodic')
        auto_backup_enabled = job_info is not None
        auto_backup_crontab = job_info.get('crontab', '0 2 * * *') if job_info else '0 2 * * *'
          
        return self.render('backup_main.html',{
                                  'backups':backups,  
                                  'settings':self.config,
                                  'format_size': self._format_size,
                                  'db_type': db_type,
                                  'auto_backup_enabled': auto_backup_enabled,
                                  'auto_backup_crontab': auto_backup_crontab,
                                  'max_backups': self.config.get('max_backups', 10),
                                  'storage_duration_days': self.config.get('storage_duration_days', 30)
                            })  
      
    def create_auto_backup(self):
        """Создание автоматической резервной копии (вызывается через задачу)"""
        try:
            from datetime import datetime
            self.logger.info("Starting automatic backup creation")
            
            # Используем настройки по умолчанию из конфигурации
            include_database = self.config.get('backup_database', True)
            include_cache = self.config.get('backup_cache', False)
            include_plugins = self.config.get('backup_plugins', False)
            include_user_files = self.config.get('backup_user_files', False)
            include_app_core = self.config.get('backup_app_core', False)
            include_venv = self.config.get('backup_venv', False)
            
            # Генерируем имя с префиксом auto_backup_
            backup_name = f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            backup_path = self.backup_manager.create_backup(
                backup_name=backup_name,
                include_database=include_database,
                include_cache=include_cache,
                include_files=(include_plugins or include_app_core or include_venv),
                include_plugins=include_plugins,
                include_user_files=include_user_files,
                include_app_core=include_app_core,
                include_venv=include_venv,
                progress_callback=None
            )
            
            self.logger.info("Automatic backup created successfully: %s", backup_path)
            
            # Очистка старых автоматических резервных копий
            self.backup_manager.cleanup_old_backups()
            
            return True
        except Exception as e:
            self.logger.error("Error creating automatic backup: %s", e)
            addNotify(
                "Ошибка автоматического резервного копирования",
                f"Не удалось создать резервную копию автоматически: {e}",
                CategoryNotify.Error,
                self.name,
            )
            return False
    
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
        include_venv = include_files and bool(request.form.get('include_venv'))
        
        # Сохраняем состояние галочек в конфигурацию для использования по умолчанию
        self.config['backup_database'] = include_database
        self.config['backup_cache'] = include_cache
        self.config['backup_plugins'] = include_plugins
        self.config['backup_user_files'] = include_user_files
        self.config['backup_app_core'] = include_app_core
        self.config['backup_venv'] = include_venv
        self.saveConfig()
        
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
                    include_venv=include_venv,
                    progress_callback=progress_callback
                )
                
                # Очистка старых резервных копий после успешного создания
                self.backup_manager.cleanup_old_backups()
                
                # Отправляем финальное сообщение об успехе
                self.sendDataToWebsocket('backup_progress', {
                    'progress': 100,
                    'message': _('Backup created successfully'),
                    'backup_path': backup_path,
                    'success': True,
                    'backup_name': backup_name or 'auto'
                })
            except Exception as e:
                self.logger.error("Error creating backup: %s", e)
                # Отправляем сообщение об ошибке
                self.sendDataToWebsocket('backup_progress', {
                    'progress': 0,
                    'message': _('Error creating backup') + f": {str(e)}",
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
            'message': _('Starting backup process...'),
            'started': True
        })  
    
    def _restore_backup(self, request):  
        """Восстановление из резервной копии через веб-интерфейс"""  
        backup_name = request.form.get('backup_name')
        restore_options = self._parse_restore_options(request)

        if not any(restore_options.values()):
            return jsonify({
                'success': False,
                'error': _('At least one component must be selected'),
            }), 400
        
        # Запускаем восстановление в отдельном потоке
        def restore_thread():
            def progress_callback(progress, message):
                """Callback для отправки прогресса через WebSocket"""
                self.sendDataToWebsocket('restore_progress', {
                    'progress': progress,
                    'message': message,
                    'backup_name': backup_name
                })

            progress_callback(1, _('Stopping plugin cycles...'))
            stopped_cycles, failed_cycles = self._stop_all_cycles()
            if failed_cycles:
                modules = ', '.join(
                    f"{item['name']} ({item['detail']})"
                    for item in failed_cycles
                )
                error_message = _('Cannot restore: the following modules could not be stopped: %(modules)s') % {
                    'modules': modules,
                }
                self.logger.error(error_message)
                self.sendDataToWebsocket('restore_progress', {
                    'progress': 0,
                    'message': error_message,
                    'success': False,
                    'error': error_message,
                    'backup_name': backup_name,
                })
                self._resume_cycles(stopped_cycles)
                return
            
            try:
                if restore_options.get('database'):
                    from plugins.Backup.database_handlers.sqlite_handler import (
                        _release_app_sqlite_connections,
                    )
                    _release_app_sqlite_connections()

                self.backup_manager.restore_backup(
                    backup_name=backup_name,
                    progress_callback=progress_callback,
                    restore_options=restore_options,
                )
                
                # Отправляем финальное сообщение об успехе
                self.sendDataToWebsocket('restore_progress', {
                    'progress': 100,
                    'message': _('Restore completed successfully'),
                    'success': True,
                    'backup_name': backup_name
                })
            except Exception as e:
                self.logger.error("Error restoring backup: %s", e)
                # Отправляем сообщение об ошибке
                self.sendDataToWebsocket('restore_progress', {
                    'progress': 0,
                    'message': _('Error restoring backup') + f": {str(e)}",
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
            'message': _('Starting restore process...'),
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

            try:
                metadata = self.backup_manager.get_backup_metadata(filename)
                if metadata:
                    self.logger.info(
                        "Backup upload: metadata loaded for %s (database=%s, cache=%s)",
                        filename,
                        metadata.get('includes_database'),
                        metadata.get('includes_cache'),
                    )
            except Exception as exc:
                self.logger.warning(
                    "Backup upload: could not read metadata for %s: %s",
                    filename,
                    exc,
                )
            
            self.logger.info("Backup uploaded successfully: %s", filename)
            return jsonify({
                'success': True,
                'message': f'Backup "{filename}" uploaded successfully',
                'backup_name': filename
            })
            
        except Exception as e:
            self.logger.error("Error uploading backup: %s", e)
            return jsonify({'success': False, 'error': str(e)})
    
    def _save_settings(self, request):
        """Сохранение настроек модуля"""
        try:
            # Пути к утилитам
            self.config['pg_dump_path'] = request.form.get('pg_dump_path', 'pg_dump').strip() or 'pg_dump'
            self.config['psql_path'] = request.form.get('psql_path', 'psql').strip() or 'psql'
            self.config['mysqldump_path'] = request.form.get('mysqldump_path', 'mysqldump').strip() or 'mysqldump'
            self.config['mysql_path'] = request.form.get('mysql_path', 'mysql').strip() or 'mysql'
            
            # Настройки шифрования
            encrypt_backups = bool(request.form.get('encrypt_backups'))
            encryption_key = request.form.get('encryption_key', '').strip()
            
            # Проверка: если шифрование включено, ключ обязателен
            if encrypt_backups and not encryption_key:
                return jsonify({'success': False, 'error': 'Encryption key is required when encryption is enabled'})
            
            self.config['encrypt_backups'] = encrypt_backups
            if encryption_key:  # Сохраняем ключ только если он указан
                self.config['encryption_key'] = encryption_key
            elif not encrypt_backups and 'encryption_key' in self.config:
                # Если шифрование отключено, можно удалить ключ (опционально)
                pass
            
            # Галочки параметров резервного копирования
            self.config['backup_database'] = bool(request.form.get('backup_database'))
            self.config['backup_cache'] = bool(request.form.get('backup_cache'))
            self.config['backup_plugins'] = bool(request.form.get('backup_plugins'))
            self.config['backup_user_files'] = bool(request.form.get('backup_user_files'))
            self.config['backup_app_core'] = bool(request.form.get('backup_app_core'))
            self.config['backup_venv'] = bool(request.form.get('backup_venv'))

            venv_directory = request.form.get('venv_directory', '').strip()
            if venv_directory:
                self.config['venv_directory'] = venv_directory
            
            # Сохраняем конфигурацию
            self.saveConfig()
            
            # Обновляем backup_manager с новыми путями
            self.backup_manager.config = self.config
            self.backup_manager.db_handler = get_database_handler(Config.SQLALCHEMY_DATABASE_URI, self.logger, self.config)
            
            self.logger.info("Backup settings saved successfully (encryption: %s)", encrypt_backups)
            return jsonify({'success': True, 'message': 'Settings saved successfully'})
            
        except Exception as e:
            self.logger.error("Error saving settings: %s", e)
            return jsonify({'success': False, 'error': str(e)})
    
    def _save_auto_backup_settings(self, request):
        """Сохранение настроек автоматического резервного копирования"""
        try:
            enabled = request.form.get('enabled') == 'true'
            crontab = request.form.get('crontab', '0 2 * * *').strip()
            
            if not crontab:
                crontab = '0 2 * * *'
            
            # Валидация crontab выражения
            try:
                from app.core.lib.crontab import nextStartCronJob
                nextStartCronJob(crontab)
            except Exception as e:
                return jsonify({'success': False, 'error': f'Invalid crontab format: {str(e)}'})
            
            # Сохраняем настройки
            self.config['auto_backup_enabled'] = enabled
            self.config['auto_backup_crontab'] = crontab
            self.saveConfig()
            
            # Обновляем задачу
            self._setup_auto_backup_task()
            
            self.logger.info("Auto backup settings saved: enabled=%s, crontab=%s", enabled, crontab)
            return jsonify({'success': True, 'message': 'Auto backup settings saved successfully'})
            
        except Exception as e:
            self.logger.error("Error saving auto backup settings: %s", e)
            return jsonify({'success': False, 'error': str(e)})
    
    def _get_auto_backup_settings(self):
        """Получение текущих настроек автоматического резервного копирования"""
        try:
            from app.core.lib.common import getJob
            job_info = getJob('Backup_auto_periodic')
            
            enabled = job_info is not None
            crontab = job_info.get('crontab', '0 2 * * *') if job_info else self.config.get('auto_backup_crontab', '0 2 * * *')
            
            # Вычисляем следующий запуск
            next_run = None
            if enabled and job_info:
                runtime = job_info.get('runtime')
                if runtime:
                    next_run = runtime.strftime('%Y-%m-%d %H:%M:%S')
            
            return jsonify({
                'success': True,
                'enabled': enabled,
                'crontab': crontab,
                'next_run': next_run
            })
        except Exception as e:
            self.logger.error("Error getting auto backup settings: %s", e)
            return jsonify({'success': False, 'error': str(e)})
    
    def _setup_auto_backup_task(self):
        """Настройка cron задачи для автоматического резервного копирования"""
        try:
            from app.core.lib.common import addCronJob, clearScheduledJob
            
            enabled = self.config.get('auto_backup_enabled', False)
            crontab = self.config.get('auto_backup_crontab', '0 2 * * *')
            
            # Всегда очищаем старую задачу
            clearScheduledJob('Backup_auto_periodic')
            
            # Создаем новую задачу, если включено
            if enabled:
                code = 'from app.core.lib.common import callPluginFunction; callPluginFunction("Backup", "create_auto_backup", {})'
                addCronJob('Backup_auto_periodic', code, crontab)
                self.logger.info("Auto backup task scheduled with crontab: %s", crontab)
            else:
                self.logger.info("Auto backup task disabled")
                
        except Exception as e:
            self.logger.error("Error setting up auto backup task: %s", e)

    @staticmethod
    def _parse_restore_options(request):
        return {
            'database': bool(request.form.get('restore_database')),
            'cache': bool(request.form.get('restore_cache')),
            'config': bool(request.form.get('restore_config')),
            'plugins': bool(request.form.get('restore_plugins')),
            'app_core': bool(request.form.get('restore_app_core')),
            'venv': bool(request.form.get('restore_venv')),
            'user_files': bool(request.form.get('restore_user_files')),
        }

    def _get_backup_metadata(self, request):
        """Получить состав резервной копии для диалога восстановления."""
        backup_name = (request.form.get('backup_name') or request.args.get('backup_name') or '').strip()
        if not backup_name:
            return jsonify({'success': False, 'error': _('Backup not found')}), 400
        try:
            metadata = self.backup_manager.get_backup_metadata(backup_name)
            if not metadata:
                return jsonify({
                    'success': False,
                    'error': _('Backup metadata not found'),
                }), 404
            components = self.backup_manager.get_restore_components(metadata)
            return jsonify({
                'success': True,
                'metadata': metadata,
                'components': components,
            })
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        except Exception as exc:
            self.logger.error("Error reading backup metadata: %s", exc)
            return jsonify({'success': False, 'error': str(exc)}), 500

    def _stop_all_cycles(self, timeout=30):
        """Останавливаем циклы всех модулей перед восстановлением.

        Returns:
            tuple[list[str], list[dict]]: остановленные модули и список сбоев
        """
        stopped = []
        failed = []
        for name, info in plugins.items():
            plugin = info["instance"]
            if 'cycle' not in getattr(plugin, 'actions', []):
                continue
            if not plugin.is_alive():
                continue
            try:
                self.logger.info("Stopping cycle for plugin '%s' before restore", name)
                plugin.event.set()
                if plugin.thread:
                    plugin.thread.join(timeout=timeout)
                    if plugin.thread.is_alive():
                        self.logger.warning(
                            "Cycle for plugin '%s' did not stop within %ss",
                            name,
                            timeout,
                        )
                        failed.append({
                            'name': name,
                            'reason': 'timeout',
                            'detail': _('did not stop within %(timeout)s seconds') % {'timeout': timeout},
                        })
                        continue
                    plugin.thread = None
                stopped.append(name)
            except Exception as exc:
                self.logger.error("Failed to stop cycle for plugin '%s': %s", name, exc)
                failed.append({
                    'name': name,
                    'reason': 'error',
                    'detail': str(exc),
                })
        return stopped, failed

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
            'backup_venv': False,
            'encrypt_backups': False,
            'compress_backups': True,
            'max_backups': 10,
            'storage_duration_days': 30,
        }

        paths = {
            'cache_directory': Config.CACHE_FILE_PATH,
            'plugins_directory': Config.PLUGINS_FOLDER,
            'user_files_directory': Config.FILES_DIR,
            'app_core_directory': os.path.join(Config.APP_DIR, 'app'),
        }
        
        # Пути к утилитам резервного копирования (по умолчанию - искать в PATH)
        tool_paths = {
            'pg_dump_path': 'pg_dump',
            'psql_path': 'psql',
            'mysqldump_path': 'mysqldump',
            'mysql_path': 'mysql',
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
        for key, value in tool_paths.items():
            if self.config.get(key) is None:
                self.config[key] = value
                updated = True

        if not self.config.get('venv_directory'):
            venv_candidates = [
                os.path.join(Config.APP_DIR, '.venv'),
                os.path.join(Config.APP_DIR, 'venv'),
            ]
            for candidate in venv_candidates:
                if os.path.isdir(candidate):
                    self.config['venv_directory'] = candidate
                    updated = True
                    break
            if not self.config.get('venv_directory'):
                # Если директория не найдена, сохраняем наиболее распространенный вариант
                self.config['venv_directory'] = os.path.join(Config.APP_DIR, '.venv')
                updated = True

        if updated:
            self.logger.debug("Backup plugin config updated with defaults: %s", defaults)
            self.saveConfig()
    
    def _save_storage_settings(self, request):
        """Сохранение настроек хранения резервных копий"""
        try:
            max_backups = request.form.get('max_backups', '10').strip()
            storage_duration_days = request.form.get('storage_duration_days', '30').strip()
            
            # Валидация
            try:
                max_backups = int(max_backups)
                if max_backups < 1:
                    return jsonify({'success': False, 'error': _('Minimum 1 backup required')})
            except ValueError:
                return jsonify({'success': False, 'error': _('Invalid value for number of backups')})
            
            try:
                storage_duration_days = int(storage_duration_days)
                if storage_duration_days < 1:
                    return jsonify({'success': False, 'error': _('Storage duration must be at least 1 day')})
            except ValueError:
                return jsonify({'success': False, 'error': _('Invalid value for storage duration')})
            
            # Сохраняем настройки
            self.config['max_backups'] = max_backups
            self.config['storage_duration_days'] = storage_duration_days
            self.saveConfig()
            
            # Обновляем backup_manager с новыми настройками
            self.backup_manager.config = self.config
            # Обновляем storage_handler с новыми настройками
            if hasattr(self.backup_manager.storage_handler, 'update_config'):
                self.backup_manager.storage_handler.update_config(self.config)
            else:
                self.backup_manager.storage_handler = get_storage_handler(self.config)
            
            self.logger.info("Storage settings saved: max_backups=%s, storage_duration_days=%s", max_backups, storage_duration_days)
            return jsonify({'success': True, 'message': _('Storage settings saved successfully')})
            
        except Exception as e:
            self.logger.error("Error saving storage settings: %s", e)
            return jsonify({'success': False, 'error': str(e)})