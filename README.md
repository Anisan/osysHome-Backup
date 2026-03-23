# Backup - Backup Management Module

![Backup Icon](static/Backup.png)

A comprehensive backup and restore system for creating, managing, and restoring system backups with support for database, files, plugins, and automatic scheduling.

## Description

The `Backup` module provides a full-featured backup management system for the osysHome platform. It enables you to create complete system backups, restore from backups, manage backup storage, and configure automatic periodic backups.

## Main Features

- ✅ **Full System Backup**: Backup database, cache, plugins, user files, app core, and virtual environment
- ✅ **Database Support**: Supports PostgreSQL and MySQL databases
- ✅ **Backup Encryption**: Optional encryption for backup files
- ✅ **Automatic Backups**: Configurable cron-based automatic backup scheduling
- ✅ **Backup Management**: List, download, upload, and delete backups
- ✅ **Storage Management**: Configure maximum backups and storage duration
- ✅ **Progress Tracking**: Real-time backup/restore progress via WebSocket
- ✅ **Widget Support**: Dashboard widget showing backup status

## Backup Components

### Database Backup
- PostgreSQL (using pg_dump/psql)
- MySQL (using mysqldump/mysql)
- Automatic detection of database type

### File Backup
- Cache directory
- Plugins directory
- User files directory
- Application core
- Virtual environment (venv)

## Admin Panel

The module provides a comprehensive admin interface:

### Main View
- **Backup List**: View all available backups with details
- **Backup Information**: Name, creation date, size, components included
- **Actions**: Create, restore, download, delete backups

### Create Backup
- Select components to include:
  - Database
  - Cache
  - Plugins
  - User files
  - App core
  - Virtual environment
- Custom backup name
- Real-time progress tracking

### Restore Backup
- Select backup to restore
- Automatic system cycle stopping before restore
- Progress tracking
- Automatic cycle resumption after restore

### Settings
- **Database Tools**: Configure paths to pg_dump, psql, mysqldump, mysql
- **Encryption**: Enable/disable backup encryption with key management
- **Auto Backup**: Configure automatic backup schedule (crontab format)
- **Storage**: Configure maximum backups and storage duration

## Automatic Backups

Configure automatic backups using cron syntax:

- **Crontab Format**: `minute hour day month weekday`
- **Example**: `0 2 * * *` - Daily at 2:00 AM
- **Default**: `0 2 * * *` (daily at 2 AM)

Automatic backups:
- Use default settings from configuration
- Are prefixed with `auto_backup_`
- Include timestamp in name
- Trigger automatic cleanup of old backups

## Backup Storage

### Storage Settings
- **Maximum Backups**: Maximum number of backups to keep
- **Storage Duration**: Days to keep backups before automatic deletion
- **Cleanup**: Automatic cleanup of old backups

### Backup Format
- **Compressed**: `.tar.gz` format
- **Encrypted**: `.encrypted.tar.gz` format (if encryption enabled)

## Widget

The module provides a dashboard widget showing:
- Total number of backups
- Latest backup information (name, date, size)
- Auto backup status and next run time

## Usage

### Creating a Backup

1. Navigate to Backup module in admin panel
2. Click "Create Backup"
3. Select components to include
4. Enter backup name (optional)
5. Click "Create"
6. Monitor progress in real-time

### Restoring a Backup

1. Navigate to Backup module
2. Find the backup to restore
3. Click "Restore"
4. Confirm restoration
5. Monitor progress
6. System will restart cycles after restore

### Configuring Automatic Backups

1. Navigate to Backup settings
2. Enable "Auto Backup"
3. Set crontab schedule (e.g., `0 2 * * *` for daily at 2 AM)
4. Save settings

### Uploading a Backup

1. Navigate to Backup module
2. Click "Upload Backup"
3. Select `.tar.gz` or `.encrypted.tar.gz` file
4. File will be added to backup list

## Technical Details

- **Backup Format**: TAR.GZ archive
- **Encryption**: AES encryption (if enabled)
- **Database Handlers**: PostgreSQL, MySQL
- **Storage Handlers**: Local filesystem, configurable storage backends
- **Threading**: Background backup/restore operations
- **WebSocket**: Real-time progress updates

## Version

Current version: **1.4**

## Category

System

## Actions

The module provides the following actions:
- `widget` - Dashboard widget with backup statistics

## Requirements

- Flask
- SQLAlchemy
- Database utilities (pg_dump, psql, mysqldump, mysql)
- Cryptography library (for encryption)
- osysHome core system

## Author

osysHome Team

## License

See the main osysHome project license

