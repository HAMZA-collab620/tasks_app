import datetime
import os
import tempfile
from dar_tasks.utils import safe_file_op
from dar_tasks.logger import logger
from dar_tasks.constants import DEFAULT_ARCHIVE_NAME, DEFAULT_TRASH_NAME


class ProjectModel:
    """Manages tasks for a single project with safe file operations and logging."""

    def __init__(self, filename, settings=None, base_dir=None):
        self.filename, self.settings, self.base_dir = filename, settings, base_dir
        logger.debug(f"Initializing ProjectModel for: {self.filename}")
        self.archive_file = (self.settings.get("backup", "archive_location") if self.settings else "") or os.path.join(
            self.base_dir, DEFAULT_ARCHIVE_NAME
        )
        self.trash_file = os.path.join(self.base_dir, DEFAULT_TRASH_NAME)
        self.all_tasks, self.pinned_tasks, self.undo_stack, self.has_unsaved_changes = [], [], [], False
        self.load_success = False

    def load_tasks(self):
        def _load():
            with open(self.filename, "r", encoding="utf-8", errors="replace") as f:
                lines = [line.strip() for line in f if line.strip()]
            self.pinned_tasks, self.all_tasks = [line for line in lines if line.startswith("⭐")], [
                line for line in lines if not line.startswith("⭐")
            ]

        success, _ = safe_file_op(_load)
        self.load_success = success
        return success

    def save_tasks_atomic(self):
        if not self.load_success:
            logger.error(f"Refusing to save {self.filename} because initial load failed.")
            return False

        def _save():
            tempname = None
            try:
                with tempfile.NamedTemporaryFile(
                    "w", dir=os.path.dirname(self.filename), delete=False, encoding="utf-8"
                ) as tf:
                    for t in self.pinned_tasks + self.all_tasks:
                        tf.write(t + "\n")
                    tempname = tf.name
                os.replace(tempname, self.filename)
            except Exception:
                if tempname and os.path.exists(tempname):
                    try:
                        os.remove(tempname)
                    except OSError:
                        pass
                raise

        success, _ = safe_file_op(_save)
        if success:
            self.has_unsaved_changes = False
        return success

    def get_filtered_tasks(self, filter_text=""):
        tasks = self.pinned_tasks + self.all_tasks
        if not filter_text:
            return tasks
        sensitive = self.settings.get("search", "case_sensitive", False) if self.settings else False
        return [t for t in tasks if (filter_text in t if sensitive else filter_text.lower() in t.lower())]

    def add_task(self, txt):
        txt = txt.strip()
        if txt:
            self.all_tasks.append(txt)
            self.has_unsaved_changes = True
            return True
        return False

    def _move_to_external_file(self, txt, target_path, undo_tag):
        """Helper to move a task to an external file (archive/trash)."""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def _append():
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(f"[{now}] {txt}\n")

        success, _ = safe_file_op(_append)
        if success:
            self._remove(txt)
            self.undo_stack.append((undo_tag, txt))
            self.has_unsaved_changes = True
        return success

    def archive_task(self, txt):
        return self._move_to_external_file(txt, self.archive_file, "archive")

    def delete_task(self, txt):
        return self._move_to_external_file(txt, self.trash_file, "delete")

    def _remove(self, txt):
        if txt in self.pinned_tasks:
            self.pinned_tasks.remove(txt)
        elif txt in self.all_tasks:
            self.all_tasks.remove(txt)

    def undo(self):
        if not self.undo_stack:
            return False
        _, txt = self.undo_stack.pop()
        self.all_tasks.append(txt)
        self.has_unsaved_changes = True
        return True

    def toggle_pin(self, txt):
        if txt.startswith("⭐"):
            new = txt[1:].strip()
            if txt in self.pinned_tasks:
                self.pinned_tasks.remove(txt)
                self.all_tasks.append(new)
                self.has_unsaved_changes = True
                return True
        else:
            new = "⭐ " + txt
            if txt in self.all_tasks:
                self.all_tasks.remove(txt)
                self.pinned_tasks.append(new)
                self.has_unsaved_changes = True
                return True
        return False

    def edit_task(self, old, new):
        new = new.strip()
        if not new:
            return False
        for task_list in [self.pinned_tasks, self.all_tasks]:
            if old in task_list:
                task_list[task_list.index(old)] = new
                self.has_unsaved_changes = True
                return True
        return False

    def move_task(self, idx, direction):
        # Determine which list the task belongs to
        if idx < len(self.pinned_tasks):
            target_list = self.pinned_tasks
            list_idx = idx
        else:
            target_list = self.all_tasks
            list_idx = idx - len(self.pinned_tasks)

        # Bounds check within its own list
        if not (0 <= list_idx + direction < len(target_list)):
            return False

        # Swap within the specific list to preserve pinned/unpinned separation
        target_list[list_idx], target_list[list_idx + direction] = (
            target_list[list_idx + direction],
            target_list[list_idx],
        )
        self.has_unsaved_changes = True
        return True
