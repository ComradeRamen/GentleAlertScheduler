# -*- coding: utf-8 -*-
import sys
import os
import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QLabel,
    QLineEdit, QComboBox, QTimeEdit, QDateEdit, QCheckBox, QHBoxLayout, QMessageBox,
    QColorDialog, QSpinBox, QFormLayout, QDoubleSpinBox, QSystemTrayIcon,
    QMenu, QAction, QStyle, QGridLayout
)
from PyQt5.QtCore import Qt, QTime, QDate, QDateTime, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QIcon
import ctypes
from ctypes import wintypes

# Conditional import for Windows features
if sys.platform == "win32":
    try:
        import winreg
    except ImportError:
        winreg = None # Set to None if import fails (e.g., non-Windows)
        print("Warning: 'winreg' module not found. Startup features disabled.")
else:
    winreg = None # Not on Windows

# --- Helper Function for Configuration Path ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        # sys._MEIPASS is a string containing the path to the temporary folder
        base_path = sys._MEIPASS
    except Exception:
        # Not running as PyInstaller bundle, use script's directory
        # os.path.abspath(".") gives the current working directory
        # Alternatively, use Path(__file__).parent for script's directory
        base_path = os.path.abspath(".")

    # Join the base path with the relative path of the resource
    return os.path.join(base_path, relative_path)
    
def get_config_dir():
    """Gets the application's configuration directory path."""
    app_name = "GentleAlertScheduler"
    if sys.platform == "win32":
        app_data_dir = os.getenv('LOCALAPPDATA')
        if not app_data_dir:
             app_data_dir = Path.home()
        config_dir = Path(app_data_dir) / app_name
    else: # Linux/macOS
        config_dir = Path.home() / ".config" / app_name

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating config directory {config_dir}: {e}")
        return Path(".") # Fallback to current directory
    return config_dir

def get_config_path(filename):
    """Gets the full path for a specific config file."""
    return get_config_dir() / filename

def is_foreground_fullscreen():
    """Checks if the foreground window is running in fullscreen mode."""
    if sys.platform != "win32": return False
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd: return False

        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        
        win_width = rect.right - rect.left
        win_height = rect.bottom - rect.top
        
        return (win_width == screen_width) and (win_height == screen_height)
    except Exception:
        return False

def press_windows_key():
    """Simulates a Windows key press to open the Start Menu."""
    if sys.platform != "win32": return
    try:
        # VK_LWIN = 0x5B
        ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0) # Key down
        ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0) # Key up (KEYEVENTF_KEYUP = 2)
        print("Simulated Windows Key press.")
    except Exception as e:
        print(f"Failed to press Windows Key: {e}")

# --- Transparent Overlay Class ---

class TransparentOverlay(QWidget):
    closed = pyqtSignal(QWidget)

    def __init__(self, time_to_full_size, transparency, color, initial_size,
                 max_pixels_per_step, exit_after, text, text_transparency, text_color, alert, start_corner, screen=None):
        super().__init__()
        self.alert = alert # Store the alert data associated with this overlay
        self.start_corner = start_corner # Store the starting corner
        self.current_width = initial_size
        self.current_height = initial_size
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)

        if screen is None: screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        self.screen_width = screen_geometry.width()
        self.screen_height = screen_geometry.height()
        self.screen_x = screen_geometry.x()
        self.screen_y = screen_geometry.y()

        # Calculate initial position based on the start corner
        if self.start_corner == "Top-Left":
            initial_x = self.screen_x
            initial_y = self.screen_y
        elif self.start_corner == "Bottom-Left":
            initial_x = self.screen_x
            initial_y = self.screen_y + self.screen_height - self.current_height
        elif self.start_corner == "Bottom-Right":
            initial_x = self.screen_x + self.screen_width - self.current_width
            initial_y = self.screen_y + self.screen_height - self.current_height
        else: # Default to "Top-Right"
            initial_x = self.screen_x + self.screen_width - self.current_width
            initial_y = self.screen_y
        
        self.setGeometry(int(initial_x), int(initial_y), int(self.current_width), int(self.current_height))

        self.overlay_color = tuple(color) if isinstance(color, list) else color
        self.transparency = int(transparency * 255 / 100)
        self.text_transparency = int(text_transparency * 255 / 100)
        self.text = text
        self.text_color = tuple(text_color) if isinstance(text_color, list) else text_color

        self.target_width = self.screen_width
        self.target_height = self.screen_height
        total_pixels_to_expand = max(self.target_width - self.current_width, self.target_height - self.current_height)
        total_steps = max(1, total_pixels_to_expand / max_pixels_per_step if max_pixels_per_step > 0 else 1)
        update_interval = (time_to_full_size * 60 * 1000) / total_steps if total_steps > 0 else 0

        self.width_increment = (self.target_width - self.current_width) / total_steps if total_steps > 0 else 0
        self.height_increment = (self.target_height - self.current_height) / total_steps if total_steps > 0 else 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.expand_window)
        if update_interval > 0 and (self.width_increment != 0 or self.height_increment != 0):
            self.timer.start(int(update_interval))
        else:
            self.expand_window(force_full=True)

        self.exit_timer = QTimer(self)
        self.exit_timer.timeout.connect(self.close_application)
        self.exit_timer.setSingleShot(True)
        self.exit_timer.start(int(exit_after * 60 * 1000))

    def expand_window(self, force_full=False):
        if force_full:
            self.current_width = self.target_width
            self.current_height = self.target_height
        else:
            self.current_width += self.width_increment
            self.current_height += self.height_increment
            self.current_width = min(self.current_width, self.target_width) if self.width_increment >= 0 else max(self.current_width, self.target_width)
            self.current_height = min(self.current_height, self.target_height) if self.height_increment >= 0 else max(self.current_height, self.target_height)

        # Calculate new position based on the start corner and current size
        if self.start_corner == "Top-Left":
            new_x = self.screen_x
            new_y = self.screen_y
        elif self.start_corner == "Bottom-Left":
            new_x = self.screen_x
            new_y = self.screen_y + self.screen_height - self.current_height
        elif self.start_corner == "Bottom-Right":
            new_x = self.screen_x + self.screen_width - self.current_width
            new_y = self.screen_y + self.screen_height - self.current_height
        else: # Default to "Top-Right"
            new_x = self.screen_x + self.screen_width - self.current_width
            new_y = self.screen_y

        self.setGeometry(int(new_x), int(new_y), int(self.current_width), int(self.current_height))
        self.update()

        if self.current_width == self.target_width and self.current_height == self.target_height:
            self.timer.stop()

    def close_application(self):
        self.timer.stop()
        self.exit_timer.stop()
        self.closed.emit(self)
        self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        overlay_rgb = self.overlay_color if isinstance(self.overlay_color, tuple) else (0, 0, 0)
        painter.setBrush(QColor(*overlay_rgb, self.transparency))
        painter.drawRect(self.rect())

        if self.text:
            text_rgb = self.text_color if isinstance(self.text_color, tuple) else (255, 255, 255)
            painter.setPen(QColor(*text_rgb, self.text_transparency))
            font = QFont("Arial", 24)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, self.text)

# --- Add/Edit Alert Dialog ---

class AddAlertDialog(QDialog):
    def __init__(self, parent=None, default_settings=None, alert_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add Alert" if alert_data is None else "Edit Alert")
        self.alert_data = alert_data
        self.default_settings = default_settings if default_settings else {}

        # Store the form layout for later access
        self.form_layout = QFormLayout()
        self.layout = QVBoxLayout(self)
        self.layout.addLayout(self.form_layout) # Add form layout to main layout

        edit_data = alert_data if alert_data else self.default_settings

        # Date / Time / Repeat
        self.date_edit = QDateEdit(QDate.fromString(edit_data.get('date', QDate.currentDate().toString("yyyy-MM-dd")), "yyyy-MM-dd"))
        self.date_edit.setCalendarPopup(True)
        self.form_layout.addRow("Start Date:", self.date_edit)
        self.time_edit = QTimeEdit(QTime.fromString(edit_data.get('time', QTime.currentTime().toString("HH:mm:ss")), "HH:mm:ss"))
        self.form_layout.addRow("Alert Time:", self.time_edit)
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItems(["No Repeat", "Daily", "Weekly", "Monthly", "Every X Minutes", "Every X Hours"])
        self.repeat_combo.setCurrentText(edit_data.get('repeat', 'No Repeat'))
        self.repeat_combo.currentIndexChanged.connect(self.update_repeat_options)
        self.form_layout.addRow("Repeat:", self.repeat_combo)

        # Weekdays
        self.weekday_checkboxes = []
        weekdays_layout = QHBoxLayout()
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        selected_weekdays = edit_data.get('weekdays', [])
        for day in weekdays:
            checkbox = QCheckBox(day); checkbox.setChecked(day in selected_weekdays)
            self.weekday_checkboxes.append(checkbox); weekdays_layout.addWidget(checkbox)
        self.weekdays_widget = QWidget(); self.weekdays_widget.setLayout(weekdays_layout)
        self.form_layout.addRow("Days of Week:", self.weekdays_widget)

        # Day of Month
        self.day_of_month_spinbox = QSpinBox(); self.day_of_month_spinbox.setRange(1, 31)
        self.day_of_month_spinbox.setValue(edit_data.get('day_of_month', 1))
        self.form_layout.addRow("Day of Month:", self.day_of_month_spinbox)

        # Interval
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 10000)  # A large range, will be adjusted dynamically
        self.interval_spinbox.setValue(edit_data.get('interval_value', 60))
        # The label text will be set dynamically in update_repeat_options
        self.form_layout.addRow("Interval:", self.interval_spinbox)

        # Text
        self.text_edit = QLineEdit(edit_data.get('text', ''))
        self.form_layout.addRow("Alert Text (optional):", self.text_edit)

        # Numeric Settings
        self.expansion_time_edit = QDoubleSpinBox(); self.expansion_time_edit.setRange(0.1, 1440); self.expansion_time_edit.setDecimals(1); self.expansion_time_edit.setSingleStep(1)
        self.expansion_time_edit.setValue(edit_data.get('expansion_time', self.default_settings.get('default_expansion_time', 60)))
        self.form_layout.addRow("Expansion Time (minutes):", self.expansion_time_edit)
        self.duration_multiplier_edit = QDoubleSpinBox(); self.duration_multiplier_edit.setRange(0.1, 10.0); self.duration_multiplier_edit.setSingleStep(0.1)
        self.duration_multiplier_edit.setValue(edit_data.get('duration_multiplier', self.default_settings.get('default_duration_multiplier', 2.0)))
        self.form_layout.addRow("Alert Duration Multiplier:", self.duration_multiplier_edit)
        self.start_size_edit = QSpinBox(); self.start_size_edit.setRange(1, 10000)
        self.start_size_edit.setValue(edit_data.get('start_size', self.default_settings.get('default_start_size', 200)))
        self.form_layout.addRow("Start Size:", self.start_size_edit)
        self.transparency_edit = QDoubleSpinBox(); self.transparency_edit.setRange(0, 100); self.transparency_edit.setSingleStep(1)
        self.transparency_edit.setValue(edit_data.get('transparency', self.default_settings.get('default_transparency', 39)))
        self.form_layout.addRow("Overlay Transparency (%):", self.transparency_edit)
        self.text_transparency_edit = QDoubleSpinBox(); self.text_transparency_edit.setRange(0, 100); self.text_transparency_edit.setSingleStep(1)
        self.text_transparency_edit.setValue(edit_data.get('text_transparency', self.default_settings.get('default_text_transparency', 39)))
        self.form_layout.addRow("Text Transparency (%):", self.text_transparency_edit)

        # Colors
        self.overlay_color_button = QPushButton("Select Overlay Color"); self.overlay_color_button.clicked.connect(self.select_overlay_color)
        self.overlay_color = tuple(edit_data.get('overlay_color', self.default_settings.get('default_overlay_color', (0, 0, 0))))
        self.update_color_button_style(self.overlay_color_button, self.overlay_color)
        self.form_layout.addRow("Overlay Color:", self.overlay_color_button)
        self.text_color_button = QPushButton("Select Text Color"); self.text_color_button.clicked.connect(self.select_text_color)
        self.text_color = tuple(edit_data.get('text_color', self.default_settings.get('default_text_color', (255, 255, 255))))
        self.update_color_button_style(self.text_color_button, self.text_color)
        self.form_layout.addRow("Text Color:", self.text_color_button)

        # Display
        self.display_combo = QComboBox(); self.display_combo.addItems(["Main", "All"])
        self.display_combo.setCurrentText(edit_data.get('display', self.default_settings.get('default_display', 'Main')))
        self.form_layout.addRow("Display On:", self.display_combo)

        # Start Corner
        self.start_corner_combo = QComboBox()
        self.start_corner_combo.addItems(["Top-Right", "Top-Left", "Bottom-Left", "Bottom-Right"])
        self.start_corner_combo.setCurrentText(edit_data.get('start_corner', self.default_settings.get('default_start_corner', 'Top-Right')))
        self.form_layout.addRow("Start Corner:", self.start_corner_combo)

        # Fullscreen Fallback
        self.fullscreen_fallback_cb = QCheckBox("Press Windows Key if Fullscreen Detected")
        self.fullscreen_fallback_cb.setChecked(edit_data.get('fullscreen_fallback', self.default_settings.get('default_fullscreen_fallback', True)))
        self.form_layout.addRow("Fullscreen Behavior:", self.fullscreen_fallback_cb)

        # OK/Cancel Buttons
        self.button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK"); self.cancel_button = QPushButton("Cancel")
        self.button_layout.addWidget(self.ok_button); self.button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_layout) # Add buttons below form
        self.ok_button.clicked.connect(self.accept); self.cancel_button.clicked.connect(self.reject)

        self.update_repeat_options() # Set initial visibility correctly

    def update_color_button_style(self, button, color_tuple):
        if color_tuple and len(color_tuple) == 3:
            button.setStyleSheet(f"background-color: rgb({color_tuple[0]}, {color_tuple[1]}, {color_tuple[2]}); color: {'black' if sum(color_tuple) > 382 else 'white'};") # Basic contrast
        else: button.setStyleSheet("")

    def update_repeat_options(self):
        repeat_mode = self.repeat_combo.currentText()
        is_weekly = (repeat_mode == "Weekly")
        is_monthly = (repeat_mode == "Monthly")
        is_minutes = (repeat_mode == "Every X Minutes")
        is_hours = (repeat_mode == "Every X Hours")
        is_interval = is_minutes or is_hours

        # Hide/show field widgets
        self.weekdays_widget.setVisible(is_weekly)
        self.day_of_month_spinbox.setVisible(is_monthly)
        self.interval_spinbox.setVisible(is_interval)

        # Hide/show corresponding labels using labelForField
        weekdays_label = self.form_layout.labelForField(self.weekdays_widget)
        if weekdays_label:
            weekdays_label.setVisible(is_weekly)

        day_of_month_label = self.form_layout.labelForField(self.day_of_month_spinbox)
        if day_of_month_label:
            day_of_month_label.setVisible(is_monthly)

        interval_label = self.form_layout.labelForField(self.interval_spinbox)
        if interval_label:
            interval_label.setVisible(is_interval)
            if is_minutes:
                interval_label.setText("Interval (Minutes):")
                self.interval_spinbox.setRange(1, 1440)  # Max 24 hours in minutes
            elif is_hours:
                interval_label.setText("Interval (Hours):")
                self.interval_spinbox.setRange(1, 168)  # Max 1 week in hours


    def select_overlay_color(self):
        initial_color = QColor(*self.overlay_color)
        color = QColorDialog.getColor(initial_color, self, "Select Overlay Color")
        if color.isValid():
            self.overlay_color = (color.red(), color.green(), color.blue())
            self.update_color_button_style(self.overlay_color_button, self.overlay_color)

    def select_text_color(self):
        initial_color = QColor(*self.text_color)
        color = QColorDialog.getColor(initial_color, self, "Select Text Color")
        if color.isValid():
            self.text_color = (color.red(), color.green(), color.blue())
            self.update_color_button_style(self.text_color_button, self.text_color)

    def get_alert(self):
        repeat_mode = self.repeat_combo.currentText()
        alert = {
            'enabled': self.alert_data.get('enabled', True) if self.alert_data else True,
            'date': self.date_edit.date().toString("yyyy-MM-dd"),
            'time': self.time_edit.time().toString("HH:mm:ss"),
            'repeat': repeat_mode,
            'text': self.text_edit.text(),
            'display': self.display_combo.currentText(),
            'start_corner': self.start_corner_combo.currentText(),
            'expansion_time': self.expansion_time_edit.value(),
            'duration_multiplier': self.duration_multiplier_edit.value(),
            'start_size': self.start_size_edit.value(),
            'transparency': self.transparency_edit.value(),
            'text_transparency': self.text_transparency_edit.value(),
            'overlay_color': self.overlay_color,
            'text_color': self.text_color,
            'fullscreen_fallback': self.fullscreen_fallback_cb.isChecked(),
        }
        if repeat_mode == "Weekly": alert['weekdays'] = [cb.text() for cb in self.weekday_checkboxes if cb.isChecked()]
        elif repeat_mode == "Monthly": alert['day_of_month'] = self.day_of_month_spinbox.value()
        elif repeat_mode in ["Every X Minutes", "Every X Hours"]:
            interval = self.interval_spinbox.value()
            # Store interval consistently in minutes
            alert['interval_value'] = interval if repeat_mode == "Every X Minutes" else interval * 60
        return alert

# --- Settings Dialog ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = settings if settings else {} # Ensure dict

        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Default Expansion Time
        self.default_expansion_time_edit = QDoubleSpinBox()
        self.default_expansion_time_edit.setRange(0.1, 1440); self.default_expansion_time_edit.setDecimals(1); self.default_expansion_time_edit.setSingleStep(1)
        self.default_expansion_time_edit.setValue(self.settings.get('default_expansion_time', 60))
        form_layout.addRow("Default Expansion Time (minutes):", self.default_expansion_time_edit)

        # Default Duration Multiplier
        self.default_duration_multiplier_edit = QDoubleSpinBox()
        self.default_duration_multiplier_edit.setRange(0.1, 10.0); self.default_duration_multiplier_edit.setSingleStep(0.1)
        self.default_duration_multiplier_edit.setValue(self.settings.get('default_duration_multiplier', 2.0))
        form_layout.addRow("Default Duration Multiplier:", self.default_duration_multiplier_edit)

        # Default Start Size
        self.default_start_size_edit = QSpinBox()
        self.default_start_size_edit.setRange(1, 10000)
        self.default_start_size_edit.setValue(self.settings.get('default_start_size', 200))
        form_layout.addRow("Default Start Size:", self.default_start_size_edit)

        # Default Overlay Transparency
        self.default_transparency_edit = QDoubleSpinBox()
        self.default_transparency_edit.setRange(0, 100); self.default_transparency_edit.setSingleStep(1)
        self.default_transparency_edit.setValue(self.settings.get('default_transparency', 39))
        form_layout.addRow("Default Overlay Transparency (%):", self.default_transparency_edit)

        # Default Text Transparency
        self.default_text_transparency_edit = QDoubleSpinBox()
        self.default_text_transparency_edit.setRange(0, 100); self.default_text_transparency_edit.setSingleStep(1)
        self.default_text_transparency_edit.setValue(self.settings.get('default_text_transparency', 39))
        form_layout.addRow("Default Text Transparency (%):", self.default_text_transparency_edit)

        # Default Overlay Color
        self.default_overlay_color_button = QPushButton("Select Default Overlay Color")
        self.default_overlay_color_button.clicked.connect(self.select_default_overlay_color)
        self.default_overlay_color = tuple(self.settings.get('default_overlay_color', (0, 0, 0)))
        self.update_color_button_style(self.default_overlay_color_button, self.default_overlay_color)
        form_layout.addRow("Default Overlay Color:", self.default_overlay_color_button)

        # Default Text Color
        self.default_text_color_button = QPushButton("Select Default Text Color")
        self.default_text_color_button.clicked.connect(self.select_default_text_color)
        self.default_text_color = tuple(self.settings.get('default_text_color', (255, 255, 255)))
        self.update_color_button_style(self.default_text_color_button, self.default_text_color)
        form_layout.addRow("Default Text Color:", self.default_text_color_button)

        # Default Display Option
        self.default_display_combo = QComboBox()
        self.default_display_combo.addItems(["Main", "All"])
        self.default_display_combo.setCurrentText(self.settings.get('default_display', 'Main'))
        form_layout.addRow("Default Display On:", self.default_display_combo)

        # Default Start Corner
        self.default_start_corner_combo = QComboBox()
        self.default_start_corner_combo.addItems(["Top-Right", "Top-Left", "Bottom-Left", "Bottom-Right"])
        self.default_start_corner_combo.setCurrentText(self.settings.get('default_start_corner', 'Top-Right'))
        form_layout.addRow("Default Start Corner:", self.default_start_corner_combo)

        # Max Pixels Per Step
        self.max_pixels_per_step_edit = QSpinBox()
        self.max_pixels_per_step_edit.setRange(1, 1000)
        self.max_pixels_per_step_edit.setValue(self.settings.get('max_pixels_per_step', 50))
        form_layout.addRow("Max Pixels Per Step (Expansion):", self.max_pixels_per_step_edit)

        # Default Fullscreen Fallback
        self.default_fullscreen_fallback_cb = QCheckBox("Press Windows Key if Fullscreen Detected")
        self.default_fullscreen_fallback_cb.setChecked(self.settings.get('default_fullscreen_fallback', True))
        form_layout.addRow("Default Fullscreen Behavior:", self.default_fullscreen_fallback_cb)

        self.layout.addLayout(form_layout)

        # Buttons
        self.button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_layout)

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def update_color_button_style(self, button, color_tuple):
         if color_tuple and len(color_tuple) == 3:
            button.setStyleSheet(f"background-color: rgb({color_tuple[0]}, {color_tuple[1]}, {color_tuple[2]}); color: {'black' if sum(color_tuple) > 382 else 'white'};")
         else: button.setStyleSheet("")

    def select_default_overlay_color(self):
        initial_color = QColor(*self.default_overlay_color)
        color = QColorDialog.getColor(initial_color, self)
        if color.isValid():
            self.default_overlay_color = (color.red(), color.green(), color.blue())
            self.update_color_button_style(self.default_overlay_color_button, self.default_overlay_color)

    def select_default_text_color(self):
        initial_color = QColor(*self.default_text_color)
        color = QColorDialog.getColor(initial_color, self)
        if color.isValid():
            self.default_text_color = (color.red(), color.green(), color.blue())
            self.update_color_button_style(self.default_text_color_button, self.default_text_color)

    def get_settings(self):
        return {
            'default_expansion_time': self.default_expansion_time_edit.value(),
            'default_duration_multiplier': self.default_duration_multiplier_edit.value(),
            'default_start_size': self.default_start_size_edit.value(),
            'default_transparency': self.default_transparency_edit.value(),
            'default_text_transparency': self.default_text_transparency_edit.value(),
            'default_overlay_color': self.default_overlay_color,
            'default_text_color': self.default_text_color,
            'default_display': self.default_display_combo.currentText(),
            'default_start_corner': self.default_start_corner_combo.currentText(),
            'max_pixels_per_step': self.max_pixels_per_step_edit.value(),
            'default_fullscreen_fallback': self.default_fullscreen_fallback_cb.isChecked(),
        }
# --- Main Window Class ---

class MainWindow(QMainWindow):
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "GentleAlertScheduler"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gentle Alert Scheduler")
        self.hide()

        self.central_widget = QWidget(); self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Alert Table
        self.alert_table = QTableWidget()
        self.alert_table.setColumnCount(8); self.alert_table.setHorizontalHeaderLabels(["Date", "Time", "Repeat", "Text", "Display", "Enabled", "Test", "Edit"])
        self.alert_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.alert_table.setSelectionBehavior(QTableWidget.SelectRows); self.alert_table.setSelectionMode(QTableWidget.SingleSelection)
        self.layout.addWidget(self.alert_table)

        # Buttons
        self.button_layout = QHBoxLayout()
        self.add_alert_button = QPushButton("Add Alert", clicked=self.open_add_alert_dialog)
        self.remove_alert_button = QPushButton("Remove Selected Alert", clicked=self.remove_selected_alert)
        self.test_alert_button = QPushButton("Send Test Alert", clicked=self.send_test_alert)
        self.stop_alerts_button = QPushButton("Stop Ongoing Alerts", clicked=self.stop_ongoing_alerts)
        self.settings_button = QPushButton("Settings", clicked=self.open_settings_dialog)
        self.button_layout.addWidget(self.add_alert_button); self.button_layout.addWidget(self.remove_alert_button); self.button_layout.addWidget(self.test_alert_button); self.button_layout.addWidget(self.stop_alerts_button); self.button_layout.addWidget(self.settings_button)
        self.layout.addLayout(self.button_layout)

        # Data storage
        self.alerts = []
        self.overlays = set() # Use set for active overlays
        self.alert_timers = {} # {alert_index: QTimer} for regular scheduled alerts
        self.temporary_timers = set()

        # Load settings and alerts
        self.settings = self.load_settings()
        self.load_alerts() # Loads alerts and sets initial timers

        # System Tray
        self.create_tray_icon()
        self.tray_icon.showMessage("Gentle Alert Scheduler", "Application started.", QSystemTrayIcon.Information, 3000)

        # Startup Check (Windows only)
        if winreg: # Check if winreg was imported successfully
            self.check_startup_status()

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        try:
            # Use helper function to find alert.png whether frozen or not
            icon_path_str = resource_path("alert.png") # Get the potentially adjusted path
            icon_path = Path(icon_path_str)
    
            if icon_path.is_file():
                self.tray_icon.setIcon(QIcon(icon_path_str))
            else:
                print(f"Tray icon file not found at resolved path: {icon_path_str}")
                self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        except Exception as e:
            # Catch potential errors during path resolution or icon loading
            print(f"Error loading tray icon: {e}")
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
    
        # --- Menu setup remains the same ---
        tray_menu = QMenu()
        restore_action = QAction("Open Scheduler", self, triggered=self.show_main_window)
        stop_alerts_action = QAction("Stop Ongoing Alerts", self, triggered=self.stop_ongoing_alerts)
        delay_menu = QMenu("Delay Active Alerts", self)
        delay_10_action = QAction("Delay by 10 minutes", self, triggered=lambda: self.delay_alerts(10))
        delay_20_action = QAction("Delay by 20 minutes", self, triggered=lambda: self.delay_alerts(20))
        delay_30_action = QAction("Delay by 30 minutes", self, triggered=lambda: self.delay_alerts(30))
        delay_menu.addAction(delay_10_action); delay_menu.addAction(delay_20_action); delay_menu.addAction(delay_30_action)
        exit_action = QAction("Exit", self, triggered=self.exit_application)
        tray_menu.addAction(restore_action); tray_menu.addAction(stop_alerts_action); tray_menu.addMenu(delay_menu); tray_menu.addAction(exit_action)
    
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def delay_alerts(self, minutes):
        """Stops currently active overlays and schedules temporary replacements."""
        if not self.overlays:
             self.tray_icon.showMessage("Delay Alerts", "No active alerts to delay.", QSystemTrayIcon.Information, 2000)
             return

        # Get data from active overlays
        active_overlays_list = list(self.overlays)
        active_alerts_data_to_reschedule = [overlay.alert for overlay in active_overlays_list]
        print(f"Delaying {len(active_overlays_list)} active overlay instance(s) by {minutes} minutes.")

        # Calculate unique logical alerts
        unique_alert_ids = set()
        unique_alerts_data_map = {} # Store the actual alert data keyed by ID
        for alert_data in active_alerts_data_to_reschedule:
            try:
                # Use JSON serialization (sorted) as a way to identify unique alert dicts
                alert_id = json.dumps(alert_data, sort_keys=True)
                if alert_id not in unique_alert_ids:
                    unique_alert_ids.add(alert_id)
                    unique_alerts_data_map[alert_id] = alert_data # Store first instance of data
            except TypeError:
                 # Fallback if data isn't serializable (shouldn't happen with current structure)
                 alert_id = id(alert_data) # Less reliable uniqueness check
                 if alert_id not in unique_alert_ids:
                     unique_alert_ids.add(alert_id)
                     unique_alerts_data_map[alert_id] = alert_data
                 print(f"Warning: Could not reliably serialize alert data for uniqueness check: {alert_data}")

        num_unique_alerts = len(unique_alert_ids)

        # Stop the visual overlays silently
        self.stop_ongoing_alerts(silent=True)

        # Schedule temporary alerts based on UNIQUE logical alerts found
        now = QDateTime.currentDateTime(); delay_secs = minutes * 60
        for alert_id in unique_alert_ids:
            alert_data = unique_alerts_data_map[alert_id] # Get the representative data
            temp_alert = alert_data.copy()
            temp_alert['original_alert_index'] = -1 # Mark as temporary/delayed
            trigger_datetime = now.addSecs(delay_secs)
            temp_alert['date'] = trigger_datetime.date().toString("yyyy-MM-dd")
            temp_alert['time'] = trigger_datetime.time().toString("HH:mm:ss")
            temp_alert['repeat'] = 'No Repeat' # Delayed alerts don't repeat
            temp_alert['enabled'] = True
            print(f"  Scheduling temporary alert: {temp_alert.get('text', 'No Text')} at {temp_alert['time']}")
            self._schedule_single_alert_instance(temp_alert, is_temporary=True)

        self.tray_icon.showMessage(
            "Delay Alerts",
            f"Delayed {num_unique_alerts} unique alert(s) by {minutes} minutes.",
            QSystemTrayIcon.Information, 3000
        )

    def show_main_window(self):
        self.show(); self.raise_(); self.activateWindow()

    def exit_application(self):
        print("Exiting application...")
        self.stop_ongoing_alerts(silent=True) # Stop overlays silently on exit
        self.save_alerts(); self.save_settings()
        # Stop all timers
        for timer in self.alert_timers.values(): timer.stop()
        for timer in self.temporary_timers: timer.stop() # Stop temp timers too
        self.alert_timers.clear()
        self.temporary_timers.clear()
        self.tray_icon.hide()
        QApplication.instance().quit()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger: self.show_main_window()

    def closeEvent(self, event):
        event.ignore(); self.hide()
        self.tray_icon.showMessage("Gentle Alert Scheduler", "Still running.", QSystemTrayIcon.Information, 2000)

    # --- Startup Management (Windows) ---
    def get_executable_path(self):
        # Handle PyInstaller executable path
        if getattr(sys, 'frozen', False):
            return sys.executable
        else:
            # For running as script, get absolute path
            return os.path.abspath(sys.argv[0])

    def check_startup_status(self):
        if not winreg: return # Skip if winreg failed to import
        exe_path = self.get_executable_path()
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, self.APP_NAME)
            winreg.CloseKey(key)
            # Compare paths case-insensitively after resolving and removing quotes
            stored_path = Path(value.strip('"')).resolve()
            current_path = Path(exe_path).resolve()
            if stored_path != current_path:
                 print(f"Startup path mismatch detected.\n Stored: {stored_path}\n Current: {current_path}")
                 self.ask_add_to_startup(update=True)
        except FileNotFoundError:
            print("Startup entry not found.")
            self.ask_add_to_startup()
        except Exception as e:
            QMessageBox.warning(None, "Startup Check Error", f"Failed to check startup status:\n{e}")

    def ask_add_to_startup(self, update=False):
        if not winreg: return
        question = ('Path changed. Update startup entry?' if update else 'Run Gentle Alert Scheduler at system startup?')
        title = 'Update Startup' if update else 'Add to Startup'
        reply = QMessageBox.question(None, title, question, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes: self.manage_startup_entry(add=True)

    def manage_startup_entry(self, add=True):
        if not winreg: return False
        exe_path = self.get_executable_path()
        try:
            # Ensure KEY_WRITE access
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_WRITE)
            if add:
                # Add quotes around path in case it contains spaces
                winreg.SetValueEx(key, self.APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
                action_msg = "added/updated in startup"
            else: # Remove
                 try:
                     winreg.DeleteValue(key, self.APP_NAME)
                     action_msg = "removed from startup"
                 except FileNotFoundError:
                     action_msg = "not found in startup (no removal needed)"
            winreg.CloseKey(key)
            QMessageBox.information(None, "Startup Success", f"Application {action_msg}.")
            print(f"Startup entry {action_msg}: {self.APP_NAME} -> \"{exe_path}\"")
            return True
        except PermissionError:
             QMessageBox.warning(None, "Startup Error", "Permission denied. Could not modify startup settings.\nTry running as administrator if needed.")
             return False
        except Exception as e:
            action = "add/update" if add else "remove"
            QMessageBox.warning(None, "Startup Error", f"Failed to {action} startup entry:\n{e}")
            return False

    # --- Alert Management Dialogs ---
    def open_add_alert_dialog(self):
        dialog = AddAlertDialog(self, default_settings=self.settings)
        if dialog.exec_() == QDialog.Accepted:
            new_alert = dialog.get_alert()
            self.alerts.append(new_alert)
            alert_index = len(self.alerts) - 1
            self.schedule_alert_timer(new_alert, alert_index)
            self.update_alert_table(); self.save_alerts()

    def open_edit_alert_dialog(self, index):
        if 0 <= index < len(self.alerts):
            alert_to_edit = self.alerts[index]
            dialog = AddAlertDialog(self, default_settings=self.settings, alert_data=alert_to_edit)
            if dialog.exec_() == QDialog.Accepted:
                updated_alert = dialog.get_alert()
                self.stop_alert_timer(index) # Stop old timer
                self.alerts[index] = updated_alert
                self.schedule_alert_timer(updated_alert, index) # Schedule new
                self.update_alert_table(); self.save_alerts()
        else: QMessageBox.warning(self, "Error", "Invalid alert index for editing.")

    def remove_selected_alert(self):
        selected_rows = self.alert_table.selectionModel().selectedRows()
        if not selected_rows: QMessageBox.warning(self, "No Selection", "Select alert to remove."); return
        selected_row = selected_rows[0].row()

        if 0 <= selected_row < len(self.alerts):
            reply = QMessageBox.question(self, "Confirm Removal", f"Remove alert: '{self.alerts[selected_row].get('text','(No Text)')}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.stop_alert_timer(selected_row) # Stop timer associated with this index
                self.alerts.pop(selected_row)
                print(f"Removed alert index {selected_row}")

                # --- IMPORTANT: Re-index timers ---
                # Create a new dictionary for timers, adjusting keys for removed index
                new_timers = {}
                for old_idx, timer in self.alert_timers.items():
                    if old_idx > selected_row:
                        new_timers[old_idx - 1] = timer # Decrement index for timers after the removed one
                    elif old_idx < selected_row:
                        new_timers[old_idx] = timer # Keep index for timers before the removed one
                    # Timer at selected_row was already stopped and is not copied
                self.alert_timers = new_timers
                # --- End Re-index ---

                self.update_alert_table(); self.save_alerts()
        else: QMessageBox.warning(self, "Error", "Selected row index out of bounds.")

    def update_alert_table(self):
        self.alert_table.setRowCount(0); self.alert_table.setRowCount(len(self.alerts))
        for row, alert in enumerate(self.alerts):
            self.alert_table.setItem(row, 0, QTableWidgetItem(alert.get('date', 'N/A')))
            self.alert_table.setItem(row, 1, QTableWidgetItem(alert.get('time', 'N/A')))
            
            repeat_text = alert.get('repeat', 'N/A')
            if repeat_text == "Every X Minutes":
                repeat_text = f"Every {alert.get('interval_value', '?')} min"
            elif repeat_text == "Every X Hours":
                # Stored as minutes, so convert back for display
                interval_mins = alert.get('interval_value', 0)
                if interval_mins > 0 and interval_mins % 60 == 0:
                    hours = interval_mins // 60
                    repeat_text = f"Every {hours} hr"
                else: # Fallback if data is inconsistent
                    repeat_text = f"Every {interval_mins} min"
            self.alert_table.setItem(row, 2, QTableWidgetItem(repeat_text))

            self.alert_table.setItem(row, 3, QTableWidgetItem(alert.get('text', '')))
            self.alert_table.setItem(row, 4, QTableWidgetItem(alert.get('display', 'Main')))
            # Enabled Checkbox
            enabled_checkbox = QCheckBox(); enabled_checkbox.setChecked(alert.get('enabled', True))
            enabled_checkbox.stateChanged.connect(lambda state, r=row: self.toggle_alert_enabled(r, state))
            enabled_cell_widget = QWidget(); enabled_layout = QHBoxLayout(enabled_cell_widget)
            enabled_layout.addWidget(enabled_checkbox); enabled_layout.setAlignment(Qt.AlignCenter); enabled_layout.setContentsMargins(0,0,0,0)
            self.alert_table.setCellWidget(row, 5, enabled_cell_widget)
            # Buttons
            test_button = QPushButton("Test", clicked=lambda _, r=row: self.test_specific_alert(r))
            edit_button = QPushButton("Edit", clicked=lambda _, r=row: self.open_edit_alert_dialog(r))
            self.alert_table.setCellWidget(row, 6, test_button); self.alert_table.setCellWidget(row, 7, edit_button)
            # Make text items non-editable
            for col in range(5):
                 item = self.alert_table.item(row, col)
                 if item: # Ensure item exists
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)

    def toggle_alert_enabled(self, index, state):
        if 0 <= index < len(self.alerts):
            is_enabled = (state == Qt.Checked)
            print(f"Toggling alert {index} enabled: {is_enabled}")
            self.alerts[index]['enabled'] = is_enabled
            if is_enabled:
                self.schedule_alert_timer(self.alerts[index], index)
            else:
                self.stop_alert_timer(index)
            self.save_alerts()
        else:
            print(f"Warning: toggle_alert_enabled called with invalid index {index}")

    # --- Alert Loading, Saving, Validation ---
    def validate_alert(self, alert_dict):
        # Use current settings as defaults during validation
        defaults = {
            'date': QDate.currentDate().toString("yyyy-MM-dd"),
            'time': QTime.currentTime().toString("HH:mm:ss"),
            'repeat': 'No Repeat',
            'text': '',
            'display': self.settings.get('default_display', 'Main'),
            'start_corner': self.settings.get('default_start_corner', 'Top-Right'),
            'enabled': True,
            'expansion_time': self.settings.get('default_expansion_time', 60),
            'duration_multiplier': self.settings.get('default_duration_multiplier', 2.0),
            'start_size': self.settings.get('default_start_size', 200),
            'transparency': self.settings.get('default_transparency', 39),
            'text_transparency': self.settings.get('default_text_transparency', 39),
            'overlay_color': self.settings.get('default_overlay_color', (0, 0, 0)),
            'text_color': self.settings.get('default_text_color', (255, 255, 255)),
            'weekdays': [],
            'day_of_month': 1,
            'interval_value': 60,
            'fullscreen_fallback': self.settings.get('default_fullscreen_fallback', True),
        }
        validated_alert = {}
        for key, default_value in defaults.items():
            value = alert_dict.get(key, default_value) # Get value or default
            # Type and value validation/correction
            if key in ['overlay_color', 'text_color']:
                 if isinstance(value, list) and len(value) == 3 and all(isinstance(v, int) for v in value):
                     value = tuple(value)
                 elif not (isinstance(value, tuple) and len(value) == 3 and all(isinstance(v, int) for v in value)):
                     value = default_value
            elif key == 'repeat':
                 if value is True: value = 'Daily'
                 elif value is False: value = 'No Repeat'
                 elif value not in ["No Repeat", "Daily", "Weekly", "Monthly", "Every X Minutes", "Every X Hours"]: value = 'No Repeat'
            elif key == 'start_corner':
                if value not in ["Top-Right", "Top-Left", "Bottom-Left", "Bottom-Right"]:
                    value = default_value
            elif key == 'weekdays':
                 if not isinstance(value, list): value = []
            elif key in ['expansion_time', 'duration_multiplier', 'transparency', 'text_transparency']:
                 try: value = float(value)
                 except (ValueError, TypeError): value = default_value
            elif key in ['start_size', 'day_of_month', 'interval_value']:
                 try: value = int(value)
                 except (ValueError, TypeError): value = default_value
            elif key == 'enabled':
                 if not isinstance(value, bool): value = True
            elif key == 'fullscreen_fallback':
                 if not isinstance(value, bool): value = True
            validated_alert[key] = value
        return validated_alert

    def load_alerts(self):
        alerts_path = get_config_path('alerts.json')
        loaded_alerts = []
        if alerts_path.exists():
            try:
                with open(alerts_path, 'r', encoding='utf-8') as f: loaded_data = json.load(f)
                if isinstance(loaded_data, list):
                    loaded_alerts = [self.validate_alert(a) for a in loaded_data]
                else:
                    print("Warning: alerts.json format invalid (expected a list).")
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "Load Error", f"Failed to parse alerts.json:\n{e}\nPlease check the file format.")
            except Exception as e:
                QMessageBox.warning(self, "Load Error", f"Failed to load alerts:\n{e}")

        self.alerts = loaded_alerts
        # Clear existing timers before loading/scheduling new ones
        for timer in self.alert_timers.values(): timer.stop()
        self.alert_timers.clear()
        for timer in self.temporary_timers: timer.stop()
        self.temporary_timers.clear()

        # Schedule timers for loaded alerts that are enabled
        for index, alert in enumerate(self.alerts):
            if alert.get('enabled', True):
                self.schedule_alert_timer(alert, index)

        self.update_alert_table()
        print(f"Loaded {len(self.alerts)} alerts.")

    def save_alerts(self):
        alerts_path = get_config_path('alerts.json')
        alerts_to_save = []
        for alert in self.alerts:
            alert_copy = alert.copy()
            if isinstance(alert_copy.get('overlay_color'), tuple):
                alert_copy['overlay_color'] = list(alert_copy['overlay_color'])
            if isinstance(alert_copy.get('text_color'), tuple):
                alert_copy['text_color'] = list(alert_copy['text_color'])
            alerts_to_save.append(alert_copy)

        try:
            with open(alerts_path, 'w', encoding='utf-8') as f:
                json.dump(alerts_to_save, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save alerts to {alerts_path}:\n{e}")
    # --- Settings Loading/Saving ---
    def load_settings(self):
        settings_path = get_config_path('settings.json')
        defaults = {
            'default_expansion_time': 60.0,
            'default_duration_multiplier': 2.0,
            'default_start_size': 200,
            'default_transparency': 39.0,
            'default_text_transparency': 39.0,
            'default_overlay_color': (0, 0, 0),
            'default_text_color': (255, 255, 255),
            'default_display': 'Main',
            'default_start_corner': 'Top-Right',
            'max_pixels_per_step': 50,
            'default_fullscreen_fallback': True,
        }
        if settings_path.exists():
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings_loaded = json.load(f)

                valid_settings = defaults.copy()
                for key, default_value in defaults.items():
                    loaded_value = settings_loaded.get(key)
                    if loaded_value is not None:
                        if key.endswith('_color'):
                            if isinstance(loaded_value, (list, tuple)) and len(loaded_value) == 3 and all(isinstance(v, int) for v in loaded_value):
                                valid_settings[key] = tuple(loaded_value)
                            else: print(f"Warning: Invalid format for '{key}' in settings.json, using default.")
                        elif isinstance(loaded_value, type(default_value)):
                             valid_settings[key] = loaded_value
                        else: print(f"Warning: Type mismatch for '{key}' in settings.json, using default.")
                print(f"Loaded settings from {settings_path}")
                return valid_settings
            except json.JSONDecodeError as e:
                 QMessageBox.warning(self, "Load Error", f"Failed to parse settings.json:\n{e}\nUsing defaults.")
            except Exception as e:
                 QMessageBox.warning(self, "Load Error", f"Failed to load settings:\n{e}\nUsing defaults.")
        else:
            print(f"Settings file not found at {settings_path}. Using defaults.")
        return defaults

    def save_settings(self):
        settings_path = get_config_path('settings.json')
        settings_to_save = self.settings.copy()
        for key in ['default_overlay_color', 'default_text_color']:
             if isinstance(settings_to_save.get(key), tuple):
                 settings_to_save[key] = list(settings_to_save[key])

        try:
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings_to_save, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save settings to {settings_path}:\n{e}")

    def open_settings_dialog(self):
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec_() == QDialog.Accepted:
            self.settings.update(dialog.get_settings()); self.save_settings()

    # --- Alert Timing and Triggering ---
    def stop_alert_timer(self, alert_index):
        """Stops and removes the timer for a specific alert index."""
        if alert_index in self.alert_timers:
            timer = self.alert_timers.pop(alert_index)
            timer.stop()

    def schedule_alert_timer(self, alert_data, alert_index):
        """Schedules a QTimer for a regular (non-temporary) alert."""
        self.stop_alert_timer(alert_index)
        if not alert_data.get('enabled', True):
            return

        alert_time_str = alert_data.get('time')
        if not alert_time_str:
             print(f"Warning: Alert {alert_index} missing time field.")
             return
        alert_time = QTime.fromString(alert_time_str, "HH:mm:ss")
        if not alert_time.isValid():
             print(f"Warning: Alert {alert_index} has invalid time format '{alert_time_str}'.")
             return

        now = QDateTime.currentDateTime()
        next_trigger_datetime = self.calculate_next_trigger(now, alert_data)

        if not next_trigger_datetime:
            if alert_data.get('repeat') == 'No Repeat':
                 print(f"Non-repeating Alert {alert_index} ('{alert_data.get('text','')}') is in the past. Disabling.")
                 if 0 <= alert_index < len(self.alerts):
                     self.alerts[alert_index]['enabled'] = False
                     self.update_alert_table()
                     self.save_alerts()
                 else: print(f"Error: Invalid index {alert_index} when trying to disable past alert.")
            return

        interval = now.msecsTo(next_trigger_datetime)
        if interval < 0:
            print(f"Warning: Calculated negative interval ({interval}ms) for alert {alert_index}. Skipping.")
            return

        # Cap interval to avoid OverflowError in QTimer (approx 24 days in ms)
        MAX_TIMER_MS = 2147483647 
        if interval > MAX_TIMER_MS:
             # Schedule a timer for the max duration, then reschedule
             print(f"Interval {interval} exceeds QTimer limit. Scheduling intermediate timer.")
             timer = QTimer(); timer.setSingleShot(True)
             timer.timeout.connect(lambda: self.schedule_alert_timer(alert_data, alert_index))
             timer.start(MAX_TIMER_MS)
             self.alert_timers[alert_index] = timer
             return

        timer = QTimer(); timer.setSingleShot(True)
        timer.timeout.connect(lambda a=alert_data.copy(), idx=alert_index: self.trigger_alert(a, idx))
        timer.start(interval);
        self.alert_timers[alert_index] = timer

    def _schedule_single_alert_instance(self, alert_data, is_temporary=False):
         """Schedules a one-off timer, typically for delayed alerts."""
         alert_time_str = alert_data.get('time')
         alert_date_str = alert_data.get('date')
         if not alert_time_str or not alert_date_str:
             print("Error: Temporary alert missing date or time.")
             return

         alert_time = QTime.fromString(alert_time_str, "HH:mm:ss")
         alert_date = QDate.fromString(alert_date_str, "yyyy-MM-dd")

         if not alert_time.isValid() or not alert_date.isValid():
             print(f"Error: Invalid date/time '{alert_date_str} {alert_time_str}' for temporary alert.")
             return

         alert_datetime = QDateTime(alert_date, alert_time)
         interval = max(0, QDateTime.currentDateTime().msecsTo(alert_datetime))

         temp_timer = QTimer(); temp_timer.setSingleShot(True)
         temp_timer.timeout.connect(
             lambda a=alert_data.copy(), timer=temp_timer: self._handle_temporary_alert_trigger(a, timer)
         )

         self.temporary_timers.add(temp_timer)
         temp_timer.start(interval)

    def _handle_temporary_alert_trigger(self, alert_data, timer_instance):
        """Handles the firing of a temporary (delayed) alert timer."""
        try:
            self.trigger_alert(alert_data, -1)
        finally:
            if timer_instance in self.temporary_timers:
                self.temporary_timers.remove(timer_instance)

    def calculate_next_trigger(self, current_datetime, alert_data):
        """Calculates the next QDateTime an alert should trigger based on its repeat settings."""
        alert_time = QTime.fromString(alert_data['time'], "HH:mm:ss")
        if not alert_time.isValid(): return None

        repeat_mode = alert_data.get('repeat', 'No Repeat')
        start_date = QDate.fromString(alert_data.get('date', ''), "yyyy-MM-dd")
        if not start_date.isValid(): start_date = current_datetime.date()

        if repeat_mode == "No Repeat":
            trigger_dt = QDateTime(start_date, alert_time)
            return trigger_dt if trigger_dt >= current_datetime else None

        elif repeat_mode in ["Every X Minutes", "Every X Hours"]:
            interval_minutes = alert_data.get('interval_value', 0)
            if interval_minutes <= 0: return None # Invalid interval

            start_datetime = QDateTime(start_date, alert_time)

            # If the start time is in the future, that's the next trigger
            if start_datetime >= current_datetime:
                return start_datetime

            # If start time is in the past, calculate the next interval tick
            interval_msecs = interval_minutes * 60 * 1000
            msecs_since_start = start_datetime.msecsTo(current_datetime)

            # How many full intervals have passed since the start time
            intervals_passed = msecs_since_start // interval_msecs

            # The next trigger is at the start of the next interval
            next_trigger_msecs_from_start = (intervals_passed + 1) * interval_msecs
            return start_datetime.addMSecs(next_trigger_msecs_from_start)

        elif repeat_mode == "Daily":
            check_date = current_datetime.date()
            if check_date < start_date: check_date = start_date

            trigger_dt_check = QDateTime(check_date, alert_time)
            if trigger_dt_check >= current_datetime:
                return trigger_dt_check

            return QDateTime(check_date.addDays(1), alert_time)

        elif repeat_mode == "Weekly":
            weekdays_map = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6, "Sun": 7}
            target_days = {weekdays_map[day] for day in alert_data.get('weekdays', []) if day in weekdays_map}
            if not target_days: return None

            check_date = current_datetime.date()
            if check_date < start_date: check_date = start_date

            for i in range(8):
                 potential_dt = QDateTime(check_date, alert_time)
                 if check_date.dayOfWeek() in target_days and potential_dt >= current_datetime:
                     if check_date >= start_date:
                         return potential_dt
                 check_date = check_date.addDays(1)
            return None

        elif repeat_mode == "Monthly":
            day_of_month = alert_data.get('day_of_month', 1)
            if not (1 <= day_of_month <= 31): return None

            check_date = current_datetime.date()
            if check_date < start_date: check_date = start_date

            year = check_date.year()
            month = check_date.month()

            while True:
                days_in_month = QDate(year, month, 1).daysInMonth()
                target_day = min(day_of_month, days_in_month)
                potential_date = QDate(year, month, target_day)

                if potential_date >= start_date:
                    potential_dt = QDateTime(potential_date, alert_time)
                    if potential_dt >= current_datetime:
                        return potential_dt

                month += 1
                if month > 12:
                    month = 1
                    year += 1
        return None

    def trigger_alert(self, alert_data, alert_index):
        """Handles the logic when an alert timer (regular or temporary) fires."""
        if alert_index == -1:
            # Temporary/delayed alert
            print(f"Triggering temporary/delayed alert: {alert_data.get('text', 'No Text')}")
            self.show_alert_overlay(alert_data)
        else:
            # Regular alert
             if not (0 <= alert_index < len(self.alerts)):
                 print(f"Skipping trigger for alert index {alert_index} (alert removed).")
                 self.stop_alert_timer(alert_index)
                 return
             current_alert_config = self.alerts[alert_index]
             if not current_alert_config.get('enabled', True):
                 print(f"Skipping trigger for alert {alert_index} (disabled).")
                 self.stop_alert_timer(alert_index)
                 return

             print(f"Triggering alert (Index: {alert_index}): {current_alert_config.get('text', 'No Text')}")
             self.show_alert_overlay(current_alert_config)

             # Reschedule or Disable
             if current_alert_config.get('repeat', 'No Repeat') == 'No Repeat':
                 print(f"Disabling non-repeating alert {alert_index} after triggering.")
                 self.alerts[alert_index]['enabled'] = False
                 self.stop_alert_timer(alert_index)
                 self.update_alert_table()
                 self.save_alerts()
             else:
                 self.schedule_alert_timer(current_alert_config, alert_index)

    # --- Overlay Display and Control ---
    def show_alert_overlay(self, alert_data):
        """Creates and displays the TransparentOverlay window(s)."""
        
        # Check for fullscreen fallback
        if alert_data.get('fullscreen_fallback', True) and is_foreground_fullscreen():
            print("Fullscreen app detected. Triggering Windows Key fallback.")
            press_windows_key()

        max_pix = self.settings.get('max_pixels_per_step', 50)
        display = alert_data.get('display', self.settings.get('default_display', 'Main'))
        start_corner = alert_data.get('start_corner', self.settings.get('default_start_corner', 'Top-Right'))
        exp_time = alert_data.get('expansion_time', self.settings.get('default_expansion_time', 60))
        trans = alert_data.get('transparency', self.settings.get('default_transparency', 39))
        overlay_color_val = alert_data.get('overlay_color', self.settings.get('default_overlay_color', (0,0,0)))
        text_color_val = alert_data.get('text_color', self.settings.get('default_text_color', (255,255,255)))
        color = tuple(overlay_color_val) if isinstance(overlay_color_val, list) else overlay_color_val
        text_color = tuple(text_color_val) if isinstance(text_color_val, list) else text_color_val
        size = alert_data.get('start_size', self.settings.get('default_start_size', 200))
        mult = alert_data.get('duration_multiplier', self.settings.get('default_duration_multiplier', 2.0))
        text = alert_data.get('text', '')
        text_trans = alert_data.get('text_transparency', self.settings.get('default_text_transparency', 39))
        exit_after = exp_time * mult

        screens = QApplication.screens() if display == 'All' else [QApplication.primaryScreen()]
        if not screens:
            print("Warning: No screens detected by QApplication. Cannot display overlay.")
            return

        for screen in screens:
            if screen is None:
                 print("Warning: Skipping a null screen found in QApplication.screens().")
                 continue

            overlay = TransparentOverlay(exp_time, trans, color, size, max_pix, exit_after, text, text_trans, text_color, alert_data, start_corner, screen)
            overlay.closed.connect(self.remove_overlay)
            overlay.show()
            self.overlays.add(overlay)

    def remove_overlay(self, overlay_widget):
        """Callback slot when an overlay closes itself."""
        if overlay_widget in self.overlays:
            self.overlays.remove(overlay_widget)

    def test_specific_alert(self, index):
         """Triggers a one-off test display of a configured alert."""
         if 0 <= index < len(self.alerts):
              alert_config = self.alerts[index]
              print(f"Testing alert {index}: {alert_config.get('text')}")
              self.show_alert_overlay(alert_config.copy())
         else: QMessageBox.warning(self, "Test Error", "Invalid alert index.")

    def send_test_alert(self):
        """Triggers a one-off test display using current default settings."""
        print("Sending test alert using default settings.")
        test_alert = {
            'date': QDate.currentDate().toString("yyyy-MM-dd"),
            'time': QTime.currentTime().toString("HH:mm:ss"),
            'repeat': "No Repeat",
            'text': "Default Settings Test Alert",
            'display': self.settings.get('default_display', 'Main'),
            'start_corner': self.settings.get('default_start_corner', 'Top-Right'),
            'enabled': True,
            'expansion_time': self.settings.get('default_expansion_time', 60),
            'duration_multiplier': self.settings.get('default_duration_multiplier', 2.0),
            'start_size': self.settings.get('default_start_size', 200),
            'transparency': self.settings.get('default_transparency', 39),
            'text_transparency': self.settings.get('default_text_transparency', 39),
            'overlay_color': self.settings.get('default_overlay_color', (0,0,0)),
            'text_color': self.settings.get('default_text_color', (255,255,255)),
            'fullscreen_fallback': self.settings.get('default_fullscreen_fallback', True),
         }
        self.show_alert_overlay(test_alert)

    def stop_ongoing_alerts(self, silent=False):
        """Closes all currently active overlay windows."""
        if not self.overlays:
             if not silent: print("No ongoing alerts to stop.")
             return

        overlays_to_close = list(self.overlays)
        num_stopped = len(overlays_to_close)
        if not silent: print(f"Stopping {num_stopped} ongoing alert overlay(s)...")

        for overlay in overlays_to_close:
             try:
                 overlay.closed.disconnect(self.remove_overlay)
             except TypeError:
                 pass
             overlay.close()

        self.overlays.clear()

        if not silent:
             print("All overlays stopped.")
             self.tray_icon.showMessage("Alerts Stopped", f"{num_stopped} alert overlay(s) closed.", QSystemTrayIcon.Information, 2000)

# --- Application Entry Point ---
if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("GentleAlertScheduler")
    app.setOrganizationName("YourOrg") # Optional
    app.setApplicationVersion("1.7") # Incremented version for new feature

    # Ensure config directory exists before creating window
    get_config_dir()

    window = MainWindow()
    # Initial window state is hidden, relies on tray icon

    sys.exit(app.exec_())
