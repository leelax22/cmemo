import os
import json
import random
import sys
import datetime
import keyboard
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import (QApplication, QMenu, QSystemTrayIcon, QStyle, QFileDialog, 
                             QMessageBox, QDialog, QTextBrowser, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QFrame, QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QWidget)
from PyQt6.QtCore import Qt, QTimer, QDateTime, QBuffer, QPointF, QAbstractNativeEventFilter
from croniter import croniter
from PyQt6.QtGui import QColor, QFont, QCursor, QAction, QPixmap, QPainter, QPen, QIcon, QFontDatabase, QPolygonF, QBrush
from memo_ui import FloatingMemo
from utils import resource_path

class PowerEventFilter(QAbstractNativeEventFilter):
    """
    Listens for Windows power events to re-register hotkeys after sleep/resume.
    """
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.WM_POWERBROADCAST = 0x0218
        self.PBT_APMRESUMEAUTOMATIC = 0x0012
        self.PBT_APMRESUMESUSPEND = 0x0007

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == self.WM_POWERBROADCAST:
                if msg.wParam in [self.PBT_APMRESUMEAUTOMATIC, self.PBT_APMRESUMESUSPEND]:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] System resume detected. Resetting hotkeys...")
                    # Delay to ensure system input handles are ready
                    QTimer.singleShot(3000, self.manager.setup_hotkeys)
        return False, 0

class MemoManager:
    """
    Main controller for managing multiple memos, hotkeys, tray, and storage.
    """
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.path_config_file = os.path.join(self.base_dir, "path_config.json")
        self.save_file = os.path.join(self.base_dir, "memo_storage.json")
        
        if os.path.exists(self.path_config_file):
            try:
                with open(self.path_config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    custom_path = cfg.get("last_storage_path")
                    if custom_path and os.path.exists(os.path.dirname(custom_path)):
                        self.save_file = custom_path
            except: pass

        self.memos = {}
        self.assets_dir = resource_path("assets")
        self._font_cache = {}
        self._icon_cache = {}
        self.fonts = self.scan_fonts()
        self.current_font = "Pretendard"
        self.current_font_size = 14
        self.title_font_size = 13
        self.title_bold = True
        self.current_theme = "기본형"
        self.pastel_colors = [
            ("노란색", "rgba(255,253,190,255)"), ("분홍색", "rgba(255,204,213,255)"),
            ("파란색", "rgba(189,224,254,255)"), ("연두색", "rgba(204,255,204,255)"),
            ("보라색", "rgba(234,196,213,255)"), ("오렌지색", "rgba(255,229,180,255)"),
            ("민트색", "rgba(186,255,201,255)"), ("하늘색", "rgba(160,210,235,255)")
        ]
        # UI Icon Paths (Using static assets)
        self.ui_icons = {
            "arrow_down": os.path.join(self.assets_dir, "ui_arrow_down.png").replace("\\", "/"),
            "arrow_up": os.path.join(self.assets_dir, "ui_arrow_up.png").replace("\\", "/"),
            "check": os.path.join(self.assets_dir, "ui_check.png").replace("\\", "/")
        }

        # Initialize Save Timer (Debounce for File I/O)
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._perform_save)

        # Auto Backup Settings (default)
        self.auto_backup_config = {
            "enabled": False,
            "cron": "0 * * * *", # Every hour
            "folder": os.path.normpath(os.path.join(self.base_dir, "backups")),
            "retention": 5
        }
        self.load_auto_backup_config()
        
        # Start Backup Timer (Check every minute)
        self.backup_check_timer = QTimer()
        self.backup_check_timer.timeout.connect(self.check_scheduled_backup)
        self.backup_check_timer.start(60000) # 60 seconds
        self._last_backup_time = None
        
        # Load Existing State
        self.load_memos()
        if not self.memos: self.create_new_memo()
        
        self.setup_hotkeys()
        
        # Install power event filter for resume from sleep
        self.power_filter = PowerEventFilter(self)
        QApplication.instance().installNativeEventFilter(self.power_filter)
        
        self.setup_tray()

    def scan_fonts(self):
        fonts = {}
        if os.path.exists(self.assets_dir):
            for f in os.listdir(self.assets_dir):
                if f.endswith(('.ttf', '.otf')):
                    name = os.path.splitext(f)[0]
                    fonts[name] = os.path.join(self.assets_dir, f)
        return fonts

    def get_font_name(self, name):
        if name in self._font_cache: return self._font_cache[name]
        
        if name in self.fonts:
            font_path = self.fonts[name]
            fid = QFontDatabase.addApplicationFont(font_path)
            if fid != -1:
                families = QFontDatabase.applicationFontFamilies(fid)
                if families:
                    self._font_cache[name] = families[0]
                    return families[0]
        return name

    def create_new_memo(self, settings=None, memo_id=None):
        if settings is None:
            _, rgba = random.choice(self.pastel_colors)
            settings = {"bg_color": rgba}
        
        disp_name = self.current_font
        family_name = self.get_font_name(disp_name)
        
        memo = FloatingMemo(memo_id=memo_id, settings=settings, font_family=family_name)
        memo.closed.connect(self.delete_memo)
        memo.content_changed.connect(self.save_memos)
        memo.font_requested.connect(self.apply_global_font)
        memo.font_size_requested.connect(self.apply_global_font_size)
        memo.theme_requested.connect(self.apply_global_theme)
        memo.add_button.clicked.connect(lambda: self.create_new_memo())
        memo.settings_button.clicked.connect(lambda: self.show_custom_settings(memo))
        # macOS specialized dots
        memo.mac_zoom.clicked.connect(lambda: self.create_new_memo())
        memo.mac_minimize.clicked.connect(lambda: self.show_custom_settings(memo))
        
        self.memos[memo.memo_id] = memo
        
        memo.update_font(family_name, size=self.current_font_size, 
                         title_size=self.title_font_size, 
                         title_bold=self.title_bold)
        memo.update_style(theme=self.current_theme)
        
        self.save_memos()

    def get_color_icon(self, rgba_str):
        clean = rgba_str.replace(" ", "")
        if clean in self._icon_cache: return self._icon_cache[clean]
        try:
            parts = clean.replace("rgba(", "").replace(")", "").split(",")
            color = QColor(int(parts[0]), int(parts[1]), int(parts[2]), 255)
        except: color = QColor("white")
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(color)
        p.setPen(QPen(QColor(0,0,0,40), 1))
        p.drawEllipse(4,4,16,16)
        p.end()
        icon = QIcon(pixmap)
        self._icon_cache[clean] = icon
        return icon

    def show_custom_settings(self, memo):
        menu = QMenu(memo)
        menu.setStyleSheet("""
            QMenu { 
                icon-size: 16px; 
                background-color: white; 
                border: 1px solid rgba(0,0,0,80);
                border-radius: 0px;
                padding: 2px;
            }
            QMenu::item { 
                padding: 4px 20px 4px 10px; 
                border-radius: 0px;
                background-color: transparent;
                margin: 0px;
            }
            QMenu::item:selected { 
                background-color: rgba(0,0,0,10);
                color: black;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(0,0,0,20);
                margin: 2px 4px;
            }
            QMenu::indicator {
                width: 14px;
                height: 14px;
                margin-left: 2px;
            }
        """)
        
        color_menu = menu.addMenu("🎨 배경색 선택")
        current_color = memo.settings.get("bg_color", "").replace(" ", "")
        for name, rgba in self.pastel_colors:
            action = QAction(name, memo)
            action.setCheckable(True)
            if rgba.replace(" ", "") == current_color:
                action.setChecked(True)
            action.setIcon(self.get_color_icon(rgba))
            action.triggered.connect(lambda checked, r=rgba: memo.set_bg_color(r))
            color_menu.addAction(action)

        font_menu = menu.addMenu("🔠 글꼴 변경")
        for disp in self.fonts:
            action = QAction(disp, memo)
            action.setCheckable(True)
            if disp == self.current_font:
                action.setChecked(True)
            action.triggered.connect(lambda checked, f=disp: self.apply_global_font(f))
            font_menu.addAction(action)

        title_size_menu = menu.addMenu("📏 제목 폰트 크기")
        for s in [9, 10, 11, 12, 13, 14, 16, 18, 20]:
            action = QAction(f"{s}pt", memo)
            action.setCheckable(True)
            if s == self.title_font_size:
                action.setChecked(True)
            action.triggered.connect(lambda checked, sz=s: self.apply_global_title_font_size(sz))
            title_size_menu.addAction(action)

        title_bold_action = QAction("🔠 제목 폰트 Bold 설정", memo)
        title_bold_action.setCheckable(True)
        title_bold_action.setChecked(self.title_bold)
        title_bold_action.triggered.connect(self.apply_global_title_bold)
        menu.addAction(title_bold_action)

        size_menu = menu.addMenu("📏 내용 폰트 크기")
        for s in [9, 10, 11, 12, 14, 16, 18, 20, 24]:
            action = QAction(f"{s}pt", memo)
            action.setCheckable(True)
            if s == self.current_font_size:
                action.setChecked(True)
            action.triggered.connect(lambda checked, sz=s: self.apply_global_font_size(sz))
            size_menu.addAction(action)

        theme_menu = menu.addMenu("🖼️ 테마 변경")
        for t in ["기본형", "둥근형", "헤더분리형", "헤더분리형(둥근형)", "윈도우98", "macOS"]:
            action = QAction(t, memo)
            action.setCheckable(True)
            if t == self.current_theme:
                action.setChecked(True)
            action.triggered.connect(lambda checked, tn=t: self.apply_global_theme(tn))
            theme_menu.addAction(action)

        auto_backup_action = QAction("📅 정기 백업 설정", memo)
        auto_backup_action.triggered.connect(self.show_auto_backup_settings)
        menu.addAction(auto_backup_action)
            
        storage_menu = menu.addMenu("📁 저장 및 백업 관리")
        
        # Display current folder path (Disabled action)
        current_dir = os.path.dirname(self.save_file)
        current_path_action = QAction(f"📍 폴더: ...{current_dir[-25:] if len(current_dir) > 25 else current_dir}", memo)
        current_path_action.setEnabled(False)
        current_path_action.setToolTip(f"전체 경로: {self.save_file}")
        storage_menu.addAction(current_path_action)
        
        storage_menu.addSeparator()
        
        storage_menu.addAction("💾 저장 위치 변경").triggered.connect(lambda: self.change_storage_path(memo))
        storage_menu.addAction("📁 백업 데이터 불러오기").triggered.connect(lambda: self.load_backup_file(memo))
        storage_menu.addAction("📤 현재 데이터 백업").triggered.connect(lambda: self.backup_current_data(memo))
        
        storage_menu.addSeparator()
        
        storage_menu.addAction("⚙️ 설정 파일 백업 (path_config)").triggered.connect(lambda: self.backup_path_config(memo))
        storage_menu.addAction("📅 정기 백업 설정").triggered.connect(lambda: self.show_auto_backup_settings())
        
        menu.exec(QCursor.pos())

    def apply_global_font(self, font_name):
        self.current_font = font_name
        self.refresh_all_memos_style()
        self.save_memos()

    def apply_global_font_size(self, size):
        self.current_font_size = size
        self.refresh_all_memos_style()
        self.save_memos()

    def apply_global_title_font_size(self, size):
        self.title_font_size = size
        self.refresh_all_memos_style()
        self.save_memos()

    def apply_global_title_bold(self, checked):
        self.title_bold = checked
        self.refresh_all_memos_style()
        self.save_memos()
        self.save_memos()

    def refresh_all_memos_style(self):
        actual = self.get_font_name(self.current_font)
        for m in self.memos.values():
            m.update_font(actual, size=self.current_font_size, 
                         title_size=self.title_font_size, 
                         title_bold=self.title_bold)
            m.update_style(theme=self.current_theme)

    def apply_global_theme(self, theme_name):
        self.current_theme = theme_name
        for m in self.memos.values():
            m.update_style(theme=theme_name)
        self.save_memos()

    def delete_memo(self, mid):
        if mid in self.memos:
            del self.memos[mid]
            self.save_memos()

    def save_memos(self, immediate=False):
        """Requests a save. Defaults to debounced saving for better performance."""
        if immediate:
            self._perform_save()
        else:
            self.save_timer.start(1500)

    def _get_app_state_data(self):
        """Builds the comprehensive state dictionary for saving/backup."""
        return {
            "global": {
                "theme": self.current_theme, 
                "font_family": self.current_font, 
                "font_size": self.current_font_size,
                "title_font_size": self.title_font_size,
                "title_bold": self.title_bold
            },
            "memos": {mid: m.get_current_settings() for mid, m in self.memos.items()}
        }

    def _perform_save(self, path=None):
        """Actual disk write operation."""
        self.save_timer.stop()
        target_path = path or self.save_file
        data = self._get_app_state_data()
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            if not path:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Disk Write: State saved.")
        except Exception as e: print(e)

    def quit_app(self):
        """Ensures state is saved before quitting."""
        self._perform_save()
        QApplication.quit()

    def load_memos(self):
        if not os.path.exists(self.save_file): return
        try:
            with open(self.save_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "global" in data:
                    self.current_theme = data["global"].get("theme", self.current_theme)
                    self.current_font = data["global"].get("font_family", self.current_font)
                    raw_fs = data["global"].get("font_size", 14)
                    try:
                        self.current_font_size = max(6, int(raw_fs))
                    except:
                        self.current_font_size = 14
                    
                    self.title_font_size = data["global"].get("title_font_size", 13)
                    self.title_bold = data["global"].get("title_bold", True)
                    for mid, s in data.get("memos", {}).items():
                        self.create_new_memo(settings=s, memo_id=mid)
                else:
                    for mid, s in data.items(): self.create_new_memo(settings=s, memo_id=mid)
            
            self.refresh_all_memos_style()
        except Exception:
            import traceback
            traceback.print_exc()

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon()
        
        icon_path = os.path.join(self.assets_dir, "icon.png")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
            
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("CMEMO")
        
        menu = QMenu()
        menu.addAction("📂 모든 메모 보기").triggered.connect(self.bring_to_front)
        menu.addSeparator()
        menu.addAction("📖 사용법 가이드").triggered.connect(self.show_guide)
        menu.addAction("➕ 새 메모").triggered.connect(lambda: self.create_new_memo())
        menu.addSeparator()
        storage_menu = menu.addMenu("📁 저장 및 백업 관리")
        
        current_dir = os.path.dirname(self.save_file)
        current_path_action = QAction(f"📍 폴더: ...{current_dir[-25:] if len(current_dir) > 25 else current_dir}")
        current_path_action.setEnabled(False)
        current_path_action.setToolTip(f"전체 경로: {self.save_file}")
        storage_menu.addAction(current_path_action)
        
        storage_menu.addSeparator()
        
        storage_menu.addAction("💾 저장 위치 변경").triggered.connect(lambda: self.change_storage_path())
        storage_menu.addAction("📁 백업 데이터 불러오기").triggered.connect(lambda: self.load_backup_file())
        storage_menu.addAction("📤 현재 데이터 백업").triggered.connect(lambda: self.backup_current_data())
        storage_menu.addAction("⚙️ 설정 파일 백업").triggered.connect(lambda: self.backup_path_config())
        storage_menu.addAction("📅 정기 백업 설정").triggered.connect(lambda: self.show_auto_backup_settings())
        
        menu.addSeparator()
        menu.addAction("⌨️ 단축키 재등록").triggered.connect(self.setup_hotkeys)
        menu.addSeparator()
        menu.addAction("❌ 종료").triggered.connect(self.quit_app)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        # Use .value property for enum comparison
        if reason.value == QSystemTrayIcon.ActivationReason.DoubleClick.value:
            self.bring_to_front()

    def show_guide(self):
        guide_path = resource_path("GUIDE.md")
        content = "가이드 파일을 찾을 수 없습니다."
        if os.path.exists(guide_path):
            with open(guide_path, "r", encoding="utf-8") as f:
                content = f.read()

        # Modern Frameless Guide Dialog
        self.guide_dialog = QDialog()
        dialog = self.guide_dialog
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        dialog.setMinimumSize(520, 650)
        
        # Main Container
        container = QFrame(dialog)
        container.setObjectName("GuideContainer")
        container.setStyleSheet("""
            QFrame#GuideContainer {
                background-color: white;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 12px;
            }
        """)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Custom Title Bar
        title_bar = QFrame()
        title_bar.setFixedHeight(45)
        title_bar.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.05);
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        
        title_label = QLabel("📖 사용법 가이드")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2d3436; border: none;")
        
        close_icon_btn = QPushButton("×")
        close_icon_btn.setFixedSize(28, 28)
        close_icon_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_icon_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 20px;
                color: #636e72;
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: rgba(0,0,0,0.05);
                color: #2d3436;
            }
        """)
        close_icon_btn.clicked.connect(dialog.accept)
        
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(close_icon_btn)
        
        container_layout.addWidget(title_bar)
        
        # Content Area
        browser = QTextBrowser()
        html_content = self._convert_md_to_html(content)
        browser.setHtml(html_content)
        
        # Match Memo Scrollbar Style
        scrollbar_css = """
            QScrollBar:vertical { 
                border: none; 
                background: transparent; 
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical { 
                background: rgba(0, 0, 0, 0.1); 
                border-radius: 3px; 
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { 
                background: rgba(0, 0, 0, 0.2); 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """
        
        browser.setStyleSheet(f"""
            QTextBrowser {{
                border: none;
                padding: 25px;
                background-color: #ffffff;
            }}
            {scrollbar_css}
        """)
        
        container_layout.addWidget(browser)
        
        # Bottom Button for confirmation
        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(60)
        bottom_layout = QHBoxLayout(bottom_bar)
        
        confirm_btn = QPushButton("확인")
        confirm_btn.setFixedSize(100, 36)
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d3436;
                color: white;
                border: none;
                border-radius: 18px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #000000;
            }
        """)
        confirm_btn.clicked.connect(dialog.accept)
        
        bottom_layout.addStretch()
        bottom_layout.addWidget(confirm_btn)
        bottom_layout.addStretch()
        
        container_layout.addWidget(bottom_bar)
        
        # Make it draggable
        def move_window(event):
            if event.buttons() == Qt.MouseButton.LeftButton:
                dialog.move(dialog.pos() + event.globalPosition().toPoint() - dialog._drag_pos)
                dialog._drag_pos = event.globalPosition().toPoint()
                event.accept()

        def press_window(event):
            if event.button() == Qt.MouseButton.LeftButton:
                dialog._drag_pos = event.globalPosition().toPoint()
                event.accept()

        title_bar.mousePressEvent = press_window
        title_bar.mouseMoveEvent = move_window
        
        dialog.exec()

    def _convert_md_to_html(self, md_text):
        # Simple internal converter for rich Guide view
        import re
        html = md_text
        
        # Headers
        html = re.sub(r'^### (.*)$', r'<h3 style="color: #2c3e50; margin-top: 20px; border-bottom: 2px solid #ecf0f1; padding-bottom: 5px;">\1</h3>', html, flags=re.M)
        html = re.sub(r'^# (.*)$', r'<h1 style="color: #2c3e50; text-align: center; border-bottom: 3px solid #34495e; padding-bottom: 10px;">\1</h1>', html, flags=re.M)
        
        # Bold
        html = re.sub(r'\*\*(.*?)\*\*', r'<b style="color: #e67e22;">\1</b>', html)
        
        # Lists
        html = re.sub(r'^\* (.*)$', r'<li style="margin-bottom: 5px;">\1</li>', html, flags=re.M)
        html = re.sub(r'^\d\. (.*)$', r'<li style="margin-bottom: 5px;">\1</li>', html, flags=re.M)
        
        # Inline code
        html = re.sub(r'`(.*?)`', r'<code style="background-color: #f8f9fa; padding: 2px 4px; border-radius: 3px; color: #e83e8c; font-family: monospace;">\1</code>', html)
        
        # Line breaks
        html = html.replace('\n', '<br>')
        
        # Wrap in body font
        font_family = "Pretendard, 'Malgun Gothic', sans-serif"
        return f"""
        <div style="font-family: {font_family}; line-height: 1.6; color: #333; font-size: 14px;">
            {html}
        </div>
        """

    def setup_hotkeys(self):
        try:
            # Clear existing hooks to prevent duplicate registrations
            keyboard.unhook_all()
            
            keyboard.add_hotkey('ctrl+alt+page up', self.bring_to_front)
            keyboard.add_hotkey('ctrl+alt+page down', self.hide_all)
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Hotkeys registered successfully.")
        except Exception as e:
            print(f"Hotkey Error: {e}")

    def bring_to_front(self):
        for m in self.memos.values():
            QTimer.singleShot(0, m.show_and_raise)

    def hide_all(self):
        for m in self.memos.values():
            QTimer.singleShot(0, m.hide)

    def change_storage_path(self, parent=None):
        if not isinstance(parent, QWidget): parent = None
        path, _ = QFileDialog.getSaveFileName(parent, "새 저장 위치 선택", self.save_file, "JSON (*.json)")
        if path:
            self.save_file = path
            new_backup_folder = os.path.join(os.path.dirname(path), "backups")
            
            cfg = {}
            if os.path.exists(self.path_config_file):
                try:
                    with open(self.path_config_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                except: pass
            
            cfg["last_storage_path"] = path
            if "auto_backup" not in cfg:
                cfg["auto_backup"] = self.auto_backup_config.copy()
            
            cfg["auto_backup"]["folder"] = new_backup_folder
            self.auto_backup_config["folder"] = new_backup_folder
            
            if not os.path.exists(new_backup_folder):
                try: os.makedirs(new_backup_folder)
                except: pass

            try:
                with open(self.path_config_file, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=4)
            except: pass
            
            self._perform_save() # Save current memos to new location
            QMessageBox.information(parent, "이동 완료", f"데이터와 백업 위치가 다음으로 이동되었습니다:\n{os.path.dirname(path)}")

    def load_backup_file(self, parent=None):
        """Import content from a backup JSON file into the current storage."""
        if not isinstance(parent, QWidget): parent = None
        path, _ = QFileDialog.getOpenFileName(parent, "백업 파일 선택", "", "JSON (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
                
                for m in list(self.memos.values()): m.close()
                self.memos.clear()
                
                with open(self.save_file, "w", encoding="utf-8") as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=4)
                
                self.load_memos()
                if not self.memos: self.create_new_memo()
            except Exception as e:
                QMessageBox.critical(parent, "오류", f"백업 파일을 불러오는 중 오류가 발생했습니다:\n{str(e)}")

    def backup_path_config(self, parent=None):
        """Back up the path_config.json file."""
        if not isinstance(parent, QWidget): parent = None
        if not os.path.exists(self.path_config_file):
            QMessageBox.warning(parent, "알림", "설정 파일이 존재하지 않습니다.")
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        default_name = f"path_config_backup_{timestamp}.json"
        
        path, _ = QFileDialog.getSaveFileName(parent, "설정 파일 백업 저장", default_name, "JSON (*.json)")
        if path:
            try:
                import shutil
                shutil.copy2(self.path_config_file, path)
                QMessageBox.information(parent, "백업 완료", f"설정 파일이 성공적으로 백업되었습니다:\n{path}")
            except Exception as e:
                QMessageBox.critical(parent, "백업 실패", f"설정 백업 중 오류가 발생했습니다:\n{str(e)}")

    def backup_current_data(self, parent=None):
        """Save a timestamped copy of the current storage to a user-chosen location."""
        if not isinstance(parent, QWidget): parent = None
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        default_path = os.path.join(os.path.dirname(self.save_file), f"memo_backup_{timestamp}.json")
        
        path, _ = QFileDialog.getSaveFileName(parent, "데이터 백업 저장", default_path, "JSON (*.json)")
        if path:
            self._perform_save(path=path)
            QMessageBox.information(parent, "백업 완료", f"데이터가 성공적으로 백업되었습니다:\n{path}")

    # --- Auto Backup & Scheduling Logic ---

    def load_auto_backup_config(self):
        try:
            if os.path.exists(self.path_config_file):
                with open(self.path_config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if "auto_backup" in cfg:
                        self.auto_backup_config.update(cfg["auto_backup"])
        except: pass

    def save_auto_backup_config(self):
        try:
            cfg = {}
            if os.path.exists(self.path_config_file):
                with open(self.path_config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["auto_backup"] = self.auto_backup_config
            with open(self.path_config_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=4)
        except: pass

    def show_auto_backup_settings(self):
        dialog = AutoBackupDialog(self.auto_backup_config, self.ui_icons, None)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.auto_backup_config = dialog.get_settings()
            self.save_auto_backup_config()
            QMessageBox.information(None, "설정 저장", "정기 백업 설정이 저장되었습니다.")

    def check_scheduled_backup(self):
        if not self.auto_backup_config.get("enabled", False):
            return
            
        cron_expr = self.auto_backup_config.get("cron", "0 * * * *")
        now = datetime.datetime.now().replace(second=0, microsecond=0)
        
        # Avoid double execution in the same minute
        if self._last_backup_time == now:
            return

        try:
            # Check if now matches the cron schedule
            if croniter.match(cron_expr, now):
                self.perform_auto_backup()
                self._last_backup_time = now
        except Exception as e:
            print(f"Schedule Check Error: {e}")

    def perform_auto_backup(self):
        config = self.auto_backup_config
        folder = config.get("folder")
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
            except: return

        # 1. Create timestamped backup
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        filename = f"memo_storage_{timestamp}.json"
        save_path = os.path.join(folder, filename)
        
        try:
            data = self._get_app_state_data()
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            print(f"Auto Backup Success: {save_path}")
            
            # 2. Rotation - Delete old files
            self.rotate_backups(folder, config.get("retention", 5))
            
        except Exception as e:
            print(f"Auto Backup Failed: {e}")

    def rotate_backups(self, folder, max_count):
        try:
            files = [os.path.join(folder, f) for f in os.listdir(folder) if f.startswith("memo_storage_") and f.endswith(".json")]
            # Sort by modification time (oldest first)
            files.sort(key=os.path.getmtime)
            
            while len(files) > max_count:
                old_file = files.pop(0)
                os.remove(old_file)
                print(f"Rotation: Deleted old backup {old_file}")
        except Exception as e:
            print(f"Rotation Error: {e}")

class AutoBackupDialog(QDialog):
    def __init__(self, config, ui_icons, parent=None):
        super().__init__(parent)
        self.config = config.copy()
        self.ui_icons = ui_icons
        self.drag_pos = None
        self.initUI()
        
    def initUI(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(480, 640)
        
        # Main Container with shadow/border effect
        container = QFrame(self)
        container.setObjectName("MainContainer")
        container.setStyleSheet("""
            QFrame#MainContainer {
                background-color: #ffffff;
                border: 1px solid #dadce0;
                border-radius: 12px;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
        
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Custom Title Bar
        title_bar = QFrame()
        title_bar.setFixedHeight(50)
        title_bar.setStyleSheet("background-color: transparent; border-bottom: 1px solid #f1f3f4;")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(20, 0, 15, 0)
        
        title_label = QLabel("📅 정기 백업 설정")
        title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #3c4043;")
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 15px;
                font-size: 20px;
                color: #70757a;
            }
            QPushButton:hover { background-color: #f1f3f4; color: #202124; }
        """)
        close_btn.clicked.connect(self.reject)
        
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(close_btn)
        
        # Enable dragging from title bar
        title_bar.mousePressEvent = self.on_title_press
        title_bar.mouseMoveEvent = self.on_title_move
        
        content_layout.addWidget(title_bar)
        
        # Form Body
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(25, 20, 25, 20)
        body_layout.setSpacing(15)
        
        # Use pre-generated icons
        arrow_down = self.ui_icons["arrow_down"]
        arrow_up = self.ui_icons["arrow_up"]
        check_icon = self.ui_icons["check"]
        
        # Section Label Style
        sec_style = "font-size: 13px; font-weight: 600; color: #3c4043; margin-top: 5px;"
        input_style = f"""
            QLineEdit, QSpinBox, QComboBox {{
                border: 1px solid #dadce0;
                border-radius: 6px;
                padding: 10px 12px;
                background-color: #ffffff;
                font-size: 13px;
                color: #3c4043;
                height: 40px;
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border: 2px solid #1a73e8;
            }}
            
            /* ComboBox Arrow */
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 32px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url({arrow_down});
                width: 12px; height: 12px;
            }}
            
            /* SpinBox Arrows */
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 24px;
                border: none;
                background-color: transparent;
            }}
            QSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; margin-top: 5px; margin-right: 2px; }}
            QSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; margin-bottom: 5px; margin-right: 2px; }}
            
            QSpinBox::up-arrow {{
                image: url({arrow_up});
                width: 10px; height: 10px;
            }}
            QSpinBox::down-arrow {{
                image: url({arrow_down});
                width: 10px; height: 10px;
            }}
        """
        
        # Enabled State
        self.enabled_cb = QCheckBox("자동 백업 기능 활성화")
        self.enabled_cb.setChecked(self.config.get("enabled", False))
        self.enabled_cb.setStyleSheet(f"""
            QCheckBox {{ font-size: 14px; font-weight: 500; color: #202124; spacing: 12px; }}
            QCheckBox::indicator {{ 
                width: 20px; height: 20px; 
                border: 2px solid #dadce0; 
                border-radius: 4px; 
                background-color: #ffffff;
            }}
            QCheckBox::indicator:checked {{
                background-color: #ffffff;
                border: 2px solid #1a73e8;
                image: url({check_icon});
            }}
            QCheckBox::indicator:unchecked:hover {{
                border-color: #1a73e8;
            }}
        """)
        body_layout.addWidget(self.enabled_cb)
        
        # Folder
        folder_sec = QLabel("백업 폴더 위치")
        folder_sec.setStyleSheet(sec_style)
        body_layout.addWidget(folder_sec)
        
        folder_inner = QHBoxLayout()
        folder_inner.setSpacing(10)
        initial_folder = os.path.normpath(self.config.get("folder", ""))
        self.folder_edit = QLineEdit(initial_folder)
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setStyleSheet(input_style)
        folder_btn = QPushButton("변경")
        folder_btn.setFixedSize(60, 42)
        folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f4;
                color: #1a73e8;
                border: 1px solid #dadce0;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #e8f0fe; }
        """)
        folder_btn.clicked.connect(self.select_folder)
        folder_inner.addWidget(self.folder_edit)
        folder_inner.addWidget(folder_btn)
        body_layout.addLayout(folder_inner)
        
        # Schedule / Cron
        cron_sec = QLabel("백업 주기 설정 (Cron 식)")
        cron_sec.setStyleSheet(sec_style)
        body_layout.addWidget(cron_sec)
        
        self.cron_preset = QComboBox()
        self.cron_preset.setFixedHeight(42)
        self.cron_preset.setStyleSheet(input_style)
        self.cron_preset.addItems([
            "사용자 직접 입력",
            "30분에 한번 (*/30 * * * *)",
            "2시간에 한번 (0 */2 * * *)",
            "매일 자정 (0 0 * * *)",
            "매주 금요일 자정 (0 0 * * 5)",
            "매달 1일 자정 (0 0 1 * *)"
        ])
        self.cron_preset.currentIndexChanged.connect(self.on_preset_changed)
        body_layout.addWidget(self.cron_preset)
        
        self.cron_edit = QLineEdit(self.config.get("cron", "0 * * * *"))
        self.cron_edit.setStyleSheet(input_style)
        self.cron_edit.setPlaceholderText("* * * * *")
        self.cron_edit.textChanged.connect(self.validate_cron)
        body_layout.addWidget(self.cron_edit)
        
        self.next_run_label = QLabel("다음 실행 예정 (최대 5개):")
        self.next_run_label.setStyleSheet("color: #70757a; font-size: 11px; margin-left: 2px;")
        body_layout.addWidget(self.next_run_label)
        
        self.next_times_text = QLabel("-")
        self.next_times_text.setStyleSheet("color: #1a73e8; font-size: 12px; margin-left: 10px; line-height: 1.4;")
        body_layout.addWidget(self.next_times_text)
        
        # Retention
        ret_sec = QLabel("보관할 백업 파일 개수")
        ret_sec.setStyleSheet(sec_style)
        body_layout.addWidget(ret_sec)
        self.retention_spin = QSpinBox()
        self.retention_spin.setFixedHeight(42)
        self.retention_spin.setStyleSheet(input_style)
        self.retention_spin.setRange(1, 100)
        self.retention_spin.setSuffix(" 개")
        self.retention_spin.setValue(self.config.get("retention", 5))
        body_layout.addWidget(self.retention_spin)
        
        body_layout.addStretch()
        content_layout.addWidget(body)
        
        # Bottom Buttons
        footer = QFrame()
        footer.setFixedHeight(70)
        footer.setStyleSheet("background-color: transparent; border-top: 1px solid #f1f3f4;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(25, 0, 25, 0)
        footer_layout.setSpacing(12)
        
        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedSize(90, 36)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #5f6368;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #f8f9fa; color: #3c4043; }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("설정 저장")
        save_btn.setFixedSize(110, 36)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #1765cc; }
        """)
        save_btn.clicked.connect(self.accept)
        
        footer_layout.addStretch()
        footer_layout.addWidget(cancel_btn)
        footer_layout.addWidget(save_btn)
        
        content_layout.addWidget(footer)
        self.validate_cron()

    def on_title_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def on_title_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "백업 폴더 선택", self.folder_edit.text())
        if folder:
            self.folder_edit.setText(os.path.normpath(folder))

    def on_preset_changed(self, index):
        if index == 1: self.cron_edit.setText("*/30 * * * *")
        elif index == 2: self.cron_edit.setText("0 */2 * * *")
        elif index == 3: self.cron_edit.setText("0 0 * * *")
        elif index == 4: self.cron_edit.setText("0 0 * * 5")
        elif index == 5: self.cron_edit.setText("0 0 1 * *")

    def validate_cron(self):
        expr = self.cron_edit.text()
        try:
            if croniter.is_valid(expr):
                now = datetime.datetime.now()
                it = croniter(expr, now)
                next_times = []
                for _ in range(5):
                    next_times.append(it.get_next(datetime.datetime).strftime('%Y-%m-%d %H:%M'))
                
                self.next_times_text.setText("\n".join(next_times))
                self.next_times_text.setStyleSheet("color: #1a73e8; font-size: 12px; margin-left: 10px;")
            else:
                self.next_times_text.setText("잘못된 크론 식입니다.")
                self.next_times_text.setStyleSheet("color: #d93025; font-size: 12px; margin-left: 10px;")
        except:
            self.next_times_text.setText("잘못된 크론 식입니다.")
            self.next_times_text.setStyleSheet("color: #d93025; font-size: 12px; margin-left: 10px;")

    def get_settings(self):
        return {
            "enabled": self.enabled_cb.isChecked(),
            "cron": self.cron_edit.text(),
            "folder": self.folder_edit.text(),
            "retention": self.retention_spin.value()
        }

