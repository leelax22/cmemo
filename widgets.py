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

    def insertFromMimeData(self, source):
        """
        Override paste behavior to insert plain text only.
        This prevents formatting (fonts, colors, sizes) from being pasted.
        """
        if source.hasText():
            # Get plain text from clipboard and insert it
            self.insertPlainText(source.text())
        else:
            # Fallback to default behavior if no plain text is available
            super().insertFromMimeData(source)

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
