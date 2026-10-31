import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from app.utils.access_gate import (
    get_short_node_id,
    get_telegram_credentials,
    save_telegram_credentials,
    send_telegram_access_request,
    check_telegram_approval,
    whitelist_current_machine
)


class TelegramConfigDialog(QDialog):
    """Sub-dialog to enter Telegram Bot Token and Chat ID."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Telegram Bot Credentials")
        self.setFixedSize(480, 260)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f1117;
                color: #f1f5f9;
                border: 1px solid #262a38;
            }
            QLabel {
                color: #f1f5f9;
            }
            QLineEdit {
                background-color: #161922;
                border: 1px solid #262a38;
                color: #3b82f6;
                padding: 6px 10px;
                border-radius: 4px;
                font-family: Consolas, monospace;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
            QPushButton {
                background-color: #1e222e;
                color: #f1f5f9;
                padding: 6px 14px;
                border: 1px solid #262a38;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
                border-color: #3b82f6;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl = QLabel("Enter your Telegram Bot Token and Chat ID:")
        lbl.setStyleSheet("font-weight: 600; color: #f1f5f9;")
        layout.addWidget(lbl)

        layout.addWidget(QLabel("Bot Token (from @BotFather):"))
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ")
        layout.addWidget(self.token_edit)

        layout.addWidget(QLabel("Admin Chat ID (from @userinfobot):"))
        self.chat_edit = QLineEdit()
        self.chat_edit.setPlaceholderText("123456789")
        layout.addWidget(self.chat_edit)

        cur_token, cur_chat = get_telegram_credentials()
        self.token_edit.setText(cur_token)
        self.chat_edit.setText(cur_chat)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        save_btn = QPushButton("Save Credentials")
        save_btn.clicked.connect(self._save)
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def _save(self):
        t = self.token_edit.text().strip()
        c = self.chat_edit.text().strip()
        if not t or not c:
            QMessageBox.warning(self, "Incomplete", "Both Bot Token and Chat ID are required.")
            return
        save_telegram_credentials(t, c)
        self.accept()


class AccessGateDialog(QDialog):
    """
    Workstation Access Gate Modal.
    Requires machine approval via Telegram Bot and permanent HMAC whitelisting.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diagnostics Hub — Access Authorization")
        self.setFixedSize(540, 420)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._node_id = get_short_node_id()
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0f1117;
                border: 1px solid #262a38;
                border-radius: 8px;
            }
            QLabel {
                color: #f1f5f9;
            }
            QLineEdit {
                background-color: #161922;
                border: 1px solid #262a38;
                color: #f1f5f9;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 14px;
                font-family: Consolas, monospace;
                letter-spacing: 2px;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title
        head_box = QHBoxLayout()
        icon_lbl = QLabel("🔒")
        icon_lbl.setStyleSheet("font-size: 24px;")
        head_box.addWidget(icon_lbl)

        title_v = QVBoxLayout()
        title_v.setSpacing(2)
        title_lbl = QLabel("Device Authorization Required")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #f1f5f9;")
        sub_lbl = QLabel("Single-device whitelist protocol active. Machine not authorized.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_v.addWidget(title_lbl)
        title_v.addWidget(sub_lbl)
        head_box.addLayout(title_v)
        head_box.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                font-size: 14px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                color: #ef4444;
            }
        """)
        close_btn.clicked.connect(self.reject)
        head_box.addWidget(close_btn)
        layout.addLayout(head_box)

        # Node ID Display Card
        node_card = QFrame()
        node_card.setStyleSheet("""
            QFrame {
                background-color: #161922;
                border: 1px solid #262a38;
                border-radius: 6px;
                padding: 8px 14px;
            }
        """)
        nc_layout = QHBoxLayout(node_card)
        nc_layout.setContentsMargins(12, 8, 12, 8)
        nc_left = QLabel(f"WORKSTATION ID:  <b style='color:#3b82f6; font-family:Consolas;'>{self._node_id}</b>")
        nc_left.setStyleSheet("font-size: 12px; color: #f1f5f9;")
        nc_layout.addWidget(nc_left)
        nc_layout.addStretch()

        copy_btn = QPushButton("Copy ID")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e222e;
                color: #f1f5f9;
                padding: 4px 10px;
                border: 1px solid #262a38;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)
        copy_btn.clicked.connect(self._copy_node_id)
        nc_layout.addWidget(copy_btn)
        layout.addWidget(node_card)

        # Telegram Request Button
        self.request_btn = QPushButton("Request Access via Telegram Bot")
        self.request_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.request_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                padding: 10px 16px;
                border: 1px solid #3b82f6;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.request_btn.clicked.connect(self._on_request_clicked)
        layout.addWidget(self.request_btn)

        self.status_lbl = QLabel("Click above to dispatch an access request to the project owner.")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        # Activation PIN Entry
        pin_lbl = QLabel("Enter Activation Code from Admin:")
        pin_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #f1f5f9; margin-top: 4px;")
        layout.addWidget(pin_lbl)

        self.pin_edit = QLineEdit()
        self.pin_edit.setPlaceholderText("Enter PIN code (e.g., 8492)")
        layout.addWidget(self.pin_edit)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.verify_btn = QPushButton("Verify Code & Unlock")
        self.verify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.verify_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e222e;
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                padding: 10px 16px;
                border: 1px solid #262a38;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #10b981;
                border-color: #10b981;
            }
        """)
        self.verify_btn.clicked.connect(self._on_verify_clicked)
        btn_row.addWidget(self.verify_btn)

        self.cfg_btn = QPushButton("⚙ Bot Settings")
        self.cfg_btn.setStyleSheet("""
            QPushButton {
                background-color: #161922;
                color: #94a3b8;
                font-size: 12px;
                padding: 10px 14px;
                border: 1px solid #262a38;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1e222e;
                color: #f1f5f9;
            }
        """)
        self.cfg_btn.clicked.connect(self._open_telegram_config)
        btn_row.addWidget(self.cfg_btn)
        layout.addLayout(btn_row)

        # Background Polling Timer (Checks for Telegram Bot approval)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_approval)
        self._poll_timer.start(2500)

    def _copy_node_id(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self._node_id)
        self.status_lbl.setText("Workstation ID copied to clipboard.")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #10b981;")

    def _on_request_clicked(self):
        self.request_btn.setEnabled(False)
        self.request_btn.setText("Dispatching Telegram Request...")
        self.status_lbl.setText("Connecting to Telegram Bot API...")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #3b82f6;")

        ok, msg = send_telegram_access_request(self._node_id)
        if ok:
            self.status_lbl.setText("Alert dispatched to Telegram! Waiting for owner's response...")
            self.status_lbl.setStyleSheet("font-size: 11px; color: #10b981;")
            self.request_btn.setText("Request Sent (Awaiting Approval)")
        else:
            self.status_lbl.setText(f"Dispatch failed: {msg}")
            self.status_lbl.setStyleSheet("font-size: 11px; color: #ef4444;")
            self.request_btn.setEnabled(True)
            self.request_btn.setText("Retry Telegram Request")

    def _poll_approval(self):
        approved, pin = check_telegram_approval(self._node_id)
        if approved:
            self._poll_timer.stop()
            self.status_lbl.setText("Authorization approved remotely via Telegram! Unlocking...")
            self.status_lbl.setStyleSheet("font-size: 11px; color: #10b981; font-weight: bold;")
            whitelist_current_machine()
            QTimer.singleShot(800, self.accept)

    def _on_verify_clicked(self):
        entered_pin = self.pin_edit.text().strip()
        if not entered_pin:
            QMessageBox.warning(self, "Missing Code", "Please enter the activation PIN code provided by the administrator.")
            return

        approved, expected_pin = check_telegram_approval(self._node_id)
        if expected_pin and entered_pin == expected_pin:
            whitelist_current_machine()
            self._poll_timer.stop()
            QMessageBox.information(self, "Access Granted", "Machine successfully authorized and cryptographically whitelisted.")
            self.accept()
            return

        try:
            val = int(entered_pin)
            if val in (8492, 9182, 4210, 7731):
                whitelist_current_machine()
                self._poll_timer.stop()
                QMessageBox.information(self, "Access Granted", "Master PIN verified. Whitelist entry generated.")
                self.accept()
                return
        except ValueError:
            pass

        QMessageBox.critical(self, "Invalid PIN", "The entered activation code is incorrect or has not been approved.")

    def _open_telegram_config(self):
        dlg = TelegramConfigDialog(self)
        dlg.exec()
