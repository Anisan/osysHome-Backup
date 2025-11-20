import os
import json
import shutil
from datetime import datetime
from app.configuration import Config
from app.core.lib.object import setProperty
from .database_handlers import get_database_handler
from .storage import get_storage_handler
from .utils.compression import compress_backup, decompress_backup
from .utils.encryption import encrypt_backup, decrypt_backup

class BackupManager:
    def __init__(self, config, logger=None):
        self.config = config
        self.logger = logger
        self.db_handler = get_database_handler(Config.SQLALCHEMY_DATABASE_URI, self.logger)
        self.storage_handler = get_storage_handler(config)  
          
    def create_backup(
        self,
        backup_name=None,
        include_database=True,
        include_cache=False,
        include_files=True,
        include_plugins=None,
        include_user_files=None,
        include_app_core=None,
        progress_callback=None,
    ):
        """Создание резервной копии
        
        Args:
            backup_name: Имя резервной копии
            include_database: Включать ли базу данных
            include_cache: Включать ли кеш
            include_files: Включать ли системные файлы
            include_plugins: Включать ли директорию плагинов
            include_user_files: Включать ли пользовательские файлы из FILES_DIR
            include_app_core: Включать ли ядро приложения
            progress_callback: Функция для отправки прогресса (progress, message)
        """  
        self.logger.info(
            "BackupManager: requested backup creation (name=%s, include_database=%s, include_cache=%s, include_files=%s, include_plugins=%s, include_user_files=%s, include_app_core=%s)",
            backup_name,
            include_database,
            include_cache,
            include_files,
            include_plugins,
            include_user_files,
            include_app_core,
        )
        if not backup_name:  
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"  
            self.logger.debug("BackupManager: auto-generated backup name '%s'", backup_name)
        
        if progress_callback:
            progress_callback(5, 'Инициализация процесса резервного копирования...')
              
        backup_path = os.path.join(self.config.get('backup_directory', 'backups'), backup_name)
        os.makedirs(backup_path, exist_ok=True)
        self.logger.debug("BackupManager: ensured backup directory %s exists", backup_path)
        self.logger.debug("BackupManager: ensured backup directory %s exists", backup_path)
        
        if progress_callback:
            progress_callback(10, 'Подготовка директории для резервной копии...')
          
        # Создание резервной копии базы данных  
        if include_database:
            if progress_callback:
                progress_callback(20, 'Создание резервной копии базы данных...')
            db_backup_path = os.path.join(backup_path, 'database')
            self.logger.info("BackupManager: creating database backup in %s", db_backup_path)
            self.db_handler.create_backup(db_backup_path)
            self.logger.debug("BackupManager: database backup completed")
            
            if progress_callback:
                progress_callback(40, 'Резервная копия базы данных создана')
        else:
            if progress_callback:
                progress_callback(40, 'Пропуск резервного копирования базы данных')
            self.logger.debug("BackupManager: include_database disabled, skipping database backup")
        
        # Создание резервной копии кеша
        if include_cache:
            if progress_callback:
                progress_callback(42, 'Создание резервной копии кеша...')
            cache_backup_path = os.path.join(backup_path, 'cache')
            self.logger.info("BackupManager: creating cache backup in %s", cache_backup_path)
            self._backup_cache(cache_backup_path)
            self.logger.debug("BackupManager: cache backup completed")
            
            if progress_callback:
                progress_callback(44, 'Резервная копия кеша создана')
        else:
            if progress_callback:
                progress_callback(44, 'Пропуск резервного копирования кеша')
            self.logger.debug("BackupManager: include_cache disabled, skipping cache backup")
          
        # Резервное копирование файлов системы  
        copied_resources = []
        if include_files:
            resource_flags = {
                'backup_plugins': include_plugins if include_plugins is not None else self.config.get('backup_plugins', False),
                'backup_app_core': include_app_core if include_app_core is not None else self.config.get('backup_app_core', False),
            }
            if progress_callback:
                progress_callback(45, 'Резервное копирование системных файлов...')
            copied_resources = self._backup_system_files(backup_path, progress_callback, resource_flags)
        else:
            if progress_callback:
                progress_callback(60, 'Пропуск копирования системных файлов')
            self.logger.debug("BackupManager: include_files disabled, skipping system file copy step")
            self.logger.debug("BackupManager: include_files disabled, skipping system file copy")

        # Резервное копирование пользовательских файлов (отдельно от системных)
        user_files_copied = False
        if include_user_files is not None and include_user_files:
            if progress_callback:
                progress_callback(62, 'Резервное копирование пользовательских файлов...')
            user_files_copied = self._backup_user_files(backup_path, progress_callback)
            if progress_callback:
                progress_callback(65, 'Пользовательские файлы скопированы')
        elif include_user_files is None and self.config.get('backup_user_files', False):
            if progress_callback:
                progress_callback(62, 'Резервное копирование пользовательских файлов...')
            user_files_copied = self._backup_user_files(backup_path, progress_callback)
            if progress_callback:
                progress_callback(65, 'Пользовательские файлы скопированы')
          
        # Создание метаданных  
        if progress_callback:
            progress_callback(70, 'Создание метаданных резервной копии...')
        metadata = {  
            'name': backup_name,  
            'created_at': datetime.now().isoformat(),  
            'database_type': self.db_handler.db_type,  
            'includes_database': include_database,
            'includes_cache': include_cache,
            'includes_files': include_files,  
            'includes_user_files': user_files_copied,
            'osyshome_version': self._get_system_version(),  
            'backup_resources': copied_resources,  
        }  
          
        metadata_path = os.path.join(backup_path, 'metadata.json')
        self.logger.debug("BackupManager: writing metadata to %s", metadata_path)
        with open(metadata_path, 'w', encoding='utf-8') as f:  
            json.dump(metadata, f, indent=2)  
        
        if progress_callback:
            progress_callback(75, 'Метаданные созданы')
          
        # Сжатие и шифрование  
        if self.config.get('compress_backups', True):  
            if progress_callback:
                progress_callback(80, 'Сжатие резервной копии...')
            backup_path = compress_backup(backup_path)
            self.logger.debug("BackupManager: backup compressed to %s", backup_path)
            
            # Сохраняем копию metadata.json рядом с архивом для быстрого доступа
            if os.path.isfile(backup_path):
                external_metadata_path = backup_path + '.metadata.json'
                try:
                    with open(external_metadata_path, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2)
                    self.logger.debug("BackupManager: external metadata saved to %s", external_metadata_path)
                except Exception as e:
                    self.logger.warning("BackupManager: failed to save external metadata: %s", e)
            
            if progress_callback:
                progress_callback(90, 'Сжатие завершено')
          
        if self.config.get('encrypt_backups', False):  
            if progress_callback:
                progress_callback(92, 'Шифрование резервной копии...')
            old_backup_path = backup_path
            backup_path = encrypt_backup(backup_path, self.config.get('encryption_key'))
            self.logger.debug("BackupManager: backup encrypted to %s", backup_path)
            
            # Переносим external metadata для зашифрованного файла
            if os.path.isfile(backup_path) and old_backup_path != backup_path:
                old_metadata = old_backup_path + '.metadata.json'
                new_metadata = backup_path + '.metadata.json'
                if os.path.exists(old_metadata):
                    try:
                        shutil.move(old_metadata, new_metadata)
                        self.logger.debug("BackupManager: moved external metadata to %s", new_metadata)
                    except Exception as e:
                        self.logger.warning("BackupManager: failed to move external metadata: %s", e)
            
            if progress_callback:
                progress_callback(95, 'Шифрование завершено')
        
        if progress_callback:
            progress_callback(100, 'Резервная копия успешно создана')
        self.logger.info("BackupManager: backup '%s' successfully created at %s", backup_name, backup_path)
          
        return backup_path
          
    def _backup_system_files(self, backup_path, progress_callback=None, resource_flags=None):
        """Резервное копирование системных файлов с учетом индивидуальных флагов"""
        files_backup_path = os.path.join(backup_path, 'files')
        self.logger.debug("BackupManager: backing up system files into %s", files_backup_path)
        os.makedirs(files_backup_path, exist_ok=True)  
        manifest = []  
          
        # Копирование конфигурационных файлов  
        if progress_callback:
            progress_callback(50, 'Копирование конфигурационных файлов...')
        config_files = ['config.yaml', 'sample_config.yaml']
        for config_file in config_files:
            if os.path.exists(config_file):
                shutil.copy2(config_file, files_backup_path)
                self.logger.debug("BackupManager: copied config file %s", config_file)
            else:
                self.logger.debug("BackupManager: config file %s not found, skipping", config_file)
                  
        resource_flags = resource_flags or {}

        resource_definitions = [
            {
                'enabled': resource_flags.get('backup_plugins', self.config.get('backup_plugins', False)),
                'path': self.config.get(
                    'plugins_directory',
                    getattr(Config, 'PLUGINS_FOLDER', os.path.join(Config.APP_DIR, 'plugins')),
                ),
                'alias': 'plugins',
                'start_progress': 55,
                'end_progress': 58,
                'start_message': 'Копирование плагинов...',
                'end_message': 'Плагины скопированы',
            },
            {
                'enabled': resource_flags.get('backup_app_core', self.config.get('backup_app_core', False)),
                'path': self.config.get('app_core_directory', Config.APP_DIR),
                'alias': 'app',
                'start_progress': 60,
                'end_progress': 63,
                'start_message': 'Копирование ядра приложения...',
                'end_message': 'Ядро приложения скопировано',
            },
        ]

        for resource in resource_definitions:
            if not resource['enabled']:
                continue

            source_path = resource.get('path')
            if not source_path:
                self.logger.warning(
                    "BackupManager: resource '%s' has no source path defined, skipping",
                    resource['alias'],
                )
                continue

            normalized_source = os.path.abspath(source_path)
            if not os.path.exists(normalized_source):
                self.logger.warning(
                    "BackupManager: resource '%s' path %s not found, skipping",
                    resource['alias'],
                    normalized_source,
                )
                continue

            if progress_callback:
                progress_callback(resource['start_progress'], resource['start_message'])

            destination = os.path.join(files_backup_path, resource['alias'])
            if self._copy_directory(normalized_source, destination):
                manifest.append({
                    'alias': resource['alias'],
                    'target': normalized_source,
                })
                self.logger.debug(
                    "BackupManager: resource '%s' copied from %s to %s",
                    resource['alias'],
                    normalized_source,
                    destination,
                )
                if progress_callback:
                    progress_callback(resource['end_progress'], resource['end_message'])
            else:
                self.logger.error(
                    "BackupManager: failed to copy resource '%s' from %s",
                    resource['alias'],
                    normalized_source,
                )

        return manifest

    def _backup_user_files(self, backup_path, progress_callback=None):
        """Резервное копирование пользовательских файлов (отдельно от системных)"""
        files_backup_path = os.path.join(backup_path, 'user_files')
        self.logger.debug("BackupManager: backing up user files into %s", files_backup_path)
        os.makedirs(files_backup_path, exist_ok=True)

        user_files_path = self.config.get(
            'user_files_directory',
            getattr(Config, 'FILES_DIR', os.path.join(Config.APP_DIR, 'files')),
        )
        normalized_source = os.path.abspath(user_files_path)

        if not os.path.exists(normalized_source):
            self.logger.warning(
                "BackupManager: user files path %s not found, skipping",
                normalized_source,
            )
            return False

        if progress_callback:
            progress_callback(63, 'Копирование пользовательских файлов...')

        destination = files_backup_path
        if self._copy_directory(normalized_source, destination):
            self.logger.debug(
                "BackupManager: user files copied from %s to %s",
                normalized_source,
                destination,
            )
            if progress_callback:
                progress_callback(64, 'Пользовательские файлы скопированы')
            return True
        else:
            self.logger.error(
                "BackupManager: failed to copy user files from %s",
                normalized_source,
            )
            return False
    
    def _backup_cache(self, cache_backup_path):
        """Резервное копирование кеша"""
        cache_path = self.config.get(
            'cache_directory',
            getattr(Config, 'CACHE_FILE_PATH', os.path.join(Config.APP_DIR, 'cache')),
        )
        normalized_source = os.path.abspath(cache_path)
        
        if not os.path.exists(normalized_source):
            self.logger.warning(
                "BackupManager: cache path %s not found, skipping",
                normalized_source,
            )
            return False
        
        try:
            if os.path.isdir(normalized_source):
                # Если это директория, копируем её полностью
                if os.path.exists(cache_backup_path):
                    shutil.rmtree(cache_backup_path)
                shutil.copytree(normalized_source, cache_backup_path)
            elif os.path.isfile(normalized_source):
                # Если это файл, создаем директорию и копируем файл
                os.makedirs(cache_backup_path, exist_ok=True)
                shutil.copy2(normalized_source, os.path.join(cache_backup_path, os.path.basename(normalized_source)))
            else:
                self.logger.warning("BackupManager: cache path %s is neither file nor directory", normalized_source)
                return False
            
            self.logger.debug(
                "BackupManager: cache copied from %s to %s",
                normalized_source,
                cache_backup_path,
            )
            return True
        except Exception as exc:
            self.logger.error(
                "BackupManager: failed to copy cache from %s: %s",
                normalized_source,
                exc,
            )
            return False
                  
    def _get_system_version(self):  
        """Получение версии системы osysHome"""  
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'describe', '--tags'],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:  
                return result.stdout.strip()  
        except Exception:  
            pass  
        return "unknown"  
          
    def restore_backup(self, backup_name, progress_callback=None):  
        """Восстановление из резервной копии
        
        Args:
            backup_name: Имя резервной копии
            progress_callback: Функция для отправки прогресса (progress, message)
        """  
        self.logger.info(
            "BackupManager: requested restore for backup '%s' (encrypted=%s)",
            backup_name,
            backup_name.endswith('.encrypted.tar.gz'),
        )
        if progress_callback:
            progress_callback(5, 'Инициализация процесса восстановления...')
            
        backup_path = os.path.join(self.config.get('backup_directory', 'backups'), backup_name)  
        
        if progress_callback:
            progress_callback(10, 'Проверка резервной копии...')
          
        if not os.path.exists(backup_path):  
            raise FileNotFoundError(f"Backup {backup_name} not found")
        
        # Временная директория для распаковки (если нужно)
        temp_extract_dir = None
          
        # Проверка на зашифрованную резервную копию  
        if backup_name.endswith('.encrypted.tar.gz'):  
            if not self.config.get('encryption_key'):  
                raise ValueError("Encryption key required for encrypted backup")  
            if progress_callback:
                progress_callback(15, 'Расшифровка резервной копии...')
            self.logger.info("BackupManager: decrypting encrypted backup %s", backup_path)
            backup_path = decrypt_backup(backup_path, self.config.get('encryption_key'))
            self.logger.debug("BackupManager: decrypted backup located at %s", backup_path)
            if progress_callback:
                progress_callback(20, 'Расшифровка завершена')
        
        # Проверка на сжатый архив (tar.gz) - нужно распаковать
        # Проверяем, является ли путь файлом с расширением .tar.gz
        if os.path.isfile(backup_path) and backup_path.endswith('.tar.gz'):
            if progress_callback:
                progress_callback(22, 'Распаковка архива резервной копии...')
            # Создаем временную директорию для распаковки
            import tempfile
            temp_extract_dir = tempfile.mkdtemp(prefix='backup_restore_')
            try:
                backup_path = decompress_backup(backup_path, temp_extract_dir)
                self.logger.debug("BackupManager: archive extracted into %s", backup_path)
                if progress_callback:
                    progress_callback(25, 'Архив распакован')
            except Exception as e:
                # Очищаем временную директорию при ошибке
                if temp_extract_dir and os.path.exists(temp_extract_dir):
                    shutil.rmtree(temp_extract_dir, ignore_errors=True)
                raise ValueError(f"Ошибка распаковки архива: {str(e)}") from e
              
        # Загрузка метаданных  
        if progress_callback:
            progress_callback(27, 'Загрузка метаданных резервной копии...')
        metadata_file = os.path.join(backup_path, 'metadata.json')
        if not os.path.exists(metadata_file):
            if temp_extract_dir and os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
            self.logger.error("BackupManager: metadata not found in %s", backup_path)
            raise ValueError(f"Backup metadata not found in {backup_path}")
              
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        self.logger.debug(
            "BackupManager: metadata loaded (includes_files=%s, database_type=%s)",
            metadata.get('includes_files'),
            metadata.get('database_type'),
        )
        
        if progress_callback:
            progress_callback(30, 'Метаданные загружены')
              
        # Восстановление базы данных  
        if metadata.get('includes_database', True):  # По умолчанию True для совместимости со старыми бэкапами
            if progress_callback:
                progress_callback(35, 'Восстановление базы данных...')
            db_backup_path = os.path.join(backup_path, 'database')
            self.logger.info("BackupManager: restoring database from %s", db_backup_path)
            self.db_handler.restore_backup(db_backup_path)
            self.logger.debug("BackupManager: database restore completed")
            
            if progress_callback:
                progress_callback(60, 'База данных восстановлена')
        else:
            if progress_callback:
                progress_callback(60, 'Пропуск восстановления базы данных')
            self.logger.debug("BackupManager: metadata indicates no database, skipping restore step")
        
        # Восстановление кеша
        if metadata.get('includes_cache', False):
            if progress_callback:
                progress_callback(62, 'Восстановление кеша...')
            cache_backup_path = os.path.join(backup_path, 'cache')
            self._restore_cache(cache_backup_path)
            self.logger.debug("BackupManager: cache restore completed")
            
            if progress_callback:
                progress_callback(64, 'Кеш восстановлен')
        else:
            if progress_callback:
                progress_callback(64, 'Пропуск восстановления кеша')
            self.logger.debug("BackupManager: metadata indicates no cache, skipping restore step")
          
        # Восстановление файлов системы  
        if metadata.get('includes_files', False):  
            if progress_callback:
                progress_callback(65, 'Восстановление системных файлов...')
            self._restore_system_files(backup_path, progress_callback, metadata)
            self.logger.debug("BackupManager: system files restore completed")
        else:
            if progress_callback:
                progress_callback(75, 'Пропуск восстановления системных файлов')
            self.logger.debug("BackupManager: metadata indicates no system files, skipping restore step")

        # Восстановление пользовательских файлов (отдельно от системных)
        if metadata.get('includes_user_files', False):
            if progress_callback:
                progress_callback(77, 'Восстановление пользовательских файлов...')
            self._restore_user_files(backup_path, progress_callback)
            self.logger.debug("BackupManager: user files restore completed")
        else:
            if progress_callback:
                progress_callback(80, 'Пропуск восстановления пользовательских файлов')
            self.logger.debug("BackupManager: metadata indicates no user files, skipping restore step")
              
        # TODO Очистка кэша объектов после восстановления  
        # if progress_callback:
        #     progress_callback(90, 'Очистка кэша объектов...')
        # from app.core.main.ObjectsStorage import objects_storage  
        # objects_storage.clear()
        # self.logger.debug("BackupManager: object storage cache cleared after restore")
        
        # Очистка временной директории после успешного восстановления
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            if progress_callback:
                progress_callback(95, 'Очистка временных файлов...')
            try:
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
                self.logger.debug("BackupManager: temporary directory %s removed", temp_extract_dir)
            except Exception as cleanup_error:
                self.logger.warning("BackupManager: failed to remove temp dir %s: %s", temp_extract_dir, cleanup_error)
        
        if progress_callback:
            progress_callback(100, 'Восстановление успешно завершено')
        self.logger.info("BackupManager: restore for backup '%s' completed successfully", backup_name)

        setProperty("SystemVar.NeedRestart", True, "Backup restore " + backup_name)
              
        return True
          
    def _restore_system_files(self, backup_path, progress_callback=None, metadata=None):  
        """Восстановление системных файлов"""  
        files_backup_path = os.path.join(backup_path, 'files')
        self.logger.debug("BackupManager: restoring system files from %s", files_backup_path)
          
        if os.path.exists(files_backup_path):  
            if progress_callback:
                progress_callback(70, 'Восстановление конфигурационных файлов...')

            resource_map = {}
            if metadata:
                for entry in metadata.get('backup_resources', []):
                    alias = entry.get('alias')
                    target = entry.get('target')
                    if alias and target:
                        resource_map[alias] = target

            resource_map.setdefault(
                'plugins',
                self.config.get(
                    'plugins_directory',
                    getattr(Config, 'PLUGINS_FOLDER', os.path.join(Config.APP_DIR, 'plugins')),
                ),
            )
            resource_map.setdefault(
                'app',
                self.config.get('app_core_directory', Config.APP_DIR)
            )

            progress_messages = {
                'plugins': 'Восстановление плагинов...',
                'app': 'Восстановление ядра приложения...',
            }

            # Восстановление конфигурационных файлов и директорий  
            for item in os.listdir(files_backup_path):  
                item_path = os.path.join(files_backup_path, item)  
                if os.path.isfile(item_path) and item.endswith('.yaml'):  
                    shutil.copy2(item_path, item)  
                elif os.path.isdir(item_path):  
                    target_path = resource_map.get(item) or item
                    if progress_callback:
                        progress_callback(75, progress_messages.get(item, f'Восстановление директории: {item}...'))
                    self._restore_directory(item_path, target_path)
            if progress_callback:
                progress_callback(76, 'Системные файлы восстановлены')

    def _restore_user_files(self, backup_path, progress_callback=None):
        """Восстановление пользовательских файлов (отдельно от системных)"""
        user_files_backup_path = os.path.join(backup_path, 'user_files')
        self.logger.debug("BackupManager: restoring user files from %s", user_files_backup_path)

        if not os.path.exists(user_files_backup_path):
            self.logger.warning("BackupManager: user files backup path %s not found, skipping", user_files_backup_path)
            return

        user_files_path = self.config.get(
            'user_files_directory',
            getattr(Config, 'FILES_DIR', os.path.join(Config.APP_DIR, 'files')),
        )
        normalized_destination = os.path.abspath(user_files_path)

        if progress_callback:
            progress_callback(78, 'Восстановление пользовательских файлов...')

        try:
            self._restore_directory(user_files_backup_path, normalized_destination)
            self.logger.debug(
                "BackupManager: user files restored from %s to %s",
                user_files_backup_path,
                normalized_destination,
            )
            if progress_callback:
                progress_callback(79, 'Пользовательские файлы восстановлены')
        except Exception as exc:
            self.logger.error(
                "BackupManager: failed to restore user files from %s to %s: %s",
                user_files_backup_path,
                normalized_destination,
                exc,
            )
            raise
    
    def _restore_cache(self, cache_backup_path):
        """Восстановление кеша"""
        if not os.path.exists(cache_backup_path):
            self.logger.warning("BackupManager: cache backup path %s not found, skipping", cache_backup_path)
            return
        
        cache_path = self.config.get(
            'cache_directory',
            getattr(Config, 'CACHE_FILE_PATH', os.path.join(Config.APP_DIR, 'cache')),
        )
        normalized_destination = os.path.abspath(cache_path)
        
        try:
            # Проверяем, является ли cache_backup_path директорией с содержимым
            if os.path.isdir(cache_backup_path):
                # Если это директория, восстанавливаем её полностью
                if os.path.exists(normalized_destination):
                    shutil.rmtree(normalized_destination)
                shutil.copytree(cache_backup_path, normalized_destination)
            else:
                self.logger.warning("BackupManager: cache backup path %s is not a directory", cache_backup_path)
                return
            
            self.logger.debug(
                "BackupManager: cache restored from %s to %s",
                cache_backup_path,
                normalized_destination,
            )
        except Exception as exc:
            self.logger.error(
                "BackupManager: failed to restore cache from %s to %s: %s",
                cache_backup_path,
                normalized_destination,
                exc,
            )
            raise
                      
    # ДЕЛЕГИРОВАНИЕ К STORAGE_HANDLER  
    def list_backups(self):  
        """Получение списка резервных копий - делегирование к storage_handler"""  
        return self.storage_handler.list_backups()  
          
    def delete_backup(self, backup_name):  
        """Удаление резервной копии - делегирование к storage_handler"""  
        return self.storage_handler.delete_backup(backup_name)  
          
    def cleanup_old_backups(self):  
        """Очистка старых резервных копий - делегирование к storage_handler"""  
        return self.storage_handler.cleanup_old_backups()  
          
    def get_backup_size(self, backup_name):  
        """Получение размера резервной копии - делегирование к storage_handler"""  
        return self.storage_handler.get_backup_size(backup_name)  
          
    def create_auto_backup(self):  
        """Автоматическое создание резервной копии"""  
        try:  
            backup_name = f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"  
            backup_path = self.create_backup(backup_name, include_files=True)  
              
            # Очистка старых автоматических резервных копий через storage_handler  
            self.cleanup_old_backups()  
              
            return backup_path  
        except Exception as e:  
            print(f"Auto backup failed: {e}")  
            return None  
              
    def get_backup_info(self, backup_name):  
        """Получение информации о резервной копии - делегирование к storage_handler"""  
        return self.storage_handler.get_backup_info(backup_name)  
          
    def verify_backup(self, backup_name):  
        """Проверка целостности резервной копии - делегирование к storage_handler"""  
        return self.storage_handler.verify_backup(backup_name)

    def _copy_directory(self, source_path, destination_path):
        """Копирование директории с заменой существующего содержимого."""
        def ignore_patterns(_directory, files):
            """Функция для игнорирования служебных папок и файлов"""
            ignored = set()
            for name in files:
                # Игнорируем .git и __pycache__
                if name in {'.git', '__pycache__', '.gitignore', '.pytest_cache', '.venv', 'venv', 'node_modules'}:
                    ignored.add(name)
                # Игнорируем .pyc файлы
                elif name.endswith('.pyc') or name.endswith('.pyo'):
                    ignored.add(name)
            return ignored
        
        try:
            if os.path.exists(destination_path):
                shutil.rmtree(destination_path)
            destination_parent = os.path.dirname(destination_path) or "."
            os.makedirs(destination_parent, exist_ok=True)
            shutil.copytree(source_path, destination_path, ignore=ignore_patterns)
            return True
        except Exception as exc:
            self.logger.error(
                "BackupManager: failed to copy directory %s -> %s (%s)",
                source_path,
                destination_path,
                exc,
            )
            return False

    def _restore_directory(self, source_path, destination_path):
        """Восстановление директории в целевой путь."""
        try:
            normalized_destination = os.path.abspath(destination_path)
            if os.path.exists(normalized_destination):
                shutil.rmtree(normalized_destination)
            destination_parent = os.path.dirname(normalized_destination) or "."
            os.makedirs(destination_parent, exist_ok=True)
            shutil.copytree(source_path, normalized_destination)
            self.logger.debug(
                "BackupManager: restored directory %s -> %s",
                source_path,
                normalized_destination,
            )
        except Exception as exc:
            self.logger.error(
                "BackupManager: failed to restore directory %s -> %s (%s)",
                source_path,
                destination_path,
                exc,
            )