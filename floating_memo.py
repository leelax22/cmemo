import sys
from PyQt6.QtWidgets import QApplication
from manager import MemoManager
from utils import setup_file_logging

"""
Floating Memo Application - Entry Point
Refactored for modularity and maintainability.
"""

if __name__ == "__main__":
    logger, log_path = setup_file_logging()

    def _log_unhandled_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = _log_unhandled_exception
    logger.info("CMEMO startup")
    logger.info("Logging to file: %s", log_path)

    app = QApplication(sys.argv)
    # Ensure the app doesn't exit when last window is closed (since tray exists)
    app.setQuitOnLastWindowClosed(False)
    
    manager = MemoManager()
    exit_code = app.exec()
    logger.info("CMEMO shutdown (exit_code=%s)", exit_code)
    sys.exit(exit_code)
