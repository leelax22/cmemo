from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QPainter, QPen, QColor

class NoteTextEdit(QTextEdit):
    """
    Custom QTextEdit with optional line guides for a notepad feel.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_lines = False
        self.line_height = 28
        self.viewport().setAutoFillBackground(False)

    def paintEvent(self, event):
        if self.show_lines:
            painter = QPainter(self.viewport())
            painter.setPen(QPen(QColor(0, 0, 0, 30), 1))
            
            # Draw lines only for the visible area
            offset = self.verticalScrollBar().value() % self.line_height
            height = self.viewport().height()
            
            # Start from the first partially visible line
            for y in range(self.line_height - offset, height + self.line_height, self.line_height):
                painter.drawLine(0, y, self.viewport().width(), y)
                
        super().paintEvent(event)
