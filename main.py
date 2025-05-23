# -*- coding: utf-8 -*-
"""
Gentle Alert Scheduler: A PyQt5 application for creating and managing timed,
full-screen visual alerts.

This application allows users to schedule visual alerts that take over the screen
for a configured duration. It features a system tray icon for background operation,
persistent storage of alerts and settings, and options to customize alert
appearance and behavior.
"""
import sys
import os
import json
import logging 
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

# Conditional import for Windows features (e.g., registry access for startup)
if sys.platform == "win32":
    try:
        import winreg
    except ImportError:
        winreg = None 
        # Logging not fully configured here, print is acceptable for this very early warning.
        print("Warning: 'winreg' module not found. Startup features disabled.") 
else:
    winreg = None

# --- Global Application Constants ---
# This section defines constants used throughout the application for consistency
# and ease of modification.

# --- Core Application Identifiers & Filenames ---
APP_NAME_FULL = "GentleAlertScheduler"
TRAY_ICON_FILENAME = "alert.png"
SETTINGS_FILENAME = 'settings.json'
ALERTS_FILENAME = 'alerts.json'
APP_VERSION = "2.8" # Current application version

# --- Formatting ---
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
DATE_FORMAT_STR = "yyyy-MM-dd"
TIME_FORMAT_STR = "HH:mm:ss"
DATETIME_FORMAT_STR = f"{DATE_FORMAT_STR} {TIME_FORMAT_STR}" # Combined for convenience

# --- Alert Dictionary Keys (used for storing and retrieving alert properties) ---
ALERT_KEY_ENABLED = 'enabled'
ALERT_KEY_DATE = 'date'
ALERT_KEY_TIME = 'time'
ALERT_KEY_REPEAT = 'repeat'
ALERT_KEY_TEXT = 'text'
ALERT_KEY_DISPLAY = 'display'
ALERT_KEY_EXPANSION_TIME = 'expansion_time'
ALERT_KEY_DURATION_MULTIPLIER = 'duration_multiplier'
ALERT_KEY_START_SIZE = 'start_size'
ALERT_KEY_TRANSPARENCY = 'transparency'
ALERT_KEY_TEXT_TRANSPARENCY = 'text_transparency'
ALERT_KEY_OVERLAY_COLOR = 'overlay_color'
ALERT_KEY_TEXT_COLOR = 'text_color'
ALERT_KEY_WEEKDAYS = 'weekdays' # For weekly repeat
ALERT_KEY_DAY_OF_MONTH = 'day_of_month' # For monthly repeat
ALERT_KEY_ORIGINAL_INDEX = 'original_alert_index' # Used to track delayed alerts

# --- Settings Dictionary Keys (used for application default settings) ---
SETTING_KEY_DEFAULT_EXPANSION_TIME = 'default_expansion_time'
SETTING_KEY_DEFAULT_DURATION_MULTIPLIER = 'default_duration_multiplier'
SETTING_KEY_DEFAULT_START_SIZE = 'default_start_size'
SETTING_KEY_DEFAULT_TRANSPARENCY = 'default_transparency'
SETTING_KEY_DEFAULT_TEXT_TRANSPARENCY = 'default_text_transparency'
SETTING_KEY_DEFAULT_OVERLAY_COLOR = 'default_overlay_color'
SETTING_KEY_DEFAULT_TEXT_COLOR = 'default_text_color'
SETTING_KEY_DEFAULT_DISPLAY = 'default_display'
SETTING_KEY_MAX_PIXELS_PER_STEP = 'max_pixels_per_step'

# --- Repeat Options (for alert scheduling) ---
REPEAT_OPTION_NONE = 'No Repeat'
REPEAT_OPTION_DAILY = 'Daily'
REPEAT_OPTION_WEEKLY = 'Weekly'
REPEAT_OPTION_MONTHLY = 'Monthly'
REPEAT_OPTIONS = [REPEAT_OPTION_NONE, REPEAT_OPTION_DAILY, REPEAT_OPTION_WEEKLY, REPEAT_OPTION_MONTHLY]
WEEKDAYS_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] # For weekly repeat day selection

# --- Display Options (for multi-monitor support) ---
DISPLAY_OPTION_MAIN = 'Main'
DISPLAY_OPTION_ALL = 'All'
DISPLAY_OPTIONS = [DISPLAY_OPTION_MAIN, DISPLAY_OPTION_ALL]

# --- UI Text & Titles ---
TITLE_APP = APP_NAME_FULL
TITLE_ADD_ALERT = "Add Alert"
TITLE_EDIT_ALERT = "Edit Alert"
TITLE_SETTINGS = "Settings"
TITLE_CONFIRM_REMOVAL = "Confirm Removal"
TITLE_SELECT_OVERLAY_COLOR = "Select Overlay Color"
TITLE_SELECT_TEXT_COLOR = "Select Text Color"
TITLE_STARTUP_ERROR = "Startup Error"
TITLE_STARTUP_CHECK_ERROR = "Startup Check Error" # For WindowsStartupManager
TITLE_STARTUP_UPDATE = "Update Startup"
TITLE_STARTUP_ADD = "Add to Startup"
TITLE_STARTUP_SUCCESS = "Startup Success"
TITLE_NO_SELECTION = "No Selection"
TITLE_ERROR = "Error" # Generic error title

# --- UI Table Headers & Column Indices ---
TABLE_HEADER_DATE = "Date"
TABLE_HEADER_TIME = "Time"
TABLE_HEADER_REPEAT = "Repeat"
TABLE_HEADER_TEXT = "Text"
TABLE_HEADER_DISPLAY = "Display"
TABLE_HEADER_ENABLED = "Enabled"
TABLE_HEADER_TEST = "Test"
TABLE_HEADER_EDIT = "Edit"

ALERT_TABLE_HEADERS = [
    TABLE_HEADER_DATE, TABLE_HEADER_TIME, TABLE_HEADER_REPEAT, 
    TABLE_HEADER_TEXT, TABLE_HEADER_DISPLAY, TABLE_HEADER_ENABLED, 
    TABLE_HEADER_TEST, TABLE_HEADER_EDIT
]
ALERT_TABLE_COLUMN_COUNT = len(ALERT_TABLE_HEADERS)

TABLE_COL_IDX_DATE = ALERT_TABLE_HEADERS.index(TABLE_HEADER_DATE)
TABLE_COL_IDX_TIME = ALERT_TABLE_HEADERS.index(TABLE_HEADER_TIME)
TABLE_COL_IDX_REPEAT = ALERT_TABLE_HEADERS.index(TABLE_HEADER_REPEAT)
TABLE_COL_IDX_TEXT = ALERT_TABLE_HEADERS.index(TABLE_HEADER_TEXT)
TABLE_COL_IDX_DISPLAY = ALERT_TABLE_HEADERS.index(TABLE_HEADER_DISPLAY)
TABLE_COL_IDX_ENABLED = ALERT_TABLE_HEADERS.index(TABLE_HEADER_ENABLED)
TABLE_COL_IDX_TEST = ALERT_TABLE_HEADERS.index(TABLE_HEADER_TEST)
TABLE_COL_IDX_EDIT = ALERT_TABLE_HEADERS.index(TABLE_HEADER_EDIT)

# --- Default Values for Spinboxes/Ranges (if not from ConfigManager directly) ---
DEFAULT_EXPANSION_TIME_MIN = 0.1
DEFAULT_EXPANSION_TIME_MAX = 1440
DEFAULT_DURATION_MULTIPLIER_MIN = 0.1
DEFAULT_DURATION_MULTIPLIER_MAX = 10.0
DEFAULT_START_SIZE_MIN = 1
DEFAULT_START_SIZE_MAX = 10000
DEFAULT_TRANSPARENCY_MIN = 0
DEFAULT_TRANSPARENCY_MAX = 100
DEFAULT_DAY_OF_MONTH_MIN = 1
DEFAULT_DAY_OF_MONTH_MAX = 31
DEFAULT_MAX_PIXELS_PER_STEP_MIN = 1
DEFAULT_MAX_PIXELS_PER_STEP_MAX = 1000

# --- Global logger instance for the application ---
logger = logging.getLogger(APP_NAME_FULL)

def resource_path(relative_path):
    """
    Get absolute path to resource, works for development and for PyInstaller.
    In PyInstaller, resources are bundled into a temporary folder (_MEIPASS).
    
    Args:
        relative_path (str): The relative path to the resource.
        
    Returns:
        str: The absolute path to the resource.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Not running as PyInstaller bundle, use script's directory
        base_path = os.path.dirname(os.path.abspath(__file__)) 
    return os.path.join(base_path, relative_path)

# --- UI Utility Functions ---
def set_button_style_for_color(button, color_tuple, logger_instance=None):
    """
    Sets the button's stylesheet (background and text color) based on the given color tuple.
    Automatically determines a contrasting text color (black or white).

    Args:
        button (QPushButton): The button widget to style.
        color_tuple (tuple): An RGB tuple (e.g., (255, 0, 0) for red).
        logger_instance (logging.Logger, optional): Specific logger to use. Defaults to global `logger`.
    """
    log_ref = logger_instance if logger_instance else logger 
    
    if color_tuple and len(color_tuple) == 3 and all(isinstance(v, int) and 0 <= v <= 255 for v in color_tuple):
        try:
            # Basic contrast check: if sum of RGB is high, text is black, else white.
            # This is a simple heuristic and may not be perfect for all colors.
            text_color = 'black' if sum(color_tuple) > (255 * 3 / 2) else 'white' 
            button.setStyleSheet(
                f"background-color: rgb({color_tuple[0]}, {color_tuple[1]}, {color_tuple[2]});"
                f"color: {text_color};"
            )
        except Exception as e: # Catch any unexpected errors during stylesheet setting
            log_ref.error(f"Error setting button style: {e}", exc_info=True)
            button.setStyleSheet("") # Reset to default on error
    else:
        log_ref.warning(f"Invalid color_tuple (must be 3 ints 0-255) provided for button style: {color_tuple}")
        button.setStyleSheet("") # Reset if color is invalid

# --- Application Components ---

class ConfigManager:
    """
    Manages application configuration, including loading and saving settings and alerts.
    It handles default values and validation for configuration data, interacting with
    JSON files for persistence.
    """
    DEFAULT_SETTINGS = {
        SETTING_KEY_DEFAULT_EXPANSION_TIME: 60.0,
        SETTING_KEY_DEFAULT_DURATION_MULTIPLIER: 2.0,
        SETTING_KEY_DEFAULT_START_SIZE: 200,
        SETTING_KEY_DEFAULT_TRANSPARENCY: 39.0,
        SETTING_KEY_DEFAULT_TEXT_TRANSPARENCY: 39.0,
        SETTING_KEY_DEFAULT_OVERLAY_COLOR: (0,0,0), # Default black
        SETTING_KEY_DEFAULT_TEXT_COLOR: (255,255,255), # Default white
        SETTING_KEY_DEFAULT_DISPLAY: DISPLAY_OPTION_MAIN,
        SETTING_KEY_MAX_PIXELS_PER_STEP: 50,
    }
    
    def __init__(self, ui_manager_ref=None): 
        """
        Initializes the ConfigManager.

        Args:
            ui_manager_ref (QWidget, optional): Reference to the main UI manager (MainWindow), 
                                                used for displaying error messages if critical 
                                                config errors occur during initialization.
        """
        self.ui_manager = ui_manager_ref 
        self.app_name = APP_NAME_FULL
        self.settings = {} # Holds current application settings, loaded from file or defaults.
        self.alerts = []   # Holds the list of configured alerts, loaded from file.
        self._config_dir_path = self._ensure_config_dir() # Path to the configuration directory.

    def _ensure_config_dir(self):
        """
        Ensures the application's configuration directory exists, creating it if necessary.
        The path is OS-dependent (LOCALAPPDATA for Windows, .config for Linux/macOS).

        Returns:
            Path: The Path object representing the configuration directory.
                  Falls back to the current working directory if creation fails.
        """
        if sys.platform == "win32":
            app_data_dir = os.getenv('LOCALAPPDATA')
            if not app_data_dir: app_data_dir = Path.home() # Fallback if LOCALAPPDATA is not set
            config_dir = Path(app_data_dir) / self.app_name
        else: # Linux/macOS
            config_dir = Path.home() / ".config" / self.app_name
        try:
            config_dir.mkdir(parents=True, exist_ok=True) # Create directory if it doesn't exist
            logger.info(f"Configuration directory ensured at: {config_dir}")
            return config_dir
        except OSError as e: # Catch potential errors during directory creation
            logger.error(f"Error creating config directory {config_dir}: {e}", exc_info=True)
            if self.ui_manager: # Show warning to user if UI is available
                QMessageBox.warning(self.ui_manager, TITLE_ERROR, f"Could not create config directory: {config_dir}\nUsing current directory as fallback.")
            return Path(".") # Fallback to current directory

    def get_config_path(self, filename):
        """
        Constructs the full path for a given configuration file within the app's config directory.

        Args:
            filename (str): The name of the configuration file (e.g., 'settings.json').
        
        Returns:
            Path: The full Path object to the configuration file.
        """
        return self._config_dir_path / filename

    def load_settings(self):
        """
        Loads application settings from 'settings.json'.
        If the file doesn't exist or is invalid, it loads default settings defined in
        `ConfigManager.DEFAULT_SETTINGS`. Ensures all expected setting keys are present
        in `self.settings`, falling back to defaults for any missing or invalid ones.
        """
        settings_path = self.get_config_path(SETTINGS_FILENAME)
        self.settings = self.DEFAULT_SETTINGS.copy() # Start with a fresh copy of defaults
        
        if settings_path.exists():
            try:
                with open(settings_path, 'r', encoding='utf-8') as f: 
                    settings_loaded = json.load(f)
                
                # Validate and update settings from the loaded file
                for key, default_value in self.DEFAULT_SETTINGS.items():
                    loaded_value = settings_loaded.get(key) # Get value from file, or None if key missing
                    
                    if loaded_value is not None: # If the key was present in the file
                        if key.endswith('_color'): # Specific validation for color tuples
                            if isinstance(loaded_value, (list, tuple)) and \
                               len(loaded_value) == 3 and \
                               all(isinstance(c, int) and 0 <= c <= 255 for c in loaded_value):
                                self.settings[key] = tuple(loaded_value)
                            else: 
                                logger.warning(f"Invalid color format or component out of range (0-255) for '{key}' in settings: {loaded_value}. Using default: {default_value}.")
                                # self.settings[key] remains the default_value already set
                        elif isinstance(loaded_value, type(default_value)): # Check type consistency
                            self.settings[key] = loaded_value
                        else: 
                            logger.warning(f"Type mismatch for '{key}' in settings (expected {type(default_value)}, got {type(loaded_value)}), using default: {default_value}.")
                            # self.settings[key] remains the default_value
                    # If loaded_value is None (key not in file), the default value is already in self.settings
                logger.info(f"Settings successfully loaded and validated from {settings_path}")
                return # Settings are now populated
            except Exception as e: # Catch JSON parsing errors or other issues
                logger.error(f"Failed to load/parse {SETTINGS_FILENAME}: {e}. Using defaults.", exc_info=True)
                if self.ui_manager: QMessageBox.warning(self.ui_manager, "Load Settings Error", f"Failed to load/parse {SETTINGS_FILENAME}: {e}\nUsing defaults.")
        
        # If file didn't exist or loading failed, self.settings already contains defaults
        logger.info(f"Using default settings as {SETTINGS_FILENAME} was not found or failed to load.")

    def save_settings(self):
        """Saves current application settings to 'settings.json' in a human-readable format."""
        settings_path = self.get_config_path(SETTINGS_FILENAME)
        settings_to_save = self.settings.copy()
        # Convert color tuples to lists for JSON serialization, as JSON doesn't support tuples directly
        for key in [SETTING_KEY_DEFAULT_OVERLAY_COLOR, SETTING_KEY_DEFAULT_TEXT_COLOR]:
            if isinstance(settings_to_save.get(key), tuple):
                settings_to_save[key] = list(settings_to_save[key])
        try:
            with open(settings_path, 'w', encoding='utf-8') as f: 
                json.dump(settings_to_save, f, indent=4, ensure_ascii=False)
            logger.info(f"Settings saved to {settings_path}")
        except Exception as e:
            if self.ui_manager: QMessageBox.warning(self.ui_manager, "Save Settings Error", f"Failed to save settings: {e}")
            logger.error(f"Error saving settings to {settings_path}: {e}", exc_info=True)

    def validate_alert(self, alert_dict):
        """
        Validates an individual alert dictionary against expected keys, types, and value ranges.
        Uses current application settings (from `self.settings`) to provide default values
        for any missing or invalid fields within the alert data.

        Args:
            alert_dict (dict): The alert dictionary to validate.

        Returns:
            dict: A validated alert dictionary.
        """
        # Define default structure and values for an alert, pulling from current app settings where appropriate
        current_defaults = {
            ALERT_KEY_DATE: QDate.currentDate().toString(DATE_FORMAT_STR), 
            ALERT_KEY_TIME: QTime.currentTime().toString(TIME_FORMAT_STR),
            ALERT_KEY_REPEAT: REPEAT_OPTION_NONE, 
            ALERT_KEY_TEXT: '', 
            ALERT_KEY_DISPLAY: self.settings.get(SETTING_KEY_DEFAULT_DISPLAY, DISPLAY_OPTION_MAIN),
            ALERT_KEY_ENABLED: True, 
            ALERT_KEY_EXPANSION_TIME: self.settings.get(SETTING_KEY_DEFAULT_EXPANSION_TIME, 60.0),
            ALERT_KEY_DURATION_MULTIPLIER: self.settings.get(SETTING_KEY_DEFAULT_DURATION_MULTIPLIER, 2.0),
            ALERT_KEY_START_SIZE: self.settings.get(SETTING_KEY_DEFAULT_START_SIZE, 200),
            ALERT_KEY_TRANSPARENCY: self.settings.get(SETTING_KEY_DEFAULT_TRANSPARENCY, 39.0),
            ALERT_KEY_TEXT_TRANSPARENCY: self.settings.get(SETTING_KEY_DEFAULT_TEXT_TRANSPARENCY, 39.0),
            ALERT_KEY_OVERLAY_COLOR: self.settings.get(SETTING_KEY_DEFAULT_OVERLAY_COLOR, (0,0,0)),
            ALERT_KEY_TEXT_COLOR: self.settings.get(SETTING_KEY_DEFAULT_TEXT_COLOR, (255,255,255)),
            ALERT_KEY_WEEKDAYS: [], 
            ALERT_KEY_DAY_OF_MONTH: 1,
        }
        validated = {} # Build a new dictionary with validated/defaulted values
        for key, default_value in current_defaults.items():
            value = alert_dict.get(key, default_value) # Get value from input, or use the current_default
            
            # Specific validation and type coercion for each key
            if key.endswith('_color'): 
                is_valid_color = False
                if isinstance(value, (list, tuple)) and len(value) == 3 and all(isinstance(c, int) for c in value):
                    if all(0 <= c <= 255 for c in value): # Check 0-255 range for RGB components
                        value = tuple(value)
                        is_valid_color = True
                if not is_valid_color:
                    logger.warning(f"Invalid color format or component out of range (0-255) for alert key '{key}': {value}. Using default: {default_value}.")
                    value = default_value # Revert to default if validation fails
            elif key == ALERT_KEY_REPEAT: 
                if value is True: value = REPEAT_OPTION_DAILY # Legacy boolean handling
                elif value is False: value = REPEAT_OPTION_NONE 
                elif value not in REPEAT_OPTIONS: value = default_value # Ensure valid option
            elif key == ALERT_KEY_WEEKDAYS and not isinstance(value, list): 
                value = default_value # Ensure it's a list
            elif key in [ALERT_KEY_EXPANSION_TIME, ALERT_KEY_DURATION_MULTIPLIER, ALERT_KEY_TRANSPARENCY, ALERT_KEY_TEXT_TRANSPARENCY]:
                try: value = float(value) # Ensure float
                except (ValueError, TypeError): value = default_value
            elif key in [ALERT_KEY_START_SIZE, ALERT_KEY_DAY_OF_MONTH]:
                try: value = int(value) # Ensure int
                except (ValueError, TypeError): value = default_value
            elif key == ALERT_KEY_ENABLED and not isinstance(value, bool): 
                value = default_value # Ensure boolean
            
            validated[key] = value
        return validated

    def load_alerts(self):
        """Loads alerts from 'alerts.json'. Each alert is validated upon loading."""
        alerts_path = self.get_config_path(ALERTS_FILENAME)
        loaded_data = []
        if alerts_path.exists():
            try:
                with open(alerts_path, 'r', encoding='utf-8') as f: 
                    raw_data = json.load(f)
                if isinstance(raw_data, list): 
                    loaded_data = [self.validate_alert(a) for a in raw_data] # Validate each alert
                else: 
                    logger.warning(f"{ALERTS_FILENAME} has invalid format (expected a list of alerts).")
            except Exception as e: 
                logger.error(f"Failed to load/parse {ALERTS_FILENAME}: {e}", exc_info=True)
                if self.ui_manager: QMessageBox.warning(self.ui_manager, "Load Alerts Error", f"Failed to load/parse {ALERTS_FILENAME}: {e}")
        self.alerts = loaded_data
        logger.info(f"Loaded {len(self.alerts)} alerts from {alerts_path if alerts_path.exists() else 'defaults (file not found)'}.")

    def save_alerts(self):
        """Saves the current list of alerts to 'alerts.json' in a human-readable format."""
        alerts_path = self.get_config_path(ALERTS_FILENAME)
        alerts_to_save = []
        for alert in self.alerts:
            ac = alert.copy() # Work with a copy
            # Convert color tuples to lists for JSON serialization
            if isinstance(ac.get(ALERT_KEY_OVERLAY_COLOR), tuple): 
                ac[ALERT_KEY_OVERLAY_COLOR] = list(ac[ALERT_KEY_OVERLAY_COLOR])
            if isinstance(ac.get(ALERT_KEY_TEXT_COLOR), tuple): 
                ac[ALERT_KEY_TEXT_COLOR] = list(ac[ALERT_KEY_TEXT_COLOR])
            alerts_to_save.append(ac)
        try:
            with open(alerts_path, 'w', encoding='utf-8') as f: 
                json.dump(alerts_to_save, f, indent=4, ensure_ascii=False)
            logger.info(f"Alerts saved to {alerts_path}")
        except Exception as e:
            if self.ui_manager: QMessageBox.warning(self.ui_manager, "Save Alerts Error", f"Failed to save alerts: {e}")
            logger.error(f"Error saving alerts to {alerts_path}: {e}", exc_info=True)

class Scheduler:
    """
    Manages the scheduling and triggering of alerts using QTimer objects.
    It calculates next trigger times based on alert data (from ConfigManager) 
    and handles both regular and temporary (delayed) alerts.
    """
    def __init__(self, ui_manager_ref, config_manager_ref):
        """
        Initializes the Scheduler.

        Args:
            ui_manager_ref (MainWindow): Reference to the main UI manager for interactions like showing overlays.
            config_manager_ref (ConfigManager): Reference to the configuration manager for accessing alert data.
        """
        self.ui_manager = ui_manager_ref
        self.config_manager = config_manager_ref
        self.alert_timers = {}  # Stores QTimer objects for regular alerts, keyed by alert_index.
        self.temporary_timers = set() # Stores QTimer objects for temporary/delayed alerts.

    def initialize_timers(self):
        """
        Stops all existing timers and then schedules timers for all currently enabled alerts
        as defined in the ConfigManager.
        """
        self.stop_all_timers() # Clear any existing timers first
        for index, alert_data in enumerate(self.config_manager.alerts):
            if alert_data.get(ALERT_KEY_ENABLED, True): # Check if alert is enabled
                self.schedule_alert_timer(alert_data, index)
        logger.info(f"Scheduler initialized. {len(self.alert_timers)} active timers scheduled out of {len(self.config_manager.alerts)} total alerts.")

    def stop_all_timers(self):
        """Stops and deletes all active regular and temporary alert timers."""
        # Stop and delete regular alert timers
        for timer in self.alert_timers.values(): 
            timer.stop()
            timer.deleteLater() # Schedule for deletion by Qt event loop
        self.alert_timers.clear()
        
        # Stop and delete temporary alert timers
        for timer in self.temporary_timers: 
            timer.stop()
            timer.deleteLater()
        self.temporary_timers.clear()
        logger.info("All scheduler timers stopped and cleared.")

    def stop_alert_timer(self, alert_index):
        """
        Stops and removes the timer for a specific regular alert.

        Args:
            alert_index (int): The index of the alert whose timer should be stopped.
        """
        if alert_index in self.alert_timers:
            timer = self.alert_timers.pop(alert_index) # Remove from dictionary
            timer.stop()
            timer.deleteLater() # Schedule for deletion
            logger.debug(f"Stopped and removed timer for alert index {alert_index}.")

    def schedule_alert_timer(self, alert_data, alert_index):
        """
        Schedules a QTimer for a given regular alert based on its configuration.
        If a timer already exists for this alert_index, it's stopped and replaced.
        Non-repeating past alerts are automatically disabled and not scheduled.

        Args:
            alert_data (dict): The dictionary containing the alert's configuration.
            alert_index (int): The index of the alert in the ConfigManager's list.
        """
        self.stop_alert_timer(alert_index) # Ensure no duplicate timers for the same alert
        if not alert_data.get(ALERT_KEY_ENABLED, True): 
            logger.debug(f"Alert {alert_index} is disabled, not scheduling.")
            return # Don't schedule disabled alerts

        alert_time_str = alert_data.get(ALERT_KEY_TIME)
        alert_time = QTime.fromString(alert_time_str, TIME_FORMAT_STR) # Parse time string
        if not alert_time_str or not alert_time.isValid():
            logger.warning(f"Scheduler: Invalid/missing time for alert {alert_index} ('{alert_data.get(ALERT_KEY_TEXT,'No Text')}'). Cannot schedule.")
            return

        now = QDateTime.currentDateTime() # Get current date and time
        next_trigger_dt = self.calculate_next_trigger(now, alert_data) # Calculate next occurrence

        if not next_trigger_dt: # If no valid future trigger time
            # For non-repeating alerts, disable them if they are in the past
            if alert_data.get(ALERT_KEY_REPEAT) == REPEAT_OPTION_NONE and 0 <= alert_index < len(self.config_manager.alerts):
                logger.info(f"Scheduler: Non-repeating Alert {alert_index} ('{alert_data.get(ALERT_KEY_TEXT,'')}') is in the past. Disabling.")
                self.config_manager.alerts[alert_index][ALERT_KEY_ENABLED] = False # Update alert state
                if self.ui_manager: self.ui_manager.update_alert_table() # Reflect change in UI
                self.config_manager.save_alerts() # Persist the change
            return

        interval = now.msecsTo(next_trigger_dt) # Calculate milliseconds until next trigger
        if interval < 0: # Safeguard: Should ideally be caught by calculate_next_trigger
            logger.warning(f"Scheduler: Calculated negative interval ({interval}ms) for alert {alert_index}. Skipping. Next trigger was: {next_trigger_dt.toString()}. Now: {now.toString()}")
            return 

        # Create and configure the QTimer
        timer = QTimer(); 
        timer.setSingleShot(True) # Timer fires once
        # Use lambda to capture current alert_data (as a copy) and index for when timeout occurs
        timer.timeout.connect(lambda data=alert_data.copy(), idx=alert_index: self.trigger_alert(data, idx))
        timer.start(interval) # Start the timer with the calculated interval
        self.alert_timers[alert_index] = timer # Store the timer
        logger.debug(f"Scheduler: Scheduled alert {alert_index} ('{alert_data.get(ALERT_KEY_TEXT,'')}') for {next_trigger_dt.toString(DATETIME_FORMAT_STR)} (in {interval/1000.0:.1f}s)")

    def _schedule_single_alert_instance(self, alert_data):
        """
        Schedules a one-off timer, typically used for a delayed alert instance.
        These timers are managed in the `temporary_timers` set.

        Args:
            alert_data (dict): The dictionary containing configuration for the temporary alert.
        """
        alert_dt_str = f"{alert_data.get(ALERT_KEY_DATE)} {alert_data.get(ALERT_KEY_TIME)}"
        alert_datetime = QDateTime.fromString(alert_dt_str, DATETIME_FORMAT_STR)
        if not alert_datetime.isValid():
            logger.error(f"Scheduler: Invalid datetime for temporary alert: {alert_dt_str}")
            return
        
        interval = max(0, QDateTime.currentDateTime().msecsTo(alert_datetime)) # Ensure interval is non-negative
        
        temp_timer = QTimer(); 
        temp_timer.setSingleShot(True)
        # Pass the timer instance itself to the handler for removal after firing
        temp_timer.timeout.connect(lambda data=alert_data.copy(), t_ref=temp_timer: self._handle_temporary_alert_trigger(data, t_ref))
        self.temporary_timers.add(temp_timer) # Store reference to keep timer alive and allow removal
        temp_timer.start(interval)
        logger.debug(f"Scheduler: Scheduled temporary alert instance for {alert_datetime.toString(DATETIME_FORMAT_STR)}. Interval: {interval}ms. Total temp timers: {len(self.temporary_timers)}")

    def _handle_temporary_alert_trigger(self, alert_data, timer_instance):
        """
        Handles the firing of a temporary (delayed) alert timer.
        Shows the overlay and ensures the timer is cleaned up from `temporary_timers`.

        Args:
            alert_data (dict): The data for the temporary alert that has triggered.
            timer_instance (QTimer): The QTimer instance that fired.
        """
        logger.debug(f"Scheduler: Temporary timer fired for alert: {alert_data.get(ALERT_KEY_TEXT, 'No Text')}")
        try:
            self.trigger_alert(alert_data, -1) # -1 indicates a temporary/delayed alert
        finally:
            # Clean up the timer from the set and schedule it for deletion
            if timer_instance in self.temporary_timers:
                self.temporary_timers.remove(timer_instance)
                timer_instance.deleteLater() # Important for Qt resource management
                logger.debug(f"Scheduler: Removed temporary timer. Remaining: {len(self.temporary_timers)}")

    def calculate_next_trigger(self, current_datetime, alert_data):
        """
        Calculates the next QDateTime an alert should trigger based on its repeat settings
        and start date/time.

        Args:
            current_datetime (QDateTime): The current date and time, used as a reference.
            alert_data (dict): The alert's configuration data.

        Returns:
            QDateTime or None: The next QDateTime for the alert to trigger, 
                               or None if no valid future trigger can be determined (e.g.,
                               a non-repeating past alert, or invalid repeat parameters).
        """
        alert_time = QTime.fromString(alert_data[ALERT_KEY_TIME], TIME_FORMAT_STR)
        if not alert_time.isValid(): 
            logger.warning(f"Scheduler: Invalid time string '{alert_data.get(ALERT_KEY_TIME)}' in calculate_next_trigger for alert '{alert_data.get(ALERT_KEY_TEXT,'No Text')}'.")
            return None
        
        start_date_str = alert_data.get(ALERT_KEY_DATE, '')
        start_date = QDate.fromString(start_date_str, DATE_FORMAT_STR)
        repeat_mode = alert_data.get(ALERT_KEY_REPEAT, REPEAT_OPTION_NONE)

        # Validate start_date; for repeating alerts, fallback to today if original start_date is invalid or missing
        if not start_date.isValid():
            if repeat_mode == REPEAT_OPTION_NONE: 
                logger.warning(f"Scheduler: Invalid or missing start date '{start_date_str}' for non-repeating alert '{alert_data.get(ALERT_KEY_TEXT,'No Text')}'. Cannot calculate trigger.")
                return None
            start_date = current_datetime.date() # Fallback for repeating alerts
            logger.debug(f"Scheduler: Invalid or missing start date '{start_date_str}' for alert '{alert_data.get(ALERT_KEY_TEXT,'No Text')}', falling back to current date for repeating alert.")

        # --- Logic for different repeat modes ---
        if repeat_mode == REPEAT_OPTION_NONE:
            trigger_dt = QDateTime(start_date, alert_time)
            # Only return if it's in the future (or exactly now) relative to current_datetime
            return trigger_dt if trigger_dt >= current_datetime else None
        
        # For repeating alerts, determine the first potential check_date
        check_date = current_datetime.date()
        # If the alert's start_date is in the future, start checking from there
        if start_date > check_date: 
            check_date = start_date

        if repeat_mode == REPEAT_OPTION_DAILY:
            potential_dt = QDateTime(check_date, alert_time)
            # If today's alert time is past OR if check_date was before the alert's original start_date, schedule for the next day.
            return potential_dt if potential_dt >= current_datetime else QDateTime(check_date.addDays(1), alert_time)
        
        elif repeat_mode == REPEAT_OPTION_WEEKLY:
            weekdays_map = {day: i+1 for i, day in enumerate(WEEKDAYS_ABBR)} # Mon=1, ..., Sun=7 (Qt standard)
            target_days_of_week = {weekdays_map[d] for d in alert_data.get(ALERT_KEY_WEEKDAYS,[]) if d in weekdays_map}
            if not target_days_of_week: 
                logger.warning(f"Weekly alert '{alert_data.get(ALERT_KEY_TEXT, '')}' has no valid weekdays selected.")
                return None 
            
            # Iterate starting from check_date for up to 7 days to find the next valid weekday
            for i in range(8): # Max 7 days ahead + current day
                current_check_date = check_date.addDays(i)
                # Check if the day is a target day AND it's on or after the alert's original start_date
                if current_check_date.dayOfWeek() in target_days_of_week and current_check_date >= start_date:
                    potential_dt = QDateTime(current_check_date, alert_time)
                    if potential_dt >= current_datetime: 
                        return potential_dt # Found the next valid trigger
            return None # No valid trigger found in the next week

        elif repeat_mode == REPEAT_OPTION_MONTHLY:
            day_of_month = alert_data.get(ALERT_KEY_DAY_OF_MONTH, 1)
            if not (1 <= day_of_month <= 31): 
                logger.warning(f"Monthly alert '{alert_data.get(ALERT_KEY_TEXT, '')}' has invalid day_of_month: {day_of_month}.")
                return None 

            # Start checking from the first day of the check_date's month
            temp_check_date = QDate(check_date.year(), check_date.month(), 1) 
            for _ in range(25): # Max search of approx 2 years (24 months + 1 for safety)
                days_in_month = temp_check_date.daysInMonth()
                actual_day_to_check = min(day_of_month, days_in_month) # Adjust for months with fewer days (e.g. 31st in Feb)
                
                potential_trigger_date = QDate(temp_check_date.year(), temp_check_date.month(), actual_day_to_check)
                
                # Ensure the date is on or after the original start_date and also on or after the current check_date's month start
                if potential_trigger_date >= start_date and potential_trigger_date >= QDate(check_date.year(), check_date.month(), 1):
                    potential_dt = QDateTime(potential_trigger_date, alert_time)
                    if potential_dt >= current_datetime:
                        return potential_dt
                
                # Move to the first day of the next month
                if temp_check_date.month() == 12:
                    temp_check_date = QDate(temp_check_date.year() + 1, 1, 1)
                else:
                    temp_check_date = QDate(temp_check_date.year(), temp_check_date.month() + 1, 1)
            logger.warning(f"Monthly alert '{alert_data.get(ALERT_KEY_TEXT, '')}' could not find a trigger within 25 months search.")
            return None 
        
        logger.error(f"Unknown repeat mode '{repeat_mode}' for alert '{alert_data.get(ALERT_KEY_TEXT, '')}'.")
        return None # Should not be reached if repeat_mode is one of the known options


    def trigger_alert(self, alert_data, alert_index):
        """
        Handles the logic when an alert timer (regular or temporary) fires.
        Shows the alert overlay and then, for regular alerts, either reschedules it
        (if repeating) or disables it (if non-repeating).

        Args:
            alert_data (dict): The configuration data of the alert being triggered.
                               For regular alerts, this is a copy of the state at scheduling time.
            alert_index (int): The index of the alert in `ConfigManager.alerts`. 
                               -1 indicates a temporary/delayed alert (not in `ConfigManager.alerts`).
        """
        if alert_index == -1: # This is a temporary/delayed alert
            logger.debug(f"Scheduler: Triggering temporary/delayed alert: {alert_data.get(ALERT_KEY_TEXT, 'No Text')}")
            if self.ui_manager: self.ui_manager.show_alert_overlay(alert_data)
        else: # This is a regular alert scheduled from self.config_manager.alerts
            # Validate index and get the *current* configuration from self.config_manager.alerts
            if not (0 <= alert_index < len(self.config_manager.alerts)):
                logger.info(f"Scheduler: Skipping trigger for alert index {alert_index} (alert likely removed).")
                self.stop_alert_timer(alert_index) # Clean up potential stray timer
                return 
            
            current_alert_config = self.config_manager.alerts[alert_index] # Get the latest config
            if not current_alert_config.get(ALERT_KEY_ENABLED, True):
                logger.info(f"Scheduler: Skipping trigger for alert {alert_index} (alert is now disabled).")
                self.stop_alert_timer(alert_index) # Clean up timer if it was disabled since scheduling
                return 
            
            logger.debug(f"Scheduler: Triggering alert (Index: {alert_index}): {current_alert_config.get(ALERT_KEY_TEXT, 'No Text')}")
            if self.ui_manager: self.ui_manager.show_alert_overlay(current_alert_config) # Show using current config
            
            # --- Reschedule or Disable after triggering ---
            if current_alert_config.get(ALERT_KEY_REPEAT, REPEAT_OPTION_NONE) == REPEAT_OPTION_NONE:
                # Disable non-repeating alert after it fires once
                logger.info(f"Scheduler: Disabling non-repeating alert {alert_index} ('{current_alert_config.get(ALERT_KEY_TEXT,'')}') after triggering.")
                self.config_manager.alerts[alert_index][ALERT_KEY_ENABLED] = False
                self.stop_alert_timer(alert_index) # Remove its timer
                if self.ui_manager: self.ui_manager.update_alert_table() # Update UI to show disabled state
                self.config_manager.save_alerts() # Persist the change
            else: # For repeating alerts, reschedule for its next occurrence
                logger.debug(f"Scheduler: Rescheduling repeating alert {alert_index} ('{current_alert_config.get(ALERT_KEY_TEXT,'')}').")
                self.schedule_alert_timer(current_alert_config, alert_index) 

    def reindex_timers_after_removal(self, removed_alert_original_index):
        """
        Adjusts alert timers after an alert has been removed from the list.
        This involves stopping timers for alerts at and after the removed index,
        and then rescheduling them with their new, shifted indices.

        Args:
            removed_alert_original_index (int): The original index of the alert that was removed.
        """
        logger.debug(f"Scheduler: Re-indexing timers due to removal at original index {removed_alert_original_index}.")
        
        # Stop all timers that were for alerts at or after the removed index
        # These timers are now invalid because their associated alert_index is wrong or gone.
        current_timer_indices_to_remove = [idx for idx in self.alert_timers.keys() if idx >= removed_alert_original_index]
        for i in sorted(current_timer_indices_to_remove, reverse=True): # Iterate safely while removing
             self.stop_alert_timer(i)
        
        # Reschedule timers for alerts from the removed_idx onwards, using their new correct indices
        # The alerts list in config_manager is already updated (item popped).
        for new_idx in range(removed_alert_original_index, len(self.config_manager.alerts)):
            alert_data = self.config_manager.alerts[new_idx]
            if alert_data.get(ALERT_KEY_ENABLED, True):
                logger.debug(f"Scheduler: Re-scheduling alert at new index {new_idx} ('{alert_data.get(ALERT_KEY_TEXT,'')}') after removal operation.")
                self.schedule_alert_timer(alert_data, new_idx)
            # else: # If it's disabled, stop_alert_timer would have been called if it had one; no action needed

    def delay_alerts(self, minutes):
        """
        Delays all currently active (visible) alerts by the specified number of minutes.
        This involves stopping the current overlays and scheduling temporary one-off alerts.

        Args:
            minutes (int): The number of minutes to delay the alerts by.
        """
        if not self.ui_manager or not self.ui_manager.overlays:
            if self.ui_manager: self.ui_manager.tray_icon.showMessage("Delay Alerts", "No active alerts to delay.", QSystemTrayIcon.Information, 2000)
            return

        # Collect data from currently active overlays to reschedule them
        active_alerts_data = [ov.alert for ov in list(self.ui_manager.overlays)] # Iterate over a copy
        logger.info(f"Scheduler: Delaying {len(active_alerts_data)} active overlay instance(s) by {minutes} minutes.")
        
        # Identify unique logical alerts to avoid rescheduling the same alert multiple times if it's on multiple screens
        unique_alerts_map = {} # Store alert_data keyed by a unique ID (e.g., serialized JSON)
        for alert_item in active_alerts_data:
            try: 
                # Serialize the alert data to create a unique ID. Sort keys for consistency.
                alert_id = json.dumps(alert_item, sort_keys=True) 
            except TypeError: # Fallback if serialization fails (e.g., non-standard data types)
                alert_id = id(alert_item) # Less reliable but a usable fallback for uniqueness
                logger.warning(f"Scheduler: Could not reliably serialize alert data for uniqueness check: {alert_item}. Using id() as fallback.", exc_info=True)
            if alert_id not in unique_alerts_map: 
                unique_alerts_map[alert_id] = alert_item # Store the first instance of this unique alert
        
        if self.ui_manager: self.ui_manager.stop_ongoing_alerts(silent=True) # Stop current visual overlays
        
        now = QDateTime.currentDateTime()
        for original_alert_data in unique_alerts_map.values():
            temp_alert = original_alert_data.copy() # Create a copy to modify for the temporary alert
            # Update for the delayed instance
            temp_alert.update({
                ALERT_KEY_ORIGINAL_INDEX: -1, # Mark as a temporary/delayed alert (not tied to main list index)
                ALERT_KEY_REPEAT: REPEAT_OPTION_NONE, # Delayed alerts are one-off, they don't repeat further
                ALERT_KEY_ENABLED: True, # Ensure it's enabled for this one-off trigger
                ALERT_KEY_DATE: now.addSecs(minutes * 60).date().toString(DATE_FORMAT_STR), # Set future date
                ALERT_KEY_TIME: now.addSecs(minutes * 60).time().toString(TIME_FORMAT_STR)  # Set future time
            })
            logger.debug(f"Scheduler: Scheduling temporary alert: {temp_alert.get(ALERT_KEY_TEXT, 'No Text')} at {temp_alert[ALERT_KEY_TIME]}")
            self._schedule_single_alert_instance(temp_alert) # Schedule this temporary alert
        
        if self.ui_manager and len(unique_alerts_map) > 0:
            self.ui_manager.tray_icon.showMessage("Delay Alerts", f"Delayed {len(unique_alerts_map)} unique alert(s) by {minutes} minutes.", QSystemTrayIcon.Information, 3000)

class WindowsStartupManager:
    """
    Handles adding or removing the application from Windows startup registry.
    This class is intended for Windows platforms only.
    """
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run" # Registry path for HKEY_CURRENT_USER startup items
    
    def __init__(self, ui_manager_ref, app_name_val):
        """
        Initializes the WindowsStartupManager.

        Args:
            ui_manager_ref (MainWindow): Reference to the main UI (MainWindow) for displaying messages.
            app_name_val (str): The application name as it should appear in the registry.
        """
        self.ui_manager = ui_manager_ref
        self.app_name = app_name_val 

    def get_executable_path(self):
        """
        Determines the path to the currently running executable.
        Handles both standard script execution and PyInstaller bundled executables.

        Returns:
            str: The absolute path to the executable.
        """
        if getattr(sys, 'frozen', False): # Check if running as a PyInstaller bundle
            return sys.executable # sys.executable is the path to the frozen .exe
        else: # Running as a script
            return os.path.abspath(sys.argv[0]) # Path to the .py script

    def check_startup_status(self):
        """
        Checks if the application is correctly configured to run at Windows startup.
        If not, or if the path is incorrect, it prompts the user to add/update the entry.
        This method does nothing if `winreg` (Windows Registry API) is not available.
        """
        if not winreg: return # Only proceed if winreg module is available
        
        exe_path = self.get_executable_path()
        try:
            # Open the Run key for the current user
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_READ)
            stored_val, _ = winreg.QueryValueEx(key, self.app_name) # Read the stored path for this app
            winreg.CloseKey(key)
            
            # Compare resolved paths to handle potential differences (e.g., casing, symlinks)
            if Path(stored_val.strip('"')).resolve() != Path(exe_path).resolve(): # Strip quotes which might be around path
                logger.info(f"Startup path mismatch. Stored: '{stored_val}', Current: '{exe_path}'. Prompting for update.")
                self.ask_add_to_startup(update=True)
        except FileNotFoundError: # Application entry not found in startup
            logger.info("Application not found in startup. Prompting to add.")
            self.ask_add_to_startup()
        except Exception as e: # Catch other potential registry access errors
            logger.error(f"Failed to check startup status: {e}", exc_info=True)
            if self.ui_manager: QMessageBox.warning(self.ui_manager, TITLE_STARTUP_CHECK_ERROR, f"Failed to check startup status:\n{e}")

    def ask_add_to_startup(self, update=False):
        """
        Asks the user via a QMessageBox if they want to add or update the application
        in Windows startup.

        Args:
            update (bool): If True, the message prompts for an update due to a path change.
                           Otherwise, it prompts to add to startup.
        """
        if not winreg or not self.ui_manager: return # Ensure necessary components are available
        
        msg = ('The application path seems to have changed. Update startup entry?' if update 
               else f'Run {self.app_name} automatically when Windows starts?')
        title = TITLE_STARTUP_UPDATE if update else TITLE_STARTUP_ADD
        
        # Ask the user
        if QMessageBox.question(self.ui_manager, title, msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.manage_startup_entry(add=True) # User confirmed, add/update the entry

    def manage_startup_entry(self, add=True):
        """
        Adds or removes the application entry from the Windows startup registry.

        Args:
            add (bool): True to add or update the entry, False to remove it.
        
        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        if not winreg: return False # Only proceed if winreg is available
        
        exe_path = self.get_executable_path()
        try:
            # Open or create the Run key with write access
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_WRITE)
            if add:
                # Set the value: app name -> "executable path" (quoted)
                winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
                action_msg = "added/updated in startup"
                logger.info(f"Application '{self.app_name}' {action_msg} with path: {exe_path}")
            else: # Remove
                 try: 
                     winreg.DeleteValue(key, self.app_name) # Attempt to delete the value
                     action_msg = "removed from startup"
                     logger.info(f"Application '{self.app_name}' {action_msg}.")
                 except FileNotFoundError: # If the value doesn't exist, no action needed
                     action_msg = "not found in startup (no removal needed)"
                     logger.info(f"Application '{self.app_name}' was {action_msg}.")
            winreg.CloseKey(key)
            if self.ui_manager: QMessageBox.information(self.ui_manager, TITLE_STARTUP_SUCCESS, f"Application {action_msg}.")
            return True
        except PermissionError:
            logger.error(f"Permission denied trying to {'add/update' if add else 'remove'} startup entry.", exc_info=True)
            if self.ui_manager: QMessageBox.warning(self.ui_manager, TITLE_STARTUP_ERROR, "Permission denied. Could not modify startup settings.\nTry running as administrator if this is unexpected.")
            return False
        except Exception as e: # Catch other potential errors
            logger.error(f"Failed to {('add/update' if add else 'remove')} startup entry: {e}", exc_info=True)
            if self.ui_manager: QMessageBox.warning(self.ui_manager, TITLE_STARTUP_ERROR, f"Failed to {('add' if add else 'remove')} startup entry:\n{e}")
            return False

# --- UI Classes ---

class TransparentOverlay(QWidget):
    """
    A transparent, frameless window that gradually expands to fill a screen,
    displaying alert text. Used to provide a visual, non-intrusive alert.
    """
    closed = pyqtSignal(QWidget) # Signal emitted when the overlay closes itself

    def __init__(self, time_to_full_size, transparency, color, initial_size,
                 max_pixels_per_step, exit_after, text, text_transparency, text_color, alert, screen=None):
        """
        Initializes the transparent overlay window.

        Args:
            time_to_full_size (float): Time in minutes for the overlay to reach full screen size.
            transparency (float): Overlay background transparency percentage (0-100).
            color (tuple): RGB tuple for the overlay background color.
            initial_size (int): Initial size (width and height) of the overlay in pixels.
            max_pixels_per_step (int): Maximum pixels the overlay expands by in each timer step.
            exit_after (float): Total duration in minutes after which the overlay closes.
            text (str): The text to display on the overlay.
            text_transparency (float): Text transparency percentage (0-100).
            text_color (tuple): RGB tuple for the text color.
            alert (dict): The alert data dictionary associated with this overlay.
            screen (QScreen, optional): The screen on which to display the overlay. Defaults to primary.
        """
        super().__init__()
        self.alert = alert # Store the original alert data for reference (e.g., if delayed)
        self.current_width = initial_size
        self.current_height = initial_size
        
        # Window flags for a frameless, always-on-top, transparent tool window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground) # Enables transparency

        if screen is None: screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        self.screen_width = screen_geometry.width()
        self.screen_height = screen_geometry.height()
        self.screen_x = screen_geometry.x() # Top-left x of the screen
        self.screen_y = screen_geometry.y() # Top-left y of the screen

        # Initial position at bottom-right of the screen (adjusts as it grows)
        initial_x = self.screen_x + self.screen_width - self.current_width
        initial_y = self.screen_y # Starts at top, expands downwards and leftwards
        self.setGeometry(int(initial_x), int(initial_y), int(self.current_width), int(self.current_height))

        # Store visual properties
        self.overlay_color = tuple(color) if isinstance(color, list) else color
        self.transparency = int(transparency * 255 / 100) # Convert percentage to 0-255 alpha
        self.text_transparency = int(text_transparency * 255 / 100)
        self.text = text
        self.text_color = tuple(text_color) if isinstance(text_color, list) else text_color

        # Calculate expansion animation parameters
        self.target_width = self.screen_width
        self.target_height = self.screen_height
        # Determine total pixels to expand along the larger dimension
        total_pixels_to_expand = max(self.target_width - self.current_width, self.target_height - self.current_height)
        # Number of steps for the animation
        total_steps = max(1, total_pixels_to_expand / max_pixels_per_step if max_pixels_per_step > 0 else 1)
        # Interval for the expansion timer
        update_interval_ms = (time_to_full_size * 60 * 1000) / total_steps if total_steps > 0 else 0

        # Calculate increment per step for width and height
        self.width_increment = (self.target_width - self.current_width) / total_steps if total_steps > 0 else 0
        self.height_increment = (self.target_height - self.current_height) / total_steps if total_steps > 0 else 0

        # Timer for controlling the expansion animation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.expand_window)
        if update_interval_ms > 0 and (self.width_increment != 0 or self.height_increment != 0):
            self.timer.start(int(update_interval_ms))
        else: # If no expansion needed or instant, set to full size
            self.expand_window(force_full=True)

        # Timer for automatically closing the overlay after its duration
        self.exit_timer = QTimer(self)
        self.exit_timer.timeout.connect(self.close_application)
        self.exit_timer.setSingleShot(True)
        self.exit_timer.start(int(exit_after * 60 * 1000)) # Duration in milliseconds

    def expand_window(self, force_full=False):
        """
        Handles one step of the overlay expansion animation or forces full size.
        Updates geometry and redraws. Stops timer if target size is reached.
        
        Args:
            force_full (bool): If True, immediately expands to full screen size.
        """
        if force_full:
            self.current_width = self.target_width
            self.current_height = self.target_height
        else:
            self.current_width += self.width_increment
            self.current_height += self.height_increment
            # Ensure current size does not exceed target size
            self.current_width = min(self.current_width, self.target_width) if self.width_increment >= 0 else max(self.current_width, self.target_width)
            self.current_height = min(self.current_height, self.target_height) if self.height_increment >= 0 else max(self.current_height, self.target_height)

        # Calculate new X position to keep it anchored to the right side as it expands leftwards
        new_x = self.screen_x + self.screen_width - self.current_width
        # Y position remains at the top of the screen
        self.setGeometry(int(new_x), self.screen_y, int(self.current_width), int(self.current_height))
        self.update() # Trigger a repaint

        # Stop animation timer if target size is reached
        if self.current_width == self.target_width and self.current_height == self.target_height:
            self.timer.stop()

    def close_application(self):
        """Stops all timers, emits closed signal, and closes the widget."""
        self.timer.stop()
        self.exit_timer.stop()
        self.closed.emit(self) # Notify manager that this overlay is closing
        self.close()

    def paintEvent(self, event):
        """
        Custom paint event to draw the semi-transparent background and alert text.
        
        Args:
            event (QPaintEvent): The paint event.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing) # Smooth edges
        painter.setPen(Qt.NoPen) # No border for the overlay
        
        # Draw background
        overlay_rgb = self.overlay_color if isinstance(self.overlay_color, tuple) else (0, 0, 0) # Fallback
        painter.setBrush(QColor(*overlay_rgb, self.transparency))
        painter.drawRect(self.rect())

        # Draw text if present
        if self.text:
            text_rgb = self.text_color if isinstance(self.text_color, tuple) else (255, 255, 255) # Fallback
            painter.setPen(QColor(*text_rgb, self.text_transparency))
            font = QFont("Arial", 24) # Basic font, consider making configurable
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, self.text) # Center text

# --- Add/Edit Alert Dialog ---

class AddAlertDialog(QDialog):
    """
    A dialog window for adding a new alert or editing an existing one.
    It provides input fields for all alert properties, using defaults from
    ConfigManager or existing alert data.
    """
    def __init__(self, parent=None, default_settings=None, alert_data=None):
        """
        Initializes the Add/Edit Alert dialog.

        Args:
            parent (QWidget, optional): The parent widget (typically MainWindow).
            default_settings (dict, optional): Dictionary of default settings to use for new alerts.
                                               These are usually from ConfigManager.
            alert_data (dict, optional): If provided, pre-fills the dialog for editing an existing alert.
                                         If None, the dialog is for adding a new alert.
        """
        super().__init__(parent)
        self.setWindowTitle(TITLE_ADD_ALERT if alert_data is None else TITLE_EDIT_ALERT)
        self.alert_data = alert_data # Store existing alert data if editing, else None
        # Ensure default_settings is a dictionary, falling back to ConfigManager's defaults if necessary
        self.default_settings = default_settings if default_settings else ConfigManager.DEFAULT_SETTINGS.copy()

        self.form_layout = QFormLayout() # For structured label-field pairs
        self.layout = QVBoxLayout(self)
        self.layout.addLayout(self.form_layout) 

        # Use existing alert data if editing, otherwise use defaults (from default_settings)
        # This ensures that when creating a new alert, fields are pre-populated with app defaults.
        edit_data = alert_data if alert_data else self.default_settings

        # --- Initialize UI Fields ---
        # Date field
        self.date_edit = QDateEdit(QDate.fromString(edit_data.get(ALERT_KEY_DATE, QDate.currentDate().toString(DATE_FORMAT_STR)), DATE_FORMAT_STR))
        self.date_edit.setCalendarPopup(True)
        self.form_layout.addRow("Start Date:", self.date_edit)
        # Time field
        self.time_edit = QTimeEdit(QTime.fromString(edit_data.get(ALERT_KEY_TIME, QTime.currentTime().toString(TIME_FORMAT_STR)), TIME_FORMAT_STR))
        self.form_layout.addRow("Alert Time:", self.time_edit)
        # Repeat options
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItems(REPEAT_OPTIONS)
        self.repeat_combo.setCurrentText(edit_data.get(ALERT_KEY_REPEAT, REPEAT_OPTION_NONE))
        self.repeat_combo.currentIndexChanged.connect(self.update_repeat_options) # Show/hide day selection
        self.form_layout.addRow("Repeat:", self.repeat_combo)

        # Weekday selection (for weekly repeat)
        self.weekday_checkboxes = []
        weekdays_layout = QHBoxLayout()
        selected_weekdays = edit_data.get(ALERT_KEY_WEEKDAYS, [])
        for day in WEEKDAYS_ABBR:
            checkbox = QCheckBox(day); checkbox.setChecked(day in selected_weekdays)
            self.weekday_checkboxes.append(checkbox); weekdays_layout.addWidget(checkbox)
        self.weekdays_widget = QWidget(); self.weekdays_widget.setLayout(weekdays_layout)
        self.form_layout.addRow("Days of Week:", self.weekdays_widget) # Label added here

        # Day of month selection (for monthly repeat)
        self.day_of_month_spinbox = QSpinBox(); self.day_of_month_spinbox.setRange(DEFAULT_DAY_OF_MONTH_MIN, DEFAULT_DAY_OF_MONTH_MAX)
        self.day_of_month_spinbox.setValue(edit_data.get(ALERT_KEY_DAY_OF_MONTH, 1))
        self.form_layout.addRow("Day of Month:", self.day_of_month_spinbox) # Label added here

        # Alert text
        self.text_edit = QLineEdit(edit_data.get(ALERT_KEY_TEXT, ''))
        self.form_layout.addRow("Alert Text (optional):", self.text_edit)
        
        # Numeric settings for overlay behavior, using constants for ranges
        self.expansion_time_edit = QDoubleSpinBox(); self.expansion_time_edit.setRange(DEFAULT_EXPANSION_TIME_MIN, DEFAULT_EXPANSION_TIME_MAX); self.expansion_time_edit.setDecimals(1); self.expansion_time_edit.setSingleStep(1)
        self.expansion_time_edit.setValue(edit_data.get(ALERT_KEY_EXPANSION_TIME, self.default_settings.get(SETTING_KEY_DEFAULT_EXPANSION_TIME, 60)))
        self.form_layout.addRow("Expansion Time (minutes):", self.expansion_time_edit)
        
        self.duration_multiplier_edit = QDoubleSpinBox(); self.duration_multiplier_edit.setRange(DEFAULT_DURATION_MULTIPLIER_MIN, DEFAULT_DURATION_MULTIPLIER_MAX); self.duration_multiplier_edit.setSingleStep(0.1)
        self.duration_multiplier_edit.setValue(edit_data.get(ALERT_KEY_DURATION_MULTIPLIER, self.default_settings.get(SETTING_KEY_DEFAULT_DURATION_MULTIPLIER, 2.0)))
        self.form_layout.addRow("Alert Duration Multiplier:", self.duration_multiplier_edit)

        self.start_size_edit = QSpinBox(); self.start_size_edit.setRange(DEFAULT_START_SIZE_MIN, DEFAULT_START_SIZE_MAX)
        self.start_size_edit.setValue(edit_data.get(ALERT_KEY_START_SIZE, self.default_settings.get(SETTING_KEY_DEFAULT_START_SIZE, 200)))
        self.form_layout.addRow("Start Size:", self.start_size_edit)

        self.transparency_edit = QDoubleSpinBox(); self.transparency_edit.setRange(DEFAULT_TRANSPARENCY_MIN, DEFAULT_TRANSPARENCY_MAX); self.transparency_edit.setSingleStep(1)
        self.transparency_edit.setValue(edit_data.get(ALERT_KEY_TRANSPARENCY, self.default_settings.get(SETTING_KEY_DEFAULT_TRANSPARENCY, 39)))
        self.form_layout.addRow("Overlay Transparency (%):", self.transparency_edit)

        self.text_transparency_edit = QDoubleSpinBox(); self.text_transparency_edit.setRange(DEFAULT_TRANSPARENCY_MIN, DEFAULT_TRANSPARENCY_MAX); self.text_transparency_edit.setSingleStep(1) # Assuming same range as overlay
        self.text_transparency_edit.setValue(edit_data.get(ALERT_KEY_TEXT_TRANSPARENCY, self.default_settings.get(SETTING_KEY_DEFAULT_TEXT_TRANSPARENCY, 39)))
        self.form_layout.addRow("Text Transparency (%):", self.text_transparency_edit)

        # Color selection buttons, styled using the utility function
        self.overlay_color_button = QPushButton("Select Overlay Color"); self.overlay_color_button.clicked.connect(self.select_overlay_color)
        self.overlay_color = tuple(edit_data.get(ALERT_KEY_OVERLAY_COLOR, self.default_settings.get(SETTING_KEY_DEFAULT_OVERLAY_COLOR, (0,0,0))))
        set_button_style_for_color(self.overlay_color_button, self.overlay_color, logger) 
        self.form_layout.addRow("Overlay Color:", self.overlay_color_button)

        self.text_color_button = QPushButton("Select Text Color"); self.text_color_button.clicked.connect(self.select_text_color)
        self.text_color = tuple(edit_data.get(ALERT_KEY_TEXT_COLOR, self.default_settings.get(SETTING_KEY_DEFAULT_TEXT_COLOR, (255,255,255))))
        set_button_style_for_color(self.text_color_button, self.text_color, logger) 
        self.form_layout.addRow("Text Color:", self.text_color_button)

        # Display target (main screen or all screens)
        self.display_combo = QComboBox(); self.display_combo.addItems(DISPLAY_OPTIONS)
        self.display_combo.setCurrentText(edit_data.get(ALERT_KEY_DISPLAY, self.default_settings.get(SETTING_KEY_DEFAULT_DISPLAY, DISPLAY_OPTION_MAIN)))
        self.form_layout.addRow("Display On:", self.display_combo)

        # OK and Cancel buttons
        self.button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK"); self.cancel_button = QPushButton("Cancel")
        self.button_layout.addWidget(self.ok_button); self.button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_layout) 
        self.ok_button.clicked.connect(self.accept); self.cancel_button.clicked.connect(self.reject)

        self.update_repeat_options() # Set initial visibility of repeat-specific options

    def update_repeat_options(self):
        """Shows or hides UI elements (weekday/day of month selectors) based on the selected repeat option."""
        repeat_mode = self.repeat_combo.currentText()
        is_weekly = (repeat_mode == REPEAT_OPTION_WEEKLY)
        is_monthly = (repeat_mode == REPEAT_OPTION_MONTHLY)

        self.weekdays_widget.setVisible(is_weekly)
        self.day_of_month_spinbox.setVisible(is_monthly)

        # Also hide/show the corresponding labels in the QFormLayout for a cleaner UI
        weekdays_label = self.form_layout.labelForField(self.weekdays_widget)
        if weekdays_label: weekdays_label.setVisible(is_weekly)

        day_of_month_label = self.form_layout.labelForField(self.day_of_month_spinbox)
        if day_of_month_label: day_of_month_label.setVisible(is_monthly)

    def select_overlay_color(self):
        """Opens a color dialog to select the overlay background color and updates the button style."""
        initial_color = QColor(*self.overlay_color) # Current color as initial for dialog
        color = QColorDialog.getColor(initial_color, self, TITLE_SELECT_OVERLAY_COLOR)
        if color.isValid(): # If user selected a color and clicked OK
            self.overlay_color = (color.red(), color.green(), color.blue())
            set_button_style_for_color(self.overlay_color_button, self.overlay_color, logger) 

    def select_text_color(self):
        """Opens a color dialog to select the text color and updates the button style."""
        initial_color = QColor(*self.text_color) # Current color as initial for dialog
        color = QColorDialog.getColor(initial_color, self, TITLE_SELECT_TEXT_COLOR)
        if color.isValid(): # If user selected a color and clicked OK
            self.text_color = (color.red(), color.green(), color.blue())
            set_button_style_for_color(self.text_color_button, self.text_color, logger) 

    def get_alert(self):
        """
        Retrieves all alert data from the dialog's input fields into a dictionary.

        Returns:
            dict: A dictionary containing all configured alert properties, using ALERT_KEY constants.
        """
        repeat_mode = self.repeat_combo.currentText()
        alert = {
            ALERT_KEY_ENABLED: self.alert_data.get(ALERT_KEY_ENABLED, True) if self.alert_data else True, # Preserve existing or default to True
            ALERT_KEY_DATE: self.date_edit.date().toString(DATE_FORMAT_STR),
            ALERT_KEY_TIME: self.time_edit.time().toString(TIME_FORMAT_STR),
            ALERT_KEY_REPEAT: repeat_mode,
            ALERT_KEY_TEXT: self.text_edit.text(),
            ALERT_KEY_DISPLAY: self.display_combo.currentText(),
            ALERT_KEY_EXPANSION_TIME: self.expansion_time_edit.value(),
            ALERT_KEY_DURATION_MULTIPLIER: self.duration_multiplier_edit.value(),
            ALERT_KEY_START_SIZE: self.start_size_edit.value(),
            ALERT_KEY_TRANSPARENCY: self.transparency_edit.value(),
            ALERT_KEY_TEXT_TRANSPARENCY: self.text_transparency_edit.value(),
            ALERT_KEY_OVERLAY_COLOR: self.overlay_color,
            ALERT_KEY_TEXT_COLOR: self.text_color,
        }
        # Add repeat-specific fields only if applicable
        if repeat_mode == REPEAT_OPTION_WEEKLY: 
            alert[ALERT_KEY_WEEKDAYS] = [cb.text() for cb in self.weekday_checkboxes if cb.isChecked()]
        elif repeat_mode == REPEAT_OPTION_MONTHLY: 
            alert[ALERT_KEY_DAY_OF_MONTH] = self.day_of_month_spinbox.value()
        return alert

# --- Settings Dialog ---
class SettingsDialog(QDialog):
    """
    A dialog window for configuring application-wide default settings.
    These settings are used as fallbacks when creating new alerts or if specific
    alert properties are missing.
    """
    def __init__(self, parent=None, settings=None): 
        """
        Initializes the Settings dialog.

        Args:
            parent (QWidget, optional): The parent widget (typically MainWindow).
            settings (dict, optional): Current application settings to pre-fill the dialog.
                                       Falls back to ConfigManager.DEFAULT_SETTINGS if None.
        """
        super().__init__(parent)
        self.setWindowTitle(TITLE_SETTINGS)
        # Use provided settings, or ConfigManager's defaults if none passed, ensuring a copy is used
        self.current_settings = settings.copy() if settings else ConfigManager.DEFAULT_SETTINGS.copy()

        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # --- Initialize UI Fields for each setting ---
        # Default Expansion Time
        self.default_expansion_time_edit = QDoubleSpinBox()
        self.default_expansion_time_edit.setRange(DEFAULT_EXPANSION_TIME_MIN, DEFAULT_EXPANSION_TIME_MAX); self.default_expansion_time_edit.setDecimals(1); self.default_expansion_time_edit.setSingleStep(1)
        self.default_expansion_time_edit.setValue(self.current_settings.get(SETTING_KEY_DEFAULT_EXPANSION_TIME, 60))
        form_layout.addRow("Default Expansion Time (minutes):", self.default_expansion_time_edit)

        # Default Duration Multiplier
        self.default_duration_multiplier_edit = QDoubleSpinBox()
        self.default_duration_multiplier_edit.setRange(DEFAULT_DURATION_MULTIPLIER_MIN, DEFAULT_DURATION_MULTIPLIER_MAX); self.default_duration_multiplier_edit.setSingleStep(0.1)
        self.default_duration_multiplier_edit.setValue(self.current_settings.get(SETTING_KEY_DEFAULT_DURATION_MULTIPLIER, 2.0))
        form_layout.addRow("Default Duration Multiplier:", self.default_duration_multiplier_edit)

        # Default Start Size
        self.default_start_size_edit = QSpinBox()
        self.default_start_size_edit.setRange(DEFAULT_START_SIZE_MIN, DEFAULT_START_SIZE_MAX)
        self.default_start_size_edit.setValue(self.current_settings.get(SETTING_KEY_DEFAULT_START_SIZE, 200))
        form_layout.addRow("Default Start Size:", self.default_start_size_edit)

        # Default Overlay Transparency
        self.default_transparency_edit = QDoubleSpinBox()
        self.default_transparency_edit.setRange(DEFAULT_TRANSPARENCY_MIN, DEFAULT_TRANSPARENCY_MAX); self.default_transparency_edit.setSingleStep(1)
        self.default_transparency_edit.setValue(self.current_settings.get(SETTING_KEY_DEFAULT_TRANSPARENCY, 39))
        form_layout.addRow("Default Overlay Transparency (%):", self.default_transparency_edit)

        # Default Text Transparency
        self.default_text_transparency_edit = QDoubleSpinBox()
        self.default_text_transparency_edit.setRange(DEFAULT_TRANSPARENCY_MIN, DEFAULT_TRANSPARENCY_MAX); self.default_text_transparency_edit.setSingleStep(1) # Assuming same range
        self.default_text_transparency_edit.setValue(self.current_settings.get(SETTING_KEY_DEFAULT_TEXT_TRANSPARENCY, 39))
        form_layout.addRow("Default Text Transparency (%):", self.default_text_transparency_edit)

        # Default Overlay Color Button
        self.default_overlay_color_button = QPushButton("Select Default Overlay Color")
        self.default_overlay_color_button.clicked.connect(self.select_default_overlay_color)
        self.default_overlay_color = tuple(self.current_settings.get(SETTING_KEY_DEFAULT_OVERLAY_COLOR, (0,0,0)))
        set_button_style_for_color(self.default_overlay_color_button, self.default_overlay_color, logger) 
        form_layout.addRow("Default Overlay Color:", self.default_overlay_color_button)

        # Default Text Color Button
        self.default_text_color_button = QPushButton("Select Default Text Color")
        self.default_text_color_button.clicked.connect(self.select_default_text_color)
        self.default_text_color = tuple(self.current_settings.get(SETTING_KEY_DEFAULT_TEXT_COLOR, (255,255,255)))
        set_button_style_for_color(self.default_text_color_button, self.default_text_color, logger) 
        form_layout.addRow("Default Text Color:", self.default_text_color_button)

        # Default Display Option
        self.default_display_combo = QComboBox()
        self.default_display_combo.addItems(DISPLAY_OPTIONS)
        self.default_display_combo.setCurrentText(self.current_settings.get(SETTING_KEY_DEFAULT_DISPLAY, DISPLAY_OPTION_MAIN))
        form_layout.addRow("Default Display On:", self.default_display_combo)

        # Max Pixels Per Step for expansion animation
        self.max_pixels_per_step_edit = QSpinBox()
        self.max_pixels_per_step_edit.setRange(DEFAULT_MAX_PIXELS_PER_STEP_MIN, DEFAULT_MAX_PIXELS_PER_STEP_MAX)
        self.max_pixels_per_step_edit.setValue(self.current_settings.get(SETTING_KEY_MAX_PIXELS_PER_STEP, 50))
        form_layout.addRow("Max Pixels Per Step (Expansion):", self.max_pixels_per_step_edit)

        self.layout.addLayout(form_layout)

        # Save and Cancel buttons
        self.button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")
        self.button_layout.addWidget(self.save_button)
        self.button_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.button_layout)

        self.save_button.clicked.connect(self.accept) # Accept the dialog (saves settings)
        self.cancel_button.clicked.connect(self.reject) # Reject the dialog (discard changes)

    def select_default_overlay_color(self):
        """Opens a color dialog for the default overlay color and updates the button style."""
        initial_color = QColor(*self.default_overlay_color)
        color = QColorDialog.getColor(initial_color, self, TITLE_SELECT_OVERLAY_COLOR)
        if color.isValid():
            self.default_overlay_color = (color.red(), color.green(), color.blue())
            set_button_style_for_color(self.default_overlay_color_button, self.default_overlay_color, logger) 

    def select_default_text_color(self):
        """Opens a color dialog for the default text color and updates the button style."""
        initial_color = QColor(*self.default_text_color)
        color = QColorDialog.getColor(initial_color, self, TITLE_SELECT_TEXT_COLOR)
        if color.isValid():
            self.default_text_color = (color.red(), color.green(), color.blue())
            set_button_style_for_color(self.default_text_color_button, self.default_text_color, logger) 

    def get_settings(self):
        """
        Retrieves all settings from the dialog's input fields into a dictionary.

        Returns:
            dict: A dictionary containing all configured default settings.
        """
        return {
            SETTING_KEY_DEFAULT_EXPANSION_TIME: self.default_expansion_time_edit.value(),
            SETTING_KEY_DEFAULT_DURATION_MULTIPLIER: self.default_duration_multiplier_edit.value(),
            SETTING_KEY_DEFAULT_START_SIZE: self.default_start_size_edit.value(),
            SETTING_KEY_DEFAULT_TRANSPARENCY: self.default_transparency_edit.value(),
            SETTING_KEY_DEFAULT_TEXT_TRANSPARENCY: self.default_text_transparency_edit.value(),
            SETTING_KEY_DEFAULT_OVERLAY_COLOR: self.default_overlay_color,
            SETTING_KEY_DEFAULT_TEXT_COLOR: self.default_text_color,
            SETTING_KEY_DEFAULT_DISPLAY: self.default_display_combo.currentText(),
            SETTING_KEY_MAX_PIXELS_PER_STEP: self.max_pixels_per_step_edit.value(),
        }

# --- UIManager Class (Main Application Window) ---

class MainWindow(QMainWindow): 
    """
    The main application window, responsible for the primary user interface,
    managing interactions between different components like alert configuration,
    scheduling, and settings. It also handles the system tray icon.
    """
    def __init__(self):
        """
        Initializes the MainWindow, sets up manager classes, UI, loads data,
        and creates the system tray icon.
        """
        super().__init__()
        self.setWindowTitle(TITLE_APP)
        self.hide() # Application starts hidden, accessible via system tray

        # Initialize core application components (managers)
        self.config_manager = ConfigManager(ui_manager_ref=self) 
        self.scheduler = Scheduler(ui_manager_ref=self, config_manager_ref=self.config_manager)
        
        # Windows-specific startup manager
        if sys.platform == "win32" and winreg:
            self.startup_manager = WindowsStartupManager(ui_manager_ref=self, app_name_val=APP_NAME_FULL)
        else:
            self.startup_manager = None

        self.overlays = set() # Set to keep track of active TransparentOverlay instances

        self._setup_ui() # Initialize the user interface elements

        # Load configurations and initialize scheduler
        self.config_manager.load_settings() 
        self.config_manager.load_alerts()   
        self.scheduler.initialize_timers()  # Schedule timers for loaded alerts
        self.update_alert_table()           # Populate the UI table with alerts

        self.create_tray_icon() # Setup and show the system tray icon
        if self.tray_icon and self.tray_icon.isVisible(): 
             self.tray_icon.showMessage(APP_NAME_FULL, "Application started.", QSystemTrayIcon.Information, 3000)
        
        if self.startup_manager: # Check and manage Windows startup setting if applicable
            self.startup_manager.check_startup_status()

    def _setup_ui(self):
        """Sets up the main UI layout and widgets, including the alert table and action buttons."""
        self.central_widget = QWidget(); self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Alert Table Setup
        self.alert_table = QTableWidget()
        self.alert_table.setColumnCount(ALERT_TABLE_COLUMN_COUNT) 
        self.alert_table.setHorizontalHeaderLabels(ALERT_TABLE_HEADERS)
        self.alert_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # Columns stretch to fill available width
        self.alert_table.setSelectionBehavior(QTableWidget.SelectRows) # Select whole rows instead of individual cells
        self.alert_table.setSelectionMode(QTableWidget.SingleSelection) # Only one row can be selected at a time
        self.layout.addWidget(self.alert_table)

        # Layout for Action Buttons
        btn_layout = QHBoxLayout()
        # Define button texts and their corresponding callback methods
        actions = [ 
            ("Add Alert", self.open_add_alert_dialog),
            ("Remove Selected", self.remove_selected_alert),
            ("Send Test Alert", self.send_test_alert_default), 
            ("Stop Ongoing Alerts", lambda: self.stop_ongoing_alerts(silent=False)), # Use lambda for methods needing arguments
            ("Settings", self.open_settings_dialog)
        ]
        for name, callback in actions: # Create and add each button
            btn = QPushButton(name); btn.clicked.connect(callback)
            btn_layout.addWidget(btn)
        self.layout.addLayout(btn_layout)

    def create_tray_icon(self):
        """Creates and configures the system tray icon and its context menu."""
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = resource_path(TRAY_ICON_FILENAME) # Get path to icon using helper
        if Path(icon_path).is_file(): 
            self.tray_icon.setIcon(QIcon(icon_path))
            logger.debug(f"Loaded tray icon from: {icon_path}")
        else: 
            logger.warning(f"Tray icon file not found at resolved path: {icon_path}. Using standard OS icon.")
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon)) # Fallback to a standard system icon
        
        # Create context menu for the tray icon
        tray_menu = QMenu()
        tray_menu.addAction("Open Scheduler", self.show_main_window)
        tray_menu.addAction("Stop Ongoing Alerts", lambda: self.stop_ongoing_alerts(silent=False))
        delay_menu = tray_menu.addMenu("Delay Active Alerts") # Submenu for delay options
        for mins in [10, 20, 30]: # Predefined delay durations
            delay_menu.addAction(f"Delay by {mins} minutes", lambda m=mins: self.scheduler.delay_alerts(m)) # Lambda to pass argument
        tray_menu.addAction("Exit", self.exit_application) # Action to quit the application
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated) # Handle clicks on the tray icon
        self.tray_icon.show()

    def show_main_window(self): 
        """Shows, raises to the front, and activates the main application window."""
        self.show(); self.raise_(); self.activateWindow()

    def on_tray_icon_activated(self, reason):
        """
        Handles activation events on the system tray icon.
        Typically, a single click (QSystemTrayIcon.Trigger) shows the main window.
        
        Args:
            reason (QSystemTrayIcon.ActivationReason): The reason for the activation.
        """
        if reason == QSystemTrayIcon.Trigger: # Typically a left-click
            self.show_main_window()

    def closeEvent(self, event):
        """
        Overrides the default close event (e.g., clicking the 'X' button) 
        to hide the window to the system tray instead of exiting the application.
        
        Args:
            event (QCloseEvent): The close event.
        """
        event.ignore(); self.hide() # Ignore the close event and hide the window
        if self.tray_icon and self.tray_icon.isVisible(): # Show a notification if tray icon is active
            self.tray_icon.showMessage(APP_NAME_FULL, "Still running in the background.", QSystemTrayIcon.Information, 2000)

    def exit_application(self):
        """
        Handles the complete shutdown of the application. This includes stopping overlays,
        saving data, stopping timers, and quitting the Qt application.
        """
        logger.info("Exiting application...")
        self.stop_ongoing_alerts(silent=True) # Close any active overlays silently
        self.config_manager.save_alerts()    # Save current alerts to file
        self.config_manager.save_settings()  # Save current settings to file
        self.scheduler.stop_all_timers()     # Stop all scheduled alert timers
        if self.tray_icon: self.tray_icon.hide() # Hide the tray icon
        QApplication.instance().quit() # Quit the Qt application event loop

    def open_add_alert_dialog(self):
        """Opens the Add/Edit dialog for creating a new alert, using current default settings."""
        # Pass a copy of current settings to be used as defaults by the dialog
        dialog = AddAlertDialog(self, default_settings=self.config_manager.settings.copy())
        if dialog.exec_() == QDialog.Accepted: # If user clicks "OK"
            new_alert = dialog.get_alert() # Retrieve data from dialog
            self.config_manager.alerts.append(new_alert) # Add to internal list
            alert_idx = len(self.config_manager.alerts) - 1 # Get index of new alert
            logger.info(f"New alert '{new_alert.get(ALERT_KEY_TEXT)}' added at index {alert_idx}")
            self.scheduler.schedule_alert_timer(new_alert, alert_idx) # Schedule its timer
            self.update_alert_table() # Refresh the UI table
            self.config_manager.save_alerts() # Persist changes

    def open_edit_alert_dialog(self, index):
        """
        Opens the Add/Edit dialog for modifying an existing alert.
        
        Args:
            index (int): The index of the alert to edit in the ConfigManager's alerts list.
        """
        if not (0 <= index < len(self.config_manager.alerts)): 
            logger.warning(f"Edit attempt for invalid alert index: {index}")
            QMessageBox.warning(self, TITLE_ERROR, "Invalid alert index for editing.")
            return
        
        alert_to_edit = self.config_manager.alerts[index]
        # Pass copies of settings (for defaults) and alert data (for editing)
        dialog = AddAlertDialog(self, default_settings=self.config_manager.settings.copy(), alert_data=alert_to_edit.copy())
        if dialog.exec_() == QDialog.Accepted:
            updated_alert = dialog.get_alert()
            self.config_manager.alerts[index] = updated_alert # Update the alert in the list
            logger.info(f"Alert at index {index} ('{updated_alert.get(ALERT_KEY_TEXT)}') updated.")
            self.scheduler.schedule_alert_timer(updated_alert, index) # Reschedule with new data
            self.update_alert_table()
            self.config_manager.save_alerts()

    def open_settings_dialog(self):
        """Opens the Settings dialog to allow configuration of application default values."""
        # Pass a copy of current settings to the dialog to avoid direct modification
        dialog = SettingsDialog(self, settings=self.config_manager.settings.copy())
        if dialog.exec_() == QDialog.Accepted:
            self.config_manager.settings.update(dialog.get_settings()) # Update ConfigManager's settings
            self.config_manager.save_settings() # Persist the new settings
            logger.info("Application settings updated via settings dialog.")

    def update_alert_table(self):
        """
        Repopulates the alert table in the main window with the current list of alerts
        from the ConfigManager. Sets up cell widgets for 'Enabled' checkbox, 'Test', and 'Edit' buttons.
        """
        self.alert_table.setRowCount(0) # Clear existing rows before repopulating
        self.alert_table.setRowCount(len(self.config_manager.alerts))
        
        for row, alert in enumerate(self.config_manager.alerts):
            # Populate standard text-based cells
            self.alert_table.setItem(row, TABLE_COL_IDX_DATE, QTableWidgetItem(alert.get(ALERT_KEY_DATE, '')))
            self.alert_table.setItem(row, TABLE_COL_IDX_TIME, QTableWidgetItem(alert.get(ALERT_KEY_TIME, '')))
            self.alert_table.setItem(row, TABLE_COL_IDX_REPEAT, QTableWidgetItem(alert.get(ALERT_KEY_REPEAT, '')))
            self.alert_table.setItem(row, TABLE_COL_IDX_TEXT, QTableWidgetItem(alert.get(ALERT_KEY_TEXT, '')))
            self.alert_table.setItem(row, TABLE_COL_IDX_DISPLAY, QTableWidgetItem(alert.get(ALERT_KEY_DISPLAY, '')))
            
            # Make text items non-editable by default
            for col in range(TABLE_COL_IDX_ENABLED): # Iterate up to the 'Enabled' column
                 item = self.alert_table.item(row, col)
                 if item: item.setFlags(item.flags() & ~Qt.ItemIsEditable) # Remove editable flag
            
            # "Enabled" Checkbox cell
            cb = QCheckBox(); cb.setChecked(alert.get(ALERT_KEY_ENABLED, True))
            # Lambda captures row index `r` for the callback to know which alert to toggle
            cb.stateChanged.connect(lambda state, r=row: self.toggle_alert_enabled(r, state == Qt.Checked))
            # Use a QWidget and QHBoxLayout to center the checkbox in the cell
            cell_widget_enabled = QWidget(); cell_layout_enabled = QHBoxLayout(cell_widget_enabled)
            cell_layout_enabled.addWidget(cb); cell_layout_enabled.setAlignment(Qt.AlignCenter); cell_layout_enabled.setContentsMargins(0,0,0,0)
            self.alert_table.setCellWidget(row, TABLE_COL_IDX_ENABLED, cell_widget_enabled) 

            # Test and Edit Buttons in cells
            btn_test = QPushButton(TABLE_HEADER_TEST)
            btn_test.clicked.connect(lambda _, r=row: self.test_specific_alert(r)) # Lambda to pass row index
            
            btn_edit = QPushButton(TABLE_HEADER_EDIT)
            btn_edit.clicked.connect(lambda _, r=row: self.open_edit_alert_dialog(r)) # Lambda to pass row index
            
            self.alert_table.setCellWidget(row, TABLE_COL_IDX_TEST, btn_test) 
            self.alert_table.setCellWidget(row, TABLE_COL_IDX_EDIT, btn_edit) 

    def toggle_alert_enabled(self, index, is_enabled):
        """
        Toggles the enabled state of an alert, updates its scheduling accordingly,
        and saves the changes.

        Args:
            index (int): The index of the alert in the ConfigManager's alerts list.
            is_enabled (bool): The new enabled state (True if checked, False otherwise).
        """
        if not (0 <= index < len(self.config_manager.alerts)): 
            logger.warning(f"toggle_alert_enabled called with invalid index: {index}")
            return
        
        logger.debug(f"Toggling alert {index} ('{self.config_manager.alerts[index].get(ALERT_KEY_TEXT)}') enabled state to: {is_enabled}")
        self.config_manager.alerts[index][ALERT_KEY_ENABLED] = is_enabled # Update in-memory list
        alert_data = self.config_manager.alerts[index]
        
        # Reschedule or stop timer based on new state
        if is_enabled: 
            self.scheduler.schedule_alert_timer(alert_data, index)
        else: 
            self.scheduler.stop_alert_timer(index)
            
        self.config_manager.save_alerts() # Persist the change

    def remove_selected_alert(self):
        """Removes the selected alert from the table and data, after user confirmation."""
        selected_rows = self.alert_table.selectionModel().selectedRows()
        if not selected_rows: 
            QMessageBox.warning(self, TITLE_NO_SELECTION, "Please select an alert to remove."); return
        
        row_to_remove = selected_rows[0].row() # Get the actual model index of the selected row
        
        alert_text = self.config_manager.alerts[row_to_remove].get(ALERT_KEY_TEXT, '(No Text)')
        # Confirm removal with the user
        if QMessageBox.question(self, TITLE_CONFIRM_REMOVAL, f"Remove alert: '{alert_text}'?", 
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            removed_alert_data = self.config_manager.alerts.pop(row_to_remove) # Remove from list
            logger.info(f"Removed alert index {row_to_remove}: '{removed_alert_data.get(ALERT_KEY_TEXT)}'")
            
            self.scheduler.reindex_timers_after_removal(row_to_remove) # Adjust scheduler timers
            self.update_alert_table() # Refresh UI
            self.config_manager.save_alerts() # Persist changes

    def show_alert_overlay(self, alert_data):
        """
        Creates and displays a TransparentOverlay window based on the provided alert data.
        Handles multi-monitor display options ('Main' or 'All').

        Args:
            alert_data (dict): The configuration dictionary for the alert overlay.
        """
        s = self.config_manager.settings # Get current application default settings
        
        # Prepare parameters for TransparentOverlay, using defaults from settings if not in alert_data
        overlay_params = {
            'time_to_full_size': alert_data.get(ALERT_KEY_EXPANSION_TIME, s.get(SETTING_KEY_DEFAULT_EXPANSION_TIME)),
            'transparency': alert_data.get(ALERT_KEY_TRANSPARENCY, s.get(SETTING_KEY_DEFAULT_TRANSPARENCY)),
            'color': tuple(alert_data.get(ALERT_KEY_OVERLAY_COLOR, s.get(SETTING_KEY_DEFAULT_OVERLAY_COLOR))),
            'initial_size': alert_data.get(ALERT_KEY_START_SIZE, s.get(SETTING_KEY_DEFAULT_START_SIZE)),
            'max_pixels_per_step': s.get(SETTING_KEY_MAX_PIXELS_PER_STEP),
            'text': alert_data.get(ALERT_KEY_TEXT, ''),
            'text_transparency': alert_data.get(ALERT_KEY_TEXT_TRANSPARENCY, s.get(SETTING_KEY_DEFAULT_TEXT_TRANSPARENCY)),
            'text_color': tuple(alert_data.get(ALERT_KEY_TEXT_COLOR, s.get(SETTING_KEY_DEFAULT_TEXT_COLOR))),
            'alert': alert_data # Pass the full alert data for reference (e.g., for delay feature)
        }
        # Calculate total duration for the overlay
        overlay_params['exit_after'] = overlay_params['time_to_full_size'] * \
                                      alert_data.get(ALERT_KEY_DURATION_MULTIPLIER, s.get(SETTING_KEY_DEFAULT_DURATION_MULTIPLIER))

        display_on = alert_data.get(ALERT_KEY_DISPLAY, s.get(SETTING_KEY_DEFAULT_DISPLAY))
        target_screens = QApplication.screens() if display_on == DISPLAY_OPTION_ALL else [QApplication.primaryScreen()]

        for screen in target_screens:
            if screen: # Ensure screen object is valid
                overlay = TransparentOverlay(**overlay_params, screen=screen)
                overlay.closed.connect(self.remove_overlay_reference) # Connect signal for cleanup
                overlay.show()
                self.overlays.add(overlay) # Keep track of active overlays to manage them
                logger.debug(f"Overlay shown on screen: {screen.name() if screen.name() else 'Unnamed Screen'}")

    def remove_overlay_reference(self, overlay_widget):
        """
        Callback slot for when an overlay closes itself (e.g., its exit_timer fires).
        Removes the overlay from the active set and schedules it for Qt's garbage collection.

        Args:
            overlay_widget (TransparentOverlay): The overlay widget that has closed.
        """
        if overlay_widget in self.overlays: 
            self.overlays.remove(overlay_widget) # Remove from the set of active overlays
            logger.debug("Overlay reference removed from active set.")
        overlay_widget.deleteLater() # Important to free Qt resources

    def stop_ongoing_alerts(self, silent=False):
        """
        Closes all currently active (visible) alert overlay windows.

        Args:
            silent (bool): If True, suppresses tray notifications and logging about 'no alerts to stop'.
        """
        if not self.overlays:
            if not silent: logger.info("No ongoing alerts to stop.")
            return
        
        num_stopped = len(self.overlays)
        if not silent: logger.info(f"Stopping {num_stopped} ongoing alert overlay(s)...")
        
        # Iterate over a copy of the set as closing an overlay modifies the set via remove_overlay_reference
        for overlay_widget in list(self.overlays): 
            try: # Disconnect the 'closed' signal to prevent remove_overlay_reference being called again
                overlay_widget.closed.disconnect(self.remove_overlay_reference) 
            except TypeError: # May happen if already disconnected or in process of closing
                pass 
            overlay_widget.close() # Close the widget window
            # self.overlays.discard(overlay_widget) # Should be handled by closed signal if connected, but as safety
            overlay_widget.deleteLater() # Ensure it's scheduled for deletion
        
        self.overlays.clear() # Explicitly clear the set after closing all

        if not silent and num_stopped > 0 and self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage("Alerts Stopped", f"{num_stopped} alert overlay(s) closed.", QSystemTrayIcon.Information, 2000)
            logger.info(f"{num_stopped} alert overlay(s) closed by user action.")
    
    def test_specific_alert(self, index):
        """
        Triggers a one-off test display of a configured alert from the alert table.
        
        Args:
            index (int): The index of the alert in the ConfigManager's alerts list to test.
        """
        if 0 <= index < len(self.config_manager.alerts):
            alert_config = self.config_manager.alerts[index]
            logger.info(f"Testing alert {index}: {alert_config.get(ALERT_KEY_TEXT)}")
            # Use a copy of the alert data to avoid any potential modification of the stored alert
            self.show_alert_overlay(alert_config.copy()) 
        else: 
            QMessageBox.warning(self, TITLE_ERROR, "Invalid alert index for testing.")
            logger.warning(f"Test specific alert called with invalid index: {index}")

    def send_test_alert_default(self): 
        """Triggers a one-off test display using the current default application settings."""
        logger.info("Sending test alert using current default settings.")
        s = self.config_manager.settings # Get current default settings
        # Construct a temporary alert_data dictionary from these defaults
        test_data = {
            ALERT_KEY_EXPANSION_TIME: s.get(SETTING_KEY_DEFAULT_EXPANSION_TIME), 
            ALERT_KEY_DURATION_MULTIPLIER: s.get(SETTING_KEY_DEFAULT_DURATION_MULTIPLIER),
            ALERT_KEY_START_SIZE: s.get(SETTING_KEY_DEFAULT_START_SIZE), 
            ALERT_KEY_TRANSPARENCY: s.get(SETTING_KEY_DEFAULT_TRANSPARENCY),
            ALERT_KEY_TEXT_TRANSPARENCY: s.get(SETTING_KEY_DEFAULT_TEXT_TRANSPARENCY), 
            ALERT_KEY_OVERLAY_COLOR: s.get(SETTING_KEY_DEFAULT_OVERLAY_COLOR),
            ALERT_KEY_TEXT_COLOR: s.get(SETTING_KEY_DEFAULT_TEXT_COLOR), 
            ALERT_KEY_DISPLAY: s.get(SETTING_KEY_DEFAULT_DISPLAY), 
            ALERT_KEY_TEXT: "Default Settings Test Alert" # Specific text for this test alert
        }
        self.show_alert_overlay(test_data)

# --- Main Execution Block ---

if __name__ == "__main__":
    # Enable High DPI scaling for better visuals on relevant displays
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Create the QApplication instance
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME_FULL) 
    app.setOrganizationName("YourOrg") # Optional: Used by QSettings, can help with config paths on some OS
    app.setApplicationVersion(APP_VERSION) 

    # Configure logging for the application
    logger.setLevel(logging.DEBUG) # Set default logging level for the application's logger
    
    # Console Handler setup (outputs logs to the console/terminal)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG) # Set level for this specific handler (can be different from logger's level)
    formatter = logging.Formatter(LOG_FORMAT) # Define log message format
    ch.setFormatter(formatter)
    logger.addHandler(ch) # Add the configured console handler to the logger
    
    logger.info(f"Application {APP_NAME_FULL} v{APP_VERSION} starting...")

    # Create and show the main window (which typically starts hidden and is accessed via the tray icon)
    window = MainWindow() 
    
    # Start the Qt event loop; sys.exit() ensures a clean exit code is returned
    sys.exit(app.exec_())

[end of main.py]
