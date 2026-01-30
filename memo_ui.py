import datetime
import uuid
import os
import sys
import ctypes
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QFrame, QLineEdit, QMessageBox, QDialog, QApplication)
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, QEvent
from PyQt6.QtGui import QFont, QCursor
from widgets import NoteTextEdit
from utils import resource_path

class FloatingMemo(QWidget):
    """
    Individual floating memo window with collapsible header and styling.
    """
    closed = pyqtSignal(str)
    content_changed = pyqtSignal()
    font_requested = pyqtSignal(str)
    font_size_requested = pyqtSignal(int)
    theme_requested = pyqtSignal(str)

    def __init__(self, memo_id=None, settings=None, font_family="Pretendard"):
        super().__init__()
        self.memo_id = memo_id or str(uuid.uuid4())
        self.font_family = font_family
        self._last_theme = "기본형"
        
        # Default Settings
        now = datetime.datetime.now()
        default_title = now.strftime("%Y-%m-%d %H:%M")
        
        self.settings = {
            "title": default_title,
            "content": "",
            "bg_color": "rgba(255, 253, 190, 255)", 
            "x": 100, "y": 100, "w": 320, "h": 280,
            "is_collapsed": False,
            "saved_height": 420,
            "saved_width": 320,
            "is_pinned": False,
            "last_modified": ""
        }
        if settings:
            self.settings.update(settings)

        self._drag_pos = QPoint()
        self._resizing = False
        self._resize_dir = 0
        self._edge_margin = 12 
        self._corner_margin = 40 
            
        self.initUI()
        self.apply_settings()

    def initUI(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        if self.settings.get("is_pinned", False):
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QFrame()
        self.container.setObjectName("MainContainer")
        
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        
        self.header_container = QWidget()
        self.header_container.setObjectName("HeaderContainer")
        self.title_bar = QHBoxLayout(self.header_container)
        self.title_bar.setContentsMargins(10, 5, 10, 5)
        self.title_bar.setSpacing(5)
        
        self.title_container = QWidget()
        self.title_container.setMouseTracking(True)
        self.title_container_layout = QHBoxLayout(self.title_container)
        self.title_container_layout.setContentsMargins(0, 0, 0, 0)
        self.title_container_layout.setSpacing(5)
        
        self.title_label = QLabel(self.settings["title"])
        self.title_label.setMinimumWidth(80) 
        self.title_label.setStyleSheet(f"QLabel {{ font-family: '{self.font_family}'; font-size: 13px; font-weight: bold; color: black; background: transparent; }}")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.edit_title_btn = QPushButton("✏️")
        self.edit_title_btn.setFixedSize(20, 20)
        self.edit_title_btn.setStyleSheet("QPushButton { background: transparent; border: none; font-size: 12px; } QPushButton:hover { background: rgba(0,0,0,20); border-radius: 10px; }")
        self.edit_title_btn.hide()
        self.edit_title_btn.clicked.connect(self.perform_edit_start)

        self.title_edit = QLineEdit()
        self.title_edit.hide() 
        self.title_edit.setStyleSheet(f"QLineEdit {{ background: rgba(255,255,255,100); border-radius: 4px; font-family: '{self.font_family}'; font-size: 13px; font-weight: normal; }}")
        self.title_edit.editingFinished.connect(self.on_title_editing_finished)
        
        self.title_container_layout.addWidget(self.title_label)
        self.title_container_layout.addWidget(self.edit_title_btn)
        self.title_container_layout.addWidget(self.title_edit)

        self.title_container.installEventFilter(self)
        
        # macOS traffic lights
        self.mac_traffic_lights = QWidget()
        self.mac_traffic_lights.setFixedSize(60, 20)
        self.mac_layout = QHBoxLayout(self.mac_traffic_lights)
        self.mac_layout.setContentsMargins(0, 0, 0, 0)
        self.mac_layout.setSpacing(8)
        
        self.mac_close = QPushButton()
        self.mac_minimize = QPushButton()
        self.mac_zoom = QPushButton()
        
        for btn, color, hover in zip(
            [self.mac_close, self.mac_minimize, self.mac_zoom], 
            ["#ff5f56", "#ffbd2e", "#27c93f"],
            ["#e04a42", "#e0a526", "#1eab33"]
        ):
            btn.setFixedSize(12, 12)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {color}; border-radius: 6px; border: 1px solid rgba(0,0,0,0.1); }}
                QPushButton:hover {{ background-color: {hover}; }}
            """)
            self.mac_layout.addWidget(btn)
            
        self.mac_traffic_lights.hide()
        self.mac_close.clicked.connect(self.request_delete)
        
        self.pin_button = QPushButton("📌")
        self.pin_button.setFixedSize(26, 26)
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(self.settings["is_pinned"])
        self.pin_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.pin_button.setStyleSheet(self.get_btn_style())
        self.pin_button.clicked.connect(self.toggle_pin)

        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(26, 26)
        self.add_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_button.setStyleSheet(self.get_btn_style())

        self.settings_button = QPushButton("≡") 
        self.settings_button.setFixedSize(26, 26)
        self.settings_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.settings_button.setStyleSheet(self.get_btn_style())

        self.delete_button = QPushButton("×")
        self.delete_button.setFixedSize(26, 26)
        self.delete_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.delete_button.setStyleSheet(self.get_btn_style("rgba(255, 80, 80, 180)"))
        self.delete_button.clicked.connect(self.request_delete)
        
        self.title_bar.addWidget(self.mac_traffic_lights)
        self.title_bar.addWidget(self.title_container, 1)
        self.title_bar.addWidget(self.pin_button)
        self.title_bar.addWidget(self.add_button)
        self.title_bar.addWidget(self.settings_button)
        self.title_bar.addWidget(self.delete_button)
        
        self.container_layout.addWidget(self.header_container)
        
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(15, 10, 15, 15)
        self.content_layout.setSpacing(8)

        self.text_editor = NoteTextEdit()
        self.text_editor.setPlaceholderText("여기에 메모하세요...")
        
        # Optimization: Set static scrollbar style once
        self.text_editor.setStyleSheet("""
            QScrollBar:vertical { 
                border: none; background: transparent; width: 5px; margin: 0px;
            }
            QScrollBar::handle:vertical { 
                background: rgba(0, 0, 0, 15); border-radius: 2px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { 
                background: rgba(0, 0, 0, 40); 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)
        self.text_editor.textChanged.connect(self.on_text_modified)
        
        self.timestamp_layout = QHBoxLayout()
        self.timestamp_layout.setContentsMargins(0, 0, 0, 0)
        self.timestamp_label = QLabel("")
        self.timestamp_label.setStyleSheet(f"QLabel {{ font-family: '{self.font_family}'; font-size: 10px; color: rgba(0, 0, 0, 60); background: transparent; }}")
        self.timestamp_layout.addStretch()
        self.timestamp_layout.addWidget(self.timestamp_label)
        
        self.content_layout.addWidget(self.text_editor)
        self.content_layout.addLayout(self.timestamp_layout)

        self.container_layout.addWidget(self.content_area)

        self.mod_timer = QTimer(self)
        self.mod_timer.setSingleShot(True)
        self.mod_timer.timeout.connect(self.update_timestamp)

        self.main_layout.addWidget(self.container)
        self.setLayout(self.main_layout)
        
        self.setMinimumSize(320, 80) 

    def get_btn_style(self, hover_color="rgba(0,0,0,40)"):
        return f"""
            QPushButton {{ 
                background: transparent; 
                border: none; 
                font-size: 14px; 
                border-radius: 13px; 
                color: rgba(0, 0, 0, 180); 
            }}
            QPushButton:hover {{ 
                background: {hover_color}; 
                color: rgba(0, 0, 0, 255);
            }}
            QPushButton:checked {{ 
                background: rgba(0, 0, 0, 70); 
                color: white; 
            }}
        """

    def eventFilter(self, obj, event):
        if obj == self.title_container:
            if event.type() == QEvent.Type.Enter:
                self.edit_title_btn.show()
            elif event.type() == QEvent.Type.Leave:
                self.edit_title_btn.hide()
        return super().eventFilter(obj, event)

    def perform_edit_start(self):
        self.title_label.hide()
        self.edit_title_btn.hide()
        self.title_edit.setText(self.settings["title"])
        self.title_edit.show()
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def on_text_modified(self):
        new_text = self.text_editor.toPlainText()
        if new_text != self.settings.get("content", ""):
            self.mod_timer.start(10000) # Update timestamp after 10s of inactivity
            self.content_changed.emit()

    def update_timestamp(self):
        now = datetime.datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M")
        self.settings["last_modified"] = ts
        self.timestamp_label.setText(f"Last Modified : {ts}")
        self.content_changed.emit()

    def on_title_editing_finished(self):
        new_title = self.title_edit.text().strip()
        if new_title:
            self.settings["title"] = new_title
            self.title_label.setText(new_title)
            self.update_elided_title()
            self.content_changed.emit()
        self.title_edit.hide()
        self.title_label.show()

    def update_elided_title(self):
        # Allow layout to settle for accurate width
        QApplication.processEvents()
        
        width = self.title_label.width()
        # If collapsed, we might need to be more aggressive or use a different width basis
        # But generally trusting the label width is correct if layout is up to date.
        
        metrics = self.title_label.fontMetrics()
        elided = metrics.elidedText(self.settings["title"], Qt.TextElideMode.ElideRight, width)
        self.title_label.setText(elided)

    def resizeEvent(self, event):
        self.update_elided_title()
        super().resizeEvent(event)

    def toggle_pin(self, checked):
        self.settings["is_pinned"] = checked
        
        # Save state to prevent jumpy movement during recreation
        is_visible = self.isVisible()
        curr_geom = self.geometry()
        
        # 1. Update Qt flag (triggers handle recreation on Windows)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        
        if is_visible:
            # 2. Re-apply geometry and show
            self.setGeometry(curr_geom)
            self.show()
            self.raise_()
            self.activateWindow()
        
        if sys.platform == "win32":
            try:
                # 3. Explicitly bring to front across all applications
                hwnd = int(self.winId())
                
                # SWP_NOSIZE (1) | SWP_NOMOVE (2) | SWP_SHOWWINDOW (64) | SWP_NOOWNERZORDER (512)
                flags = 0x0001 | 0x0002 | 0x0040 | 0x0200
                
                # HWND_TOPMOST = -1, HWND_NOTOPMOST = -2
                ctypes.windll.user32.SetWindowPos(hwnd, -1 if checked else -2, 0, 0, 0, 0, flags)
                
                # 4. Hammer the foreground focus if pinning
                if checked:
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
                
        self.content_changed.emit()

    def show_and_raise(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.header_container.underMouse():
                self.toggle_collapse()
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        if self.settings.get("is_collapsed", False) and not getattr(self, "_is_preview", False):
            self._is_preview = True
            self.set_collapsed_ui(False)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if getattr(self, "_is_preview", False):
            self._is_preview = False
            self.set_collapsed_ui(True)
        super().leaveEvent(event)

    def toggle_collapse(self):
        new_state = not self.settings["is_collapsed"]
        self.settings["is_collapsed"] = new_state
        if new_state:
            self.settings["saved_height"] = self.height()
            self.settings["saved_width"] = self.width()
        
        self._is_preview = False 
        self.set_collapsed_ui(new_state)
        self.content_changed.emit()

    def set_collapsed_ui(self, is_collapsed):
        if is_collapsed:
            self.content_area.hide()
            self.pin_button.hide()
            self.add_button.hide()
            self.settings_button.hide()
            self.delete_button.hide()
            
            metrics = self.title_label.fontMetrics()
            text_w = metrics.horizontalAdvance(self.settings["title"])
            new_w = max(120, text_w + 40)
            
            self.setMinimumWidth(0)
            self.setFixedSize(new_w, 40)
            
            # Hide macOS traffic lights if they exist
            if hasattr(self, 'mac_traffic_lights'):
                self.mac_traffic_lights.hide()
                
        else:
            self.setMinimumSize(320, 250)
            self.setMaximumSize(2000, 2000)
            
            saved_w = self.settings.get("saved_width", 320)
            saved_h = self.settings.get("saved_height", 420)
            self.resize(saved_w, saved_h)
            
            self.content_area.show()
            self.pin_button.show()
            
            # Restore visibility based on theme
            theme = getattr(self, "_last_theme", "기본형")
            if theme == "macOS":
                if hasattr(self, 'mac_traffic_lights'):
                    self.mac_traffic_lights.show()
            else:
                self.add_button.show()
                self.settings_button.show()
                self.delete_button.show()
        
        actual_state = self.settings["is_collapsed"]
        self.settings["is_collapsed"] = is_collapsed
        self.update_style()
        self.update_elided_title() # Recalculate title after size change
        self.settings["is_collapsed"] = actual_state

    def set_bg_color(self, rgba):
        self.settings["bg_color"] = rgba
        self.update_style()
        self.content_changed.emit()

    def update_font(self, family_name, display_name=None, size=None, title_size=13, title_bold=True):
        self.font_family = family_name
        safe_font = f"'{family_name}'"
        
        # Cache text font size
        font_size = size or getattr(self, "_last_font_size", 14)
        self._last_font_size = font_size
        
        # Cache title settings if valid args provided, otherwise use last known
        if title_size is not None: self._last_title_size = title_size
        else: title_size = getattr(self, "_last_title_size", 13)
            
        if title_bold is not None: self._last_title_bold = title_bold
        else: title_bold = getattr(self, "_last_title_bold", True)
        
        theme = getattr(self, "_last_theme", "기본형")
        title_color = "white" if theme == "윈도우98" else "black"
        editor_bg = "white" if theme == "윈도우98" else "transparent"
        editor_border = "2px solid #808080" if theme == "윈도우98" else "none"

        title_weight = 'bold' if title_bold else 'normal'
        self.title_label.setStyleSheet(f"font-family: {safe_font}; font-size: {title_size}px; font-weight: {title_weight}; color: {title_color}; background: transparent;")
        self.title_edit.setStyleSheet(f"background: rgba(255,255,255,100); border-radius: 4px; font-family: {safe_font}; font-size: {title_size}px; font-weight: normal;")
        
        # Use static base + dynamic part to prevent stylesheet bloating
        base_style = """
            QScrollBar:vertical { border: none; background: transparent; width: 5px; margin: 0px; }
            QScrollBar::handle:vertical { background: rgba(0, 0, 0, 15); border-radius: 2px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: rgba(0, 0, 0, 40); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """
        self.text_editor.setStyleSheet(base_style + f"""
            NoteTextEdit {{
                background: {editor_bg}; border: {editor_border};
                font-family: {safe_font}; font-size: {font_size}px; color: #2c3e50;
            }}
        """)
        self.timestamp_label.setStyleSheet(f"font-family: {safe_font}; font-size: 10px; color: rgba(0, 0, 0, 60); background: transparent;")
        
        # Enforce font objects
        t_font = QFont(family_name, title_size)
        t_font.setBold(title_bold)
        self.title_label.setFont(t_font)
        
        c_font = QFont(family_name, max(1, font_size))
        self.title_edit.setFont(c_font)
        self.text_editor.setFont(c_font)
        self.update_elided_title()

    def update_style(self, theme=None):
        if theme: self._last_theme = theme
        theme = getattr(self, "_last_theme", "기본형")
        
        is_collapsed = self.settings.get("is_collapsed", False)
        bg_color_str = self.settings["bg_color"]
        if theme == "윈도우98": bg_color_str = "#c0c0c0"
        elif theme == "macOS": bg_color_str = "#f6f6f6"

        self.text_editor.show_lines = False 
        self.text_editor.viewport().update()
        
        # Reset traffic lights and button visibility
        if theme == "macOS":
            self.mac_traffic_lights.show()
            self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            # Hide standard buttons for macOS
            self.add_button.hide()
            self.settings_button.hide()
            self.delete_button.hide()
            # Move traffic lights to the right
            self.title_bar.removeWidget(self.mac_traffic_lights)
            self.title_bar.insertWidget(self.title_bar.count(), self.mac_traffic_lights)
        else:
            self.mac_traffic_lights.hide()
            self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            # Show standard buttons
            self.add_button.show()
            self.settings_button.show()
            self.delete_button.show()
            # Move traffic lights back to the left
            self.title_bar.removeWidget(self.mac_traffic_lights)
            self.title_bar.insertWidget(0, self.mac_traffic_lights)

        # Reset fonts and specialized UI colors
        self.update_font(self.font_family, size=getattr(self, "_last_font_size", 14), 
                         title_size=getattr(self, "_last_title_size", 13),
                         title_bold=getattr(self, "_last_title_bold", True))

        # Button styles
        if theme == "윈도우98":
            btn_style = """
                QPushButton {
                    background-color: #c0c0c0; border: 1px solid;
                    border-top-color: #ffffff; border-left-color: #ffffff;
                    border-right-color: #808080; border-bottom-color: #808080;
                    color: black; border-radius: 0px; font-size: 13px;
                }
                QPushButton:pressed, QPushButton:checked {
                    background-color: #d0d0d0;
                    border-top-color: #808080; border-left-color: #808080;
                    border-right-color: #ffffff; border-bottom-color: #ffffff;
                    padding-top: 1px; padding-left: 1px;
                }
            """
            for btn in [self.add_button, self.pin_button, self.settings_button]:
                btn.setStyleSheet(btn_style)
            self.delete_button.setStyleSheet(btn_style.replace("color: black;", "color: red;"))
        elif theme == "macOS":
            btn_style = """
                QPushButton {
                    background: transparent; border: none; font-size: 14px; 
                    border-radius: 4px; color: #555;
                }
                QPushButton:hover { background: rgba(0,0,0,10); color: black; }
                QPushButton:checked { background: rgba(0,0,0,40); color: black; }
            """
            for btn in [self.add_button, self.pin_button, self.settings_button, self.delete_button]:
                btn.setStyleSheet(btn_style)
        else:
            self.add_button.setStyleSheet(self.get_btn_style())
            self.pin_button.setStyleSheet(self.get_btn_style())
            self.settings_button.setStyleSheet(self.get_btn_style())
            self.delete_button.setStyleSheet(self.get_btn_style("rgba(255, 80, 80, 180)"))

        border_css = "1px solid rgba(0, 0, 0, 40)"
        if is_collapsed:
            border_css = "1px solid rgba(0, 0, 0, 180)"

        if theme == "윈도우98":
            radius = "0px"
            container_style = "background-color: #c0c0c0; border: 2px solid; border-top-color: #ffffff; border-left-color: #ffffff; border-right-color: #404040; border-bottom-color: #404040;"
            self.header_container.setStyleSheet("background-color: #000080; border-bottom: 1px solid #c0c0c0;")
        elif theme == "macOS":
            radius = "12px"
            container_style = f"background-color: {bg_color_str}; border-radius: 12px; border: none;"
            self.header_container.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f0f0f0, stop:1 #e8e8e8); border-top-left-radius: 11px; border-top-right-radius: 11px; border-bottom: none;")
        elif theme == "둥근형":
            radius = "12px"
            container_style = f"background-color: {bg_color_str}; border-radius: {radius}; border: {border_css};"
            self.header_container.setStyleSheet("background: transparent;")
        elif "헤더분리형" in theme:
            is_rounded = "둥근형" in theme
            radius = "12px" if is_rounded else "2px"
            inner_radius = 11 if is_rounded else 1
            header_bg = "white"
            container_style = f"background-color: {bg_color_str}; border-radius: {radius}; border: {border_css};"
            
            if is_collapsed:
                header_rounding = f"border-radius: {inner_radius}px;"
            else:
                header_rounding = f"border-top-left-radius: {inner_radius}px; border-top-right-radius: {inner_radius}px; border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;"
            self.header_container.setStyleSheet(f"background: {header_bg}; {header_rounding}")
        else:
            radius = "2px"
            container_style = f"background-color: {bg_color_str}; border-radius: {radius}; border: {border_css};"
            self.header_container.setStyleSheet("background: transparent;")

        self.container.setStyleSheet(f"QFrame#MainContainer {{ {container_style} }}")

    def get_resize_dir(self, pos):
        direction = 0
        rect = self.rect()
        m = self._edge_margin
        cm = self._corner_margin

        if pos.x() < cm and pos.y() < cm: return 1 | 4
        if pos.x() > rect.width() - cm and pos.y() < cm: return 2 | 4
        if pos.x() < cm and pos.y() > rect.height() - cm: return 1 | 8
        if pos.x() > rect.width() - cm and pos.y() > rect.height() - cm: return 2 | 8

        if pos.x() < m: direction |= 1
        if pos.x() > rect.width() - m: direction |= 2
        if pos.y() < m: direction |= 4
        if pos.y() > rect.height() - m: direction |= 8
        return direction

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self._resize_dir = self.get_resize_dir(pos)
            if self._resize_dir and not self.settings["is_collapsed"]:
                self._resizing = True
                self._initial_geo = self.geometry()
                self._initial_mouse_pos = event.globalPosition().toPoint()
            else:
                self._resizing = False
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        g_pos = event.globalPosition().toPoint()
        
        if not self._resizing:
            dist = min(pos.x(), self.width()-pos.x(), pos.y(), self.height()-pos.y())
            if dist < self._edge_margin + 10 and not self.settings["is_collapsed"]:
                d = self.get_resize_dir(pos)
                if (d == 5) or (d == 10): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                elif (d == 6) or (d == 9): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                elif d & 1 or d & 2: self.setCursor(Qt.CursorShape.SizeHorCursor)
                elif d & 4 or d & 8: self.setCursor(Qt.CursorShape.SizeVerCursor)
                else: self.setCursor(Qt.CursorShape.ArrowCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

        if self._resizing:
            dx = g_pos.x() - self._initial_mouse_pos.x()
            dy = g_pos.y() - self._initial_mouse_pos.y()
            x, y, w, h = self._initial_geo.x(), self._initial_geo.y(), self._initial_geo.width(), self._initial_geo.height()
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            if self._resize_dir & 1: 
                new_w = max(min_w, w - dx)
                x = x + (w - new_w)
                w = new_w
            if self._resize_dir & 2: w = max(min_w, w + dx)
            if self._resize_dir & 4: 
                new_h = max(min_h, h - dy)
                y = y + (h - new_h)
                h = new_h
            if self._resize_dir & 8: h = max(min_h, h + dy)
            self.setGeometry(x, y, w, h)
        elif event.buttons() == Qt.MouseButton.LeftButton:
            self.move(g_pos - self._drag_pos)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._resizing = False
        self.content_changed.emit()
        event.accept()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.content_changed.emit()

    def apply_settings(self):
        self.title_label.setText(self.settings.get("title", ""))
        self.text_editor.blockSignals(True)
        self.text_editor.setPlainText(self.settings.get("content", ""))
        self.text_editor.blockSignals(False)
        self.setWindowOpacity(1.0)
        
        self.move(self.settings.get("x", 100), self.settings.get("y", 100))
        self.resize(self.settings.get("w", 320), self.settings.get("h", 420))
        if self.settings.get("is_collapsed", False):
            self.set_collapsed_ui(True)
        
        last_mod = self.settings.get("last_modified", "")
        if last_mod:
            self.timestamp_label.setText(f"Last Modified : {last_mod}")
        else:
            self.timestamp_label.setText("")
            
        self.show()
        
        # Apply pin state after show to ensure window handle is ready and flags apply
        pin_state = self.settings.get("is_pinned", False)
        self.pin_button.setChecked(pin_state)
        self.toggle_pin(pin_state)

    def get_current_settings(self):
        for k in ["font_family", "font_size", "theme"]:
            if k in self.settings: del self.settings[k]
            
        self.settings.update({
            "content": self.text_editor.toPlainText(),
            "x": self.x(), "y": self.y(),
            "w": self.width(), "h": self.height()
        })
        return self.settings

    def request_delete(self):
        # Frameless Elegant Delete Dialog (Solid White)
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog | Qt.WindowType.Tool)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        d_w, d_h = 280, 160
        dialog.setFixedSize(d_w, d_h)
        
        # Center dialog relative to this memo
        memo_rect = self.geometry()
        center_x = memo_rect.x() + (memo_rect.width() - d_w) // 2
        center_y = memo_rect.y() + (memo_rect.height() - d_h) // 2
        dialog.move(center_x, center_y)

        # Use a container frame to ensure a solid white background even with transparency enabled for rounded corners
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{ 
                background-color: white; 
                border: 1px solid #ced4da; 
                border-radius: 12px; 
            }}
        """)
        main_layout.addWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("메모 삭제")
        title.setStyleSheet(f"font-family: '{self.font_family}'; font-size: 16px; font-weight: bold; color: black; background: transparent; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        sub_title = QLabel("이 작업은 되돌릴 수 없습니다.")
        sub_title.setStyleSheet(f"font-family: '{self.font_family}'; font-size: 12px; color: #636e72; background: transparent; border: none;")
        sub_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title)
        layout.addWidget(sub_title)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        def get_diag_btn_style(bg, color, hover):
            return f"""
                QPushButton {{
                    background-color: {bg};
                    color: {color};
                    border: none;
                    border-radius: 6px;
                    font-family: '{self.font_family}';
                    font-size: 13px;
                    font-weight: 500;
                    height: 36px;
                }}
                QPushButton:hover {{ background-color: {hover}; }}
            """

        cancel_btn = QPushButton("취소")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(get_diag_btn_style("#f1f3f4", "#3c4043", "#e8eaed"))
        cancel_btn.clicked.connect(dialog.reject)
        
        delete_btn = QPushButton("삭제")
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet(get_diag_btn_style("#d93025", "white", "#c5221f"))
        delete_btn.clicked.connect(dialog.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(delete_btn)
        
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.closed.emit(self.memo_id)
            self.close()
