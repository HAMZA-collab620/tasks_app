import os
import shutil
import datetime
from dar_tasks.constants import DAILY_FILENAME, DAILY_TEMPLATE_FILENAME
from dar_tasks.utils import safe_file_op
from dar_tasks.logger import logger


class BackupManager:
    """Manages project backups and daily task transitions with logging."""

    def __init__(self, base_dir, projects_dir, backups_dir, settings_manager):
        self.base_dir, self.projects_dir, self.backups_dir, self.settings = (
            base_dir,
            projects_dir,
            backups_dir,
            settings_manager,
        )
        logger.info("BackupManager initialized.")

    def perform_routine_maintenance(self):
        """Standard maintenance: cleanup old backups and create a new daily snapshot."""
        self.cleanup_old_backups()
        self.create_snapshot("routine")

    def create_snapshot(self, reason="manual"):
        """Create a full backup of all project files."""
        date_str = datetime.date.today().isoformat()
        dest_dir = os.path.join(self.backups_dir, date_str)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        for fn in os.listdir(self.projects_dir):
            if fn.endswith(".txt"):
                safe_file_op(shutil.copy2, os.path.join(self.projects_dir, fn), os.path.join(dest_dir, fn))

    def cleanup_old_backups(self):
        """Remove backup directories older than the retention setting."""
        days = self.settings.get("backup", "backup_retention_days", 30)
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)

        for d in os.listdir(self.backups_dir):
            path = os.path.join(self.backups_dir, d)
            if os.path.isdir(path):
                try:
                    dt = datetime.datetime.fromisoformat(d)
                    if dt < cutoff:
                        safe_file_op(shutil.rmtree, path)
                except ValueError:
                    pass

    def setup_daily_tasks(self):
        """Prepare daily.txt, archiving old content and resetting it for a new day."""
        daily_path = os.path.join(self.projects_dir, DAILY_FILENAME)
        template_path = os.path.join(self.projects_dir, DAILY_TEMPLATE_FILENAME)
        archive_path = os.path.join(self.base_dir, "أرشيف_المهام_اليومية.txt")

        if os.path.exists(daily_path):
            # Check if the file was modified on a previous day
            mtime = os.path.getmtime(daily_path)
            last_mod_date = datetime.date.fromtimestamp(mtime)
            today = datetime.date.today()

            if last_mod_date < today:
                logger.info("New day detected. Archiving previous daily tasks.")
                # 1. Archive old content
                try:
                    with open(daily_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    
                    if content:
                        with open(archive_path, "a", encoding="utf-8") as f:
                            f.write(f"\n--- {last_mod_date.isoformat()} ---\n{content}\n")
                except IOError as e:
                    logger.error(f"Failed to archive daily tasks: {e}")

                # 2. Reset from template or clear
                if os.path.exists(template_path):
                    safe_file_op(shutil.copy2, template_path, daily_path)
                else:
                    try:
                        with open(daily_path, "w", encoding="utf-8") as f:
                            pass
                    except IOError as e:
                        logger.error(f"Failed to clear daily_path: {e}")
        else:
            # Create for the first time
            if os.path.exists(template_path):
                safe_file_op(shutil.copy2, template_path, daily_path)
            else:
                try:
                    with open(daily_path, "w", encoding="utf-8") as f:
                        pass
                except IOError as e:
                    logger.error(f"Failed to create daily_path: {e}")
