import sys
from PyQt6.QtWidgets import QApplication
from manager import MemoManager

"""
Floating Memo Application - Entry Point
Refactored for modularity and maintainability.
"""

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Ensure the app doesn't exit when last window is closed (since tray exists)
    app.setQuitOnLastWindowClosed(False)
    
    manager = MemoManager()
    sys.exit(app.exec())
