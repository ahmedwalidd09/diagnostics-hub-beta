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
                background-color: #07080c;
                color: #f0f6fc;
                border: 1px solid #1a2130;
            }
            QLabel {
                color: #f0f6fc;
            }
            QLineEdit {
                background-color: #0d1017;
                border: 1px solid #1a2130;
                color: #00d2ff;
                padding: 6px 10px;
                border-radius: 4px;
                font-family: Consolas, monospace;
            }
            QLineEdit:focus {
                border: 1px solid #00a8ff;
            }
            QPushButton {
                background-color: #1a2130;
                color: #f0f6fc;
                padding: 6px 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00a8ff;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl = QLabel("Enter your Telegram Bot Token and Chat ID:")
        lbl.setStyleSheet("font-weight: bold; color: #00d2ff;")
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
    Cyber Stealth Access Gate Modal.
    Requires machine approval via Telegram Bot and permanent HMAC whitelisting.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚡ Diagnostics Hub // Access Gate")
        self.setFixedSize(540, 420)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._node_id = get_short_node_id()
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #07080c;
                border: 2px solid #1a273a;
                border-top: 3px solid qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff2a51, stop:0.5 #00d2ff, stop:1 #00a8ff);
                border-radius: 8px;
            }
            QLabel {
                color: #f0f6fc;
            }
            QLineEdit {
                background-color: #0d1017;
                border: 1px solid #1a2130;
                color: #00d2ff;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 14px;
                font-family: Consolas, monospace;
                letter-spacing: 2px;
            }
            QLineEdit:focus {
                border: 1px solid #00d2ff;
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
        title_lbl = QLabel("RESTRICTED BETA // ACCESS REQUIRED")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #00d2ff; letter-spacing: 0.8px;")
        sub_lbl = QLabel("Single-device whitelist protocol active. Machine not authorized.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #828d9e;")
        title_v.addWidget(title_lbl)
        title_v.addWidget(sub_lbl)
        head_box.addLayout(title_v)
        head_box.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #828d9e;
                font-size: 14px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                color: #ff2a51;
            }
        """)
        close_btn.clicked.connect(self.reject)
        head_box.addWidget(close_btn)
        layout.addLayout(head_box)

        # Node ID Display Card
        node_card = QFrame()
        node_card.setStyleSheet("""
            QFrame {
                background-color: #0d1017;
                border: 1px solid #1a2130;
                border-radius: 6px;
                padding: 8px 14px;
            }
        """)
        nc_layout = QHBoxLayout(node_card)
        nc_layout.setContentsMargins(12, 8, 12, 8)
        nc_left = QLabel(f"YOUR NODE ID:  <b style='color:#00d2ff; font-family:Consolas;'>{self._node_id}</b>")
        nc_left.setStyleSheet("font-size: 12px; color: #f0f6fc;")
        nc_layout.addWidget(nc_left)
        nc_layout.addStretch()

        copy_btn = QPushButton("📋 Copy ID")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a2130;
                color: #f0f6fc;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #00a8ff;
                color: #ffffff;
            }
        """)
        copy_btn.clicked.connect(self._copy_node_id)
        nc_layout.addWidget(copy_btn)
        layout.addWidget(node_card)

        # Telegram Request Button
        self.request_btn = QPushButton("📡 Request Access via Telegram Bot")
        self.request_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.request_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0052cc, stop:1 #00a8ff);
                color: #ffffff;
                font-weight: 800;
                font-size: 12px;
                letter-spacing: 0.5px;
                padding: 10px 16px;
                border: 1px solid #00d2ff;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0066ff, stop:1 #33c2ff);
            }
        """)
        self.request_btn.clicked.connect(self._on_request_clicked)
        layout.addWidget(self.request_btn)

        self.status_lbl = QLabel("Click above to dispatch an access request to the project owner.")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #828d9e;")
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        # Activation PIN Entry
        pin_lbl = QLabel("Enter Activation Code from Admin:")
        pin_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #f0f6fc; margin-top: 4px;")
        layout.addWidget(pin_lbl)

        self.pin_edit = QLineEdit()
        self.pin_edit.setPlaceholderText("Enter PIN code (e.g., 8492)")
        layout.addWidget(self.pin_edit)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.verify_btn = QPushButton("⚡ Verify Code & Unlock")
        self.verify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.verify_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #b30024, stop:1 #ff2a51);
                color: #ffffff;
                font-weight: 800;
                font-size: 12px;
                padding: 10px 16px;
                border: 1px solid #ff4757;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #cc0029, stop:1 #ff4757);
            }
        """)
        self.verify_btn.clicked.connect(self._on_verify_clicked)
        btn_row.addWidget(self.verify_btn)

        self.cfg_btn = QPushButton("⚙️ Config Bot")
        self.cfg_btn.setStyleSheet("""
            QPushButton {
                background-color: #141824;
                color: #828d9e;
                padding: 10px 12px;
                border: 1px solid #1a2130;
                border-radius: 6px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #f0f6fc;
                border-color: #00a8ff;
            }
        """)
        self.cfg_btn.clicked.connect(self._open_telegram_config)
        btn_row.addWidget(self.cfg_btn)
        layout.addLayout(btn_row)

    def _copy_node_id(self):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self._node_id)
            self.status_lbl.setText("✓ Node ID copied to clipboard.")
            self.status_lbl.setStyleSheet("font-size: 11px; color: #00e676;")

    def _open_telegram_config(self):
        dlg = TelegramConfigDialog(self)
        if dlg.exec():
            self.status_lbl.setText("Telegram credentials updated successfully.")
            self.status_lbl.setStyleSheet("font-size: 11px; color: #00e676;")

    def _on_request_clicked(self):
        bot_token, chat_id = get_telegram_credentials()
        if not bot_token or not chat_id:
            reply = QMessageBox.question(
                self,
                "Telegram Credentials Needed",
                "Telegram Bot Token and Admin Chat ID are not configured yet.\n\nWould you like to configure them now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._open_telegram_config()
            return

        self.request_btn.setEnabled(False)
        self.status_lbl.setText("Dispatching request to Telegram bot...")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #00d2ff;")
        QApplication.processEvents()

        ok, msg = send_telegram_access_request(bot_token, chat_id)
        self.request_btn.setEnabled(True)
        if ok:
            self.status_lbl.setText("✓ Request sent to admin! Check your Telegram or wait for your code.")
            self.status_lbl.setStyleSheet("font-size: 11px; color: #00e676; font-weight: bold;")
        else:
            self.status_lbl.setText(f"✕ Request failed: {msg}")
            self.status_lbl.setStyleSheet("font-size: 11px; color: #ff2a51;")

    def _on_verify_clicked(self):
        bot_token, chat_id = get_telegram_credentials()
        entered = self.pin_edit.text().strip()

        if not entered:
            # Attempt auto-check via Telegram updates
            self.status_lbl.setText("Checking Telegram updates for owner approval...")
            self.status_lbl.setStyleSheet("font-size: 11px; color: #00d2ff;")
            QApplication.processEvents()

            ok, msg = check_telegram_approval(bot_token, chat_id, entered_pin="")
            if ok:
                QMessageBox.information(self, "Access Granted", "Machine successfully whitelisted and unlocked!")
                self.accept()
                return
            else:
                self.status_lbl.setText(msg)
                self.status_lbl.setStyleSheet("font-size: 11px; color: #ff9f1a;")
                return

        # Explicit code validation against Telegram updates
        self.status_lbl.setText(f"Validating PIN '{entered}' with Telegram...")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #00d2ff;")
        QApplication.processEvents()

        ok, msg = check_telegram_approval(bot_token, chat_id, entered_pin=entered)
        if ok:
            QMessageBox.information(self, "Access Granted", "Machine successfully whitelisted! This device is permanently authorized.")
            self.accept()
        else:
            self.status_lbl.setText(f"✕ {msg}")
            self.status_lbl.setStyleSheet("font-size: 11px; color: #ff2a51; font-weight: bold;")
