import sys
import json
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, 
                          QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, 
                          QCheckBox, QFileDialog, QMessageBox, QFrame,
                          QTextEdit)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QIcon, QFont
import psutil
from datetime import datetime
import signal
import os
import threading
from PyQt6.QtWidgets import QScrollBar
import winreg

# Constants
CONFIG_FILE = Path("config.json")
PID_FILE = Path("monitor.pid")
LOG_FILE = Path("hikibridge.log")

@dataclass
class AppConfig:
    api_endpoint: str
    api_key: str
    folder_path: str
    auto_start: bool
    windows_startup: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        return cls(
            api_endpoint=data.get('api_endpoint', ''),
            api_key=data.get('api_key', ''),
            folder_path=data.get('folder_path', ''),
            auto_start=data.get('auto_start', False),
            windows_startup=data.get('windows_startup', False)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'api_endpoint': self.api_endpoint,
            'api_key': self.api_key,
            'folder_path': self.folder_path,
            'auto_start': self.auto_start,
            'windows_startup': self.windows_startup
        }

class Logger:
    def __init__(self):
        self.logger = logging.getLogger('HikiBridge')
        self.logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(file_handler)

    def info(self, message: str):
        self.logger.info(message)

    def error(self, message: str):
        self.logger.error(message)

    def warning(self, message: str):
        self.logger.warning(message)

class ProcessManager:
    def __init__(self, logger: Logger):
        self.process: Optional[subprocess.Popen] = None
        self.logger = logger
        self.pid_file = PID_FILE
        self.output_callback = None
        self.output_thread = None

    def start_process(self, config: AppConfig, output_callback=None) -> bool:
        if self.is_running():
            self.logger.warning("Process already running")
            return False

        try:
            self.output_callback = output_callback
            cmd = [
                sys.executable,
                'monitor.py',
                config.folder_path,
                config.api_endpoint,
                config.api_key
            ]

            # Run process in background with output capture
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Start output reader thread
            self.output_thread = threading.Thread(
                target=self._read_output,
                daemon=True
            )
            self.output_thread.start()

            # Write PID file
            with open(self.pid_file, 'w') as f:
                f.write(str(self.process.pid))

            self.logger.info(f"Started monitoring process with PID {self.process.pid}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start process: {e}")
            return False

    def _read_output(self):
        """Read output from the process and send it to the callback"""
        try:
            for line in iter(self.process.stdout.readline, ''):
                if self.output_callback:
                    self.output_callback(line.strip())
        except Exception as e:
            self.logger.error(f"Error reading process output: {e}")

    def stop_process(self) -> bool:
        if not self.is_running():
            return True

        try:
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)])
            else:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

            self.process = None
            if self.pid_file.exists():
                self.pid_file.unlink()
            
            self.logger.info("Monitoring process stopped")
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop process: {e}")
            return False

    def is_running(self) -> bool:
        if self.process:
            return self.process.poll() is None
        return False

class ConfigManager:
    def __init__(self, logger: Logger):
        self.config_file = CONFIG_FILE
        self.logger = logger

    def load(self) -> AppConfig:
        try:
            if self.config_file.exists():
                with open(self.config_file) as f:
                    data = json.load(f)
                return AppConfig.from_dict(data)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
        
        return AppConfig('', '', '', False)

    def save(self, config: AppConfig) -> bool:
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config.to_dict(), f)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            return False

class StartupManager:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.app_name = "HikiBridge"
        
        # Get the full path to the executable or script
        if getattr(sys, 'frozen', False):
            self.app_path = f'"{sys.executable}"'
        else:
            self.app_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'

        # Set platform-specific startup path
        if sys.platform == 'win32':
            self.key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        else:
            # Linux startup file path
            self.startup_file = Path.home() / '.config/autostart/hikibridge.desktop'

    def enable_startup(self) -> bool:
        if sys.platform == 'win32':
            return self._enable_windows_startup()
        else:
            return self._enable_linux_startup()

    def disable_startup(self) -> bool:
        if sys.platform == 'win32':
            return self._disable_windows_startup()
        else:
            return self._disable_linux_startup()

    def is_enabled(self) -> bool:
        if sys.platform == 'win32':
            return self._is_windows_enabled()
        else:
            return self._is_linux_enabled()

    # Windows-specific methods
    def _enable_windows_startup(self) -> bool:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, self.app_path)
            winreg.CloseKey(key)
            self.logger.info("Added to Windows startup")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add to Windows startup: {e}")
            return False

    def _disable_windows_startup(self) -> bool:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key_path, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, self.app_name)
            winreg.CloseKey(key)
            self.logger.info("Removed from Windows startup")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove from Windows startup: {e}")
            return False

    def _is_windows_enabled(self) -> bool:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key_path, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, self.app_name)
            winreg.CloseKey(key)
            return True
        except:
            return False

    # Linux-specific methods
    def _enable_linux_startup(self) -> bool:
        try:
            os.makedirs(self.startup_file.parent, exist_ok=True)
            desktop_entry = f"""[Desktop Entry]
Name={self.app_name}
Exec={self.app_path}
Type=Application
X-GNOME-Autostart-enabled=true"""
            
            with open(self.startup_file, 'w') as f:
                f.write(desktop_entry)
            
            # Make the .desktop file executable
            os.chmod(self.startup_file, 0o755)
            self.logger.info("Added to Linux startup")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add to Linux startup: {e}")
            return False

    def _disable_linux_startup(self) -> bool:
        try:
            if self.startup_file.exists():
                self.startup_file.unlink()
            self.logger.info("Removed from Linux startup")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove from Linux startup: {e}")
            return False

    def _is_linux_enabled(self) -> bool:
        return self.startup_file.exists()

class HikiBridgeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = Logger()
        self.process_manager = ProcessManager(self.logger)
        self.config_manager = ConfigManager(self.logger)
        self.startup_manager = StartupManager(self.logger)
        
        self.init_ui()
        self.load_config()
        
        # Start monitoring if auto-start is enabled
        if self.auto_start.isChecked():
            self.start_monitoring()

    def init_ui(self):
        self.setWindowTitle('HikiBridge')
        self.setFixedSize(600, 400)

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Create input fields
        self.api_endpoint = QLineEdit()
        self.api_endpoint.setPlaceholderText('API Endpoint')
        layout.addWidget(QLabel('API Endpoint:'))
        layout.addWidget(self.api_endpoint)

        self.api_key = QLineEdit()
        self.api_key.setPlaceholderText('API Key')
        layout.addWidget(QLabel('API Key:'))
        layout.addWidget(self.api_key)

        # Folder selection
        folder_layout = QHBoxLayout()
        self.folder_path = QLineEdit()
        self.folder_path.setPlaceholderText('Select Folder to Monitor')
        folder_layout.addWidget(self.folder_path)
        
        browse_btn = QPushButton('Browse')
        browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(browse_btn)
        
        layout.addWidget(QLabel('Folder Path:'))
        layout.addLayout(folder_layout)

        # Auto-start checkbox
        self.auto_start = QCheckBox('Auto-start monitoring')
        self.auto_start.stateChanged.connect(self.auto_start_changed)
        layout.addWidget(self.auto_start)

        # Add Windows startup checkbox and verify button in a horizontal layout
        startup_layout = QHBoxLayout()
        
        self.windows_startup = QCheckBox('Start with Windows')
        self.windows_startup.stateChanged.connect(self.windows_startup_changed)
        startup_layout.addWidget(self.windows_startup)
        
        verify_btn = QPushButton('Verify Startup')
        verify_btn.clicked.connect(self.verify_startup)
        startup_layout.addWidget(verify_btn)
        
        startup_layout.addStretch()  # This pushes the elements to the left
        layout.addLayout(startup_layout)

        # Status display
        self.status_display = QTextEdit()
        self.status_display.setReadOnly(True)
        layout.addWidget(QLabel('Status:'))
        layout.addWidget(self.status_display)

        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton('Start Monitoring')
        self.start_btn.clicked.connect(self.start_monitoring)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton('Stop Monitoring')
        self.stop_btn.clicked.connect(self.stop_monitoring)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        # Add clear console button
        self.clear_btn = QPushButton('Clear Console')
        self.clear_btn.clicked.connect(self.clear_console)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)

    def load_config(self):
        config = self.config_manager.load()
        self.api_endpoint.setText(config.api_endpoint)
        self.api_key.setText(config.api_key)
        self.folder_path.setText(config.folder_path)
        self.auto_start.setChecked(config.auto_start)
        
        # Silently set Windows startup checkbox based on actual registry state
        self.windows_startup.blockSignals(True)  # Prevent triggering the change event
        self.windows_startup.setChecked(self.startup_manager.is_enabled())
        self.windows_startup.blockSignals(False)  # Re-enable signals

    def save_config(self):
        config = AppConfig(
            api_endpoint=self.api_endpoint.text(),
            api_key=self.api_key.text(),
            folder_path=self.folder_path.text(),
            auto_start=self.auto_start.isChecked(),
            windows_startup=self.windows_startup.isChecked()
        )
        self.config_manager.save(config)

    def windows_startup_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            if self.startup_manager.enable_startup():
                if self.verify_startup():
                    self.status_display.append("Successfully added to Windows startup")
                else:
                    self.windows_startup.setChecked(False)
                    QMessageBox.warning(self, 'Error', 
                                      'Failed to verify Windows startup configuration')
            else:
                self.windows_startup.setChecked(False)
                QMessageBox.warning(self, 'Error', 
                                  'Failed to add application to Windows startup')
        else:
            if self.startup_manager.disable_startup():
                if not self.verify_startup():
                    self.status_display.append("Successfully removed from Windows startup")
                else:
                    self.windows_startup.setChecked(True)
                    QMessageBox.warning(self, 'Error', 
                                      'Failed to verify Windows startup removal')
            else:
                self.windows_startup.setChecked(True)
                QMessageBox.warning(self, 'Error', 
                                  'Failed to remove application from Windows startup')

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder to Monitor')
        if folder:
            self.folder_path.setText(folder)

    def start_monitoring(self):
        if not self.validate_inputs():
            return

        self.save_config()
        config = AppConfig(
            api_endpoint=self.api_endpoint.text(),
            api_key=self.api_key.text(),
            folder_path=self.folder_path.text(),
            auto_start=self.auto_start.isChecked()
        )

        if self.process_manager.start_process(config, self.update_status):
            self.status_display.append("Monitoring started successfully")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:
            self.status_display.append("Failed to start monitoring")

    def stop_monitoring(self):
        if self.process_manager.stop_process():
            self.status_display.append("Monitoring stopped")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        else:
            self.status_display.append("Failed to stop monitoring")

    def validate_inputs(self) -> bool:
        if not self.api_endpoint.text():
            QMessageBox.warning(self, 'Validation Error', 'API Endpoint is required')
            return False
        if not self.api_key.text():
            QMessageBox.warning(self, 'Validation Error', 'API Key is required')
            return False
        if not self.folder_path.text():
            QMessageBox.warning(self, 'Validation Error', 'Folder Path is required')
            return False
        if not Path(self.folder_path.text()).exists():
            QMessageBox.warning(self, 'Validation Error', 'Selected folder does not exist')
            return False
        return True

    def closeEvent(self, event):
        """Override close event to show confirmation dialog"""
        if self.process_manager.is_running():
            reply = QMessageBox.question(
                self,
                'Confirm Exit',
                'Monitoring is currently running. Closing the application will stop the monitoring process.\n\nDo you want to exit?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.process_manager.stop_process()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def update_status(self, message: str):
        """Update the status display with new messages"""
        self.status_display.append(message)
        # Scroll to the bottom
        self.status_display.verticalScrollBar().setValue(
            self.status_display.verticalScrollBar().maximum()
        )

    def verify_startup(self):
        try:
            # Check registry
            is_in_registry = self.startup_manager.is_enabled()
            
            # Get the actual registry value for comparison
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                self.startup_manager.key_path, 
                                0, 
                                winreg.KEY_READ)
            reg_value, _ = winreg.QueryValueEx(key, self.startup_manager.app_name)
            winreg.CloseKey(key)
            
            # Compare with our expected path
            expected_path = self.startup_manager.app_path
            path_matches = reg_value == expected_path
            
            if is_in_registry and path_matches:
                self.status_display.append("✓ Windows startup is correctly configured")
                self.status_display.append(f"Startup path: {reg_value}")
                return True
            else:
                if not is_in_registry:
                    self.status_display.append("✗ Application is not in Windows startup")
                elif not path_matches:
                    self.status_display.append("✗ Startup path mismatch:")
                    self.status_display.append(f"Expected: {expected_path}")
                    self.status_display.append(f"Found: {reg_value}")
                return False
                
        except Exception as e:
            self.status_display.append(f"✗ Error verifying startup: {str(e)}")
            return False

    def auto_start_changed(self, state):
        """Save config whenever auto-start is toggled"""
        self.save_config()
        is_enabled = "enabled" if state == Qt.CheckState.Checked.value else "disabled"
        self.status_display.append(f"Auto-start {is_enabled} and saved to config")

    def clear_console(self):
        """Clear the status display"""
        self.status_display.clear()

def main():
    app = QApplication(sys.argv)
    window = HikiBridgeApp()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
