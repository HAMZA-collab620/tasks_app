"""
Global Logging System for Dar Tasks.
Configures file and console logging for the entire application.
"""

import logging
import os
import datetime


def setup_logger(base_dir):
    """Initialize logging configuration."""
    log_dir = os.path.join(base_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, f"app_{datetime.date.today().isoformat()}.log")

    logger = logging.getLogger("DarTasks")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if setup is called multiple times
    if not logger.handlers:
        # File Handler
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)

        # Console Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger


# Create a placeholder logger that will be properly initialized in MainFrame
logger = logging.getLogger("DarTasks")
