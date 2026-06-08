"""
Utility functions for project file management and ordering.
"""

import os
from dar_tasks.constants import DAILY_FILENAME, DAILY_TEMPLATE_FILENAME
from dar_tasks.logger import logger

PROJECT_ORDER_FILENAME = ".project_order.txt"


def extract_filename_from_entry(entry):
    """Extract filename from project order entry (handles pin prefix)."""
    return entry[2:] if entry.startswith("⭐ ") else entry


def get_project_display_name(filename, translator=None):
    """Return a user-friendly name for a project file."""
    if filename == DAILY_FILENAME:
        return translator._("daily_tab") if translator else "Daily Tasks"
    return filename[:-4] if filename.endswith(".txt") else filename


def load_project_order(projects_dir):
    """Load the saved project order from the order file."""
    path = os.path.join(projects_dir, PROJECT_ORDER_FILENAME)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return [line.strip() for line in f if line.strip()]
    except (IOError, UnicodeDecodeError):
        return []


def save_project_order(projects_dir, order_entries):
    """Save the project order to the order file."""
    path = os.path.join(projects_dir, PROJECT_ORDER_FILENAME)
    try:
        with open(path, "w", encoding="utf-8") as f:
            for entry in order_entries:
                f.write(entry + "\n")
    except IOError as e:
        logger.error(f"Unable to save project order: {e}")


def get_project_order(projects_dir):
    """Return the current project ordering."""
    try:
        files = [
            f
            for f in os.listdir(projects_dir)
            if f.endswith(".txt") and f not in (DAILY_TEMPLATE_FILENAME, PROJECT_ORDER_FILENAME)
        ]
    except OSError:
        return []
    files_set = set(files)
    saved_order = load_project_order(projects_dir)
    ordered = []
    seen = set()
    for entry in saved_order:
        fname = extract_filename_from_entry(entry)
        if fname in files_set and fname not in seen:
            ordered.append(entry)
            seen.add(fname)
    for fname in sorted(files, key=lambda f: (f != "daily.txt", f.lower())):
        if fname not in seen:
            ordered.append(fname)
    return ordered


def ensure_project_order(projects_dir):
    """Ensure order file exists."""
    order = get_project_order(projects_dir)
    if order and not os.path.exists(os.path.join(projects_dir, PROJECT_ORDER_FILENAME)):
        save_project_order(projects_dir, order)
    return order
