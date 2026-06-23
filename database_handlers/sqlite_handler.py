import os
import time

import sqlite3

from app.database import engine
from app.extensions import db as flask_db
from app.core.main.ObjectManager import shutdown_batch_writer


def _release_app_sqlite_connections():
    """Закрыть пул соединений приложения, чтобы файл SQLite можно было заменить."""
    shutdown_batch_writer()

    try:
        flask_db.session.remove()
    except Exception:
        pass

    try:
        engine.dispose()
    except Exception:
        pass

    try:
        flask_db.engine.dispose()
    except Exception:
        pass


class SQLiteHandler:
    def __init__(self, database_uri, logger):
        self.db_type = 'sqlite'
        self.db_path = database_uri.replace('sqlite:///', '')
        self.logger = logger

    def _wal_paths(self):
        """Пути WAL-файлов для текущей БД."""
        return {
            'wal': self.db_path + '-wal',
            'shm': self.db_path + '-shm',
        }

    @staticmethod
    def _to_sqlite_uri(path: str, mode: str) -> str:
        # SQLite URI требует "file:" и нормализованный путь (для Windows заменяем "\" на "/").
        # Используем только необходимые параметры, чтобы не зависеть от конкретной конфигурации.
        uri_path = os.path.abspath(path).replace('\\', '/')
        # Для Windows делаем путь вида /D:/path/to/db.db, чтобы URI гарантированно трактовался как файл.
        if len(uri_path) >= 2 and uri_path[1] == ':':
            uri_path = '/' + uri_path
        return f"file:{uri_path}?mode={mode}"

    def create_backup(self, backup_path):  
        """Создание резервной копии SQLite"""  
        os.makedirs(backup_path, exist_ok=True)
        backup_db_filename = 'database.db'
        backup_file = os.path.join(backup_path, backup_db_filename)

        if not os.path.exists(self.db_path):
            if self.logger:
                self.logger.warning("SQLiteHandler: db file not found: %s", self.db_path)
            return None

        # Удаляем старый файл бэкапа (если он был) — дальше откроем его как "dest".
        if os.path.exists(backup_file):
            os.remove(backup_file)

        try:
            # Используем SQLite backup API, которое корректно делает "снимок" даже в WAL-режиме.
            # Источник читаем только в режиме ro, чтобы не зависеть от блокировок записи.
            src_conn = sqlite3.connect(
                self._to_sqlite_uri(self.db_path, mode='ro'),
                uri=True,
                timeout=10,
            )
            try:
                dst_conn = sqlite3.connect(backup_file, timeout=10)
                try:
                    src_conn.backup(dst_conn)
                    dst_conn.commit()
                finally:
                    dst_conn.close()
            finally:
                src_conn.close()
        except Exception as exc:
            if self.logger:
                self.logger.error("SQLiteHandler: failed to create backup via sqlite3.backup: %s", exc)
            raise

        if self.logger:
            self.logger.debug("SQLiteHandler: backup created at %s", backup_file)
        return backup_file

    def restore_backup(self, backup_path):
        """Восстановление из резервной копии SQLite"""
        backup_db_filename = 'database.db'
        backup_file = os.path.join(backup_path, backup_db_filename)
        if not os.path.exists(backup_file):
            return False

        # Убедимся, что папка БД существует.
        db_dir = os.path.dirname(os.path.abspath(self.db_path)) or "."
        os.makedirs(db_dir, exist_ok=True)

        # Чтобы не смешать WAL от текущего состояния с восстановленным main-db,
        # сначала удаляем имеющиеся wal/shm (если они есть).
        for path in self._wal_paths().values():
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as exc:
                if self.logger:
                    self.logger.warning("SQLiteHandler: failed to remove %s: %s", path, exc)

        # Восстанавливаем во временный файл (в той же директории), затем делаем атомарную замену.
        tmp_db_path = self.db_path + ".restore_tmp"
        if os.path.exists(tmp_db_path):
            os.remove(tmp_db_path)

        try:
            src_conn = sqlite3.connect(
                self._to_sqlite_uri(backup_file, mode='ro'),
                uri=True,
                timeout=10,
            )
            try:
                dst_conn = sqlite3.connect(tmp_db_path, timeout=10)
                try:
                    src_conn.backup(dst_conn)
                    dst_conn.commit()
                finally:
                    dst_conn.close()
            finally:
                src_conn.close()

            # Закрываем пул соединений приложения, иначе os.replace получит EBUSY.
            _release_app_sqlite_connections()
            time.sleep(0.2)

            # Атомарно заменяем основной файл БД.
            os.replace(tmp_db_path, self.db_path)
        except Exception as exc:
            # На случай ошибки удалим временный файл.
            try:
                if os.path.exists(tmp_db_path):
                    os.remove(tmp_db_path)
            except Exception:
                pass
            if self.logger:
                self.logger.error("SQLiteHandler: failed to restore backup via sqlite3.backup: %s", exc)
            raise
        finally:
            # На всякий случай ещё раз подчистим WAL/SHM.
            for path in self._wal_paths().values():
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass

        if self.logger:
            self.logger.debug("SQLiteHandler: restored from %s", backup_file)
        return True