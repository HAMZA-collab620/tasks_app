import os
import sys
import shutil
import json
from dar_tasks.logger import logger


def sanitize_project_name(name):
    """Sanitize project names by allowing only safe characters."""
    return "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()


def get_base_dir():
    """Get the application root directory (handles both frozen and development modes)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    else:
        # File is in dar_tasks/utils.py, so we need to go up one level
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def safe_file_op(op_func, *args, **kwargs):
    """
    Execute a file operation safely and log errors if they occur.
    Returns (True, result) on success, (False, error) on failure.
    """
    try:
        result = op_func(*args, **kwargs)
        return True, result
    except (IOError, OSError, shutil.Error) as e:
        name = op_func.__name__ if hasattr(op_func, "__name__") else "anonymous"
        logger.error(f"File operation failed: {name} - Args: {args} - Error: {e}")
        return False, str(e)


def load_json_data(filename, default=None):
    """Helper to load JSON data from the dar_tasks directory."""
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, filename)
    def _load():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    success, result = safe_file_op(_load)
    return result if success else (default if default is not None else {})
