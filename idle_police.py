import sys
import os
import ctypes
from PyQt5.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QAction, QInputDialog
)
from PyQt5.QtCore import QTimer, Qt, QUrl
from PyQt5.QtGui import QColor, QIcon, QPixmap, QPainter
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QMediaPlaylist

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

def get_idle_time_seconds():
    """Returns the system-wide idle time in seconds using Windows API."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    return 0

class PoliceOverlay(QWidget):
    def __init__(self, sound_file):
        super().__init__()
        self.sound_file = sound_file
        self.is_red = True
        
        # Borderless, Always On Top, No Taskbar Entry
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        # 65% opacity overlay so desktop remains partially visible beneath
        self.setWindowOpacity(0.65)
        
        # Flashing color timer
        self.flash_timer = QTimer(self)
        self.flash_timer.timeout.connect(self.toggle_color)

        # MP3 Audio player setup using PyQt5 QtMultimedia
        self.player = QMediaPlayer()
        self.playlist = QMediaPlaylist()
        if os.path.exists(self.sound_file):
            url = QUrl.fromLocalFile(os.path.abspath(self.sound_file))
            self.playlist.addMedia(QMediaContent(url))
            self.playlist.setPlaybackMode(QMediaPlaylist.Loop)
            self.player.setPlaylist(self.playlist)

    def toggle_color(self):
        self.is_red = not self.is_red
        color = "rgba(255, 0, 0, 220)" if self.is_red else "rgba(0, 0, 255, 220)"
        self.setStyleSheet(f"background-color: {color};")

    def start_siren(self):
        # Expand across all connected displays
        desktop = QApplication.desktop()
        self.setGeometry(desktop.geometry())
        self.showFullScreen()
        
        # Flash every 200ms
        self.flash_timer.start(200)
        
        # Play siren MP3 loop
        if os.path.exists(self.sound_file):
            self.player.play()

    def stop_siren(self):
        self.flash_timer.stop()
        self.hide()
        self.player.stop()

class IdlePoliceApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.idle_threshold_seconds = 30  # Default idle time
        self.is_active = False
        
        # Locate sound file (handles both standalone script and PyInstaller temp dir)
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        self.sound_file = os.path.join(base_path, "siren.mp3")
        
        self.overlay = PoliceOverlay(self.sound_file)
        self.setup_tray()
        
        # Check idle state twice per second
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_idle)
        self.check_timer.start(500)

    def create_tray_pixmap(self):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QColor(255, 0, 0))
        painter.drawRect(0, 0, 16, 32)
        painter.setBrush(QColor(0, 0, 255))
        painter.drawRect(16, 0, 16, 32)
        painter.end()
        return QIcon(pixmap)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self.create_tray_pixmap(), self.app)
        self.update_tray_tooltip()
        
        menu = QMenu()
        
        # Time options sub-menu
        time_menu = menu.addMenu("Set Idle Time")
        options = [
            ("15 Seconds", 15), 
            ("30 Seconds", 30), 
            ("1 Minute", 60), 
            ("3 Minutes", 180), 
            ("5 Minutes", 300)
        ]
        
        for label, seconds in options:
            action = QAction(label, menu)
            action.triggered.connect(lambda _, s=seconds: self.set_timeout(s))
            time_menu.addAction(action)
            
        custom_action = QAction("Custom Seconds...", menu)
        custom_action.triggered.connect(self.set_custom_timeout)
        time_menu.addAction(custom_action)
        
        menu.addSeparator()
        
        exit_action = QAction("Exit", menu)
        exit_action.triggered.connect(self.app.quit)
        menu.addAction(exit_action)
        
        self.tray.setContextMenu(menu)
        self.tray.show()

    def update_tray_tooltip(self):
        self.tray.setToolTip(f"Idle Police Siren (Timeout: {self.idle_threshold_seconds}s)")

    def set_timeout(self, seconds):
        self.idle_threshold_seconds = seconds
        self.update_tray_tooltip()

    def set_custom_timeout(self):
        sec, ok = QInputDialog.getInt(
            None, "Custom Timeout", "Enter idle threshold (seconds):", 
            self.idle_threshold_seconds, 5, 3600
        )
        if ok:
            self.set_timeout(sec)

    def check_idle(self):
        idle_time = get_idle_time_seconds()
        
        if not self.is_active:
            if idle_time >= self.idle_threshold_seconds:
                self.is_active = True
                self.overlay.start_siren()
        else:
            # Any mouse move or key press resets idle_time back near 0
            if idle_time < 0.5:
                self.is_active = False
                self.overlay.stop_siren()

    def run(self):
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    app = IdlePoliceApp()
    app.run()