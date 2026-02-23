import sys
import os
import logging
import tempfile
from logging.handlers import RotatingFileHandler

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def setup_file_logging(app_name="CMEMO", log_filename="cmemo.log", logger_name="cmemo"):
    """Configure rotating file logging and return (logger, log_path)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base_dir = os.path.join(local_app_data, app_name) if local_app_data else os.path.join(tempfile.gettempdir(), app_name)
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, log_filename)
    abs_log_path = os.path.abspath(log_path)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    has_handler = False
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and os.path.abspath(getattr(handler, "baseFilename", "")) == abs_log_path:
            has_handler = True
            break

    if not has_handler:
        handler = RotatingFileHandler(
            abs_log_path,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(handler)

    return logger, abs_log_path
