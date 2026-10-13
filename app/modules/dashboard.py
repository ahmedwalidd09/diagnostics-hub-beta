from collections import deque
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QProgressBar, QScrollArea, QPushButton
)
from PyQt6.QtCore import Qt
from app.widgets.gauge_widget import GaugeWidget
from app.widgets.sparkline_widget import SparklineWidget
from app.constants import (
    COLOR_BG_CARD,
    COLOR_BORDER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_GAUGE_HEALTHY,
    COLOR_GAUGE_WARNING,
    COLOR_GAUGE_CRITICAL
)


def format_bytes_speed(kbs: float) -> str:
    """Format KB/s into human readable speed string."""
    if kbs >= 1024.0:
        return f"{kbs / 1024.0:.2f} MB/s"
    return f"{kbs:.1f} KB/s"


class DashboardPage(QWidget):
    """
    Main System Overview Dashboard.
    Visualizes CPU, RAM, Disk, GPU, Network, Battery, and host vitals.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MainContent")
        self._core_bars = []
        self._drive_widgets = []
        self._ram_history = deque(maxlen=60)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QGridLayout(container)
        grid.setSpacing(16)

        # -------------------------------------------------------------
        # ROW 0: Cyber Hero Banner (System Node Status + RAM Flush)
        # -------------------------------------------------------------
        self.hero_card = QFrame()
        self.hero_card.setObjectName("HeroBanner")
        self.hero_card.setStyleSheet("""
            QFrame#HeroBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #070a12, stop:0.5 #0d121f, stop:1 #070a12);
                border: 1px solid #1a273a;
                border-top: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff2a51, stop:0.5 #00d2ff, stop:1 #00a8ff);
                border-radius: 8px;
            }
        """)
        hero_layout = QHBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(18, 14, 18, 14)
        hero_layout.setSpacing(16)

        hero_left = QVBoxLayout()
        hero_left.setSpacing(4)
        self.hero_title = QLabel("⚡ SYSTEM NODE // ONLINE")
        self.hero_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #00d2ff; letter-spacing: 0.8px;")
        hero_left.addWidget(self.hero_title)

        self.hero_sub = QLabel("Kernel Vitals Synchronized • Real-Time Hardware Telemetry Active")
        self.hero_sub.setStyleSheet("font-size: 11px; color: #828d9e; font-weight: 500;")
        hero_left.addWidget(self.hero_sub)
        hero_layout.addLayout(hero_left)
        hero_layout.addStretch()

        self.hero_flush_btn = QPushButton("⚡ INSTANT RAM FLUSH")
        self.hero_flush_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hero_flush_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0052cc, stop:1 #00a8ff);
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                letter-spacing: 0.5px;
                padding: 8px 18px;
                border: 1px solid #00d2ff;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0066ff, stop:1 #33c2ff);
                border: 1px solid #ffffff;
            }
            QPushButton:pressed {
                background: #003d99;
            }
        """)
        self.hero_flush_btn.clicked.connect(self._on_hero_flush_clicked)
        hero_layout.addWidget(self.hero_flush_btn)

        grid.addWidget(self.hero_card, 0, 0, 1, 3)

        # -------------------------------------------------------------
        # ROW 1: 3 Primary Vitals Cards (CPU, RAM, Storage)
        # -------------------------------------------------------------
        # 1. CPU Card
        self.cpu_card = self._create_card("// PROCESSOR (CPU)")
        cpu_layout = QVBoxLayout(self.cpu_card)
        cpu_layout.setContentsMargins(16, 16, 16, 16)
        cpu_layout.setSpacing(10)

        cpu_title_lbl = QLabel("// PROCESSOR (CPU)")
        cpu_title_lbl.setObjectName("CardTitle")
        cpu_layout.addWidget(cpu_title_lbl)

        cpu_top = QHBoxLayout()
        self.cpu_gauge = GaugeWidget(title="Total Load", unit="%", min_value=0, max_value=100)
        cpu_top.addWidget(self.cpu_gauge, alignment=Qt.AlignmentFlag.AlignCenter)

        cpu_details = QVBoxLayout()
        cpu_details.setSpacing(4)
        self.cpu_model_lbl = QLabel("Detecting CPU...")
        self.cpu_model_lbl.setWordWrap(True)
        self.cpu_model_lbl.setStyleSheet("font-weight: 600; color: #ffffff;")
        cpu_details.addWidget(self.cpu_model_lbl)

        self.cpu_freq_lbl = QLabel("Clock: -- MHz")
        self.cpu_freq_lbl.setObjectName("SubText")
        cpu_details.addWidget(self.cpu_freq_lbl)

        self.cpu_temp_lbl = QLabel("Temp: Checking...")
        self.cpu_temp_lbl.setObjectName("SubText")
        cpu_details.addWidget(self.cpu_temp_lbl)

        cpu_top.addLayout(cpu_details)
        cpu_layout.addLayout(cpu_top)

        # Core Usage Sub-panel
        self.cores_container = QVBoxLayout()
        self.cores_container.setSpacing(3)
        core_header = QLabel("Per-Core Utilization:")
        core_header.setObjectName("SubText")
        self.cores_container.addWidget(core_header)
        cpu_layout.addLayout(self.cores_container)
        grid.addWidget(self.cpu_card, 1, 0)

        # 2. RAM Card
        self.ram_card = self._create_card("// SYSTEM MEMORY (RAM)")
        ram_layout = QVBoxLayout(self.ram_card)
        ram_layout.setContentsMargins(16, 16, 16, 16)
        ram_layout.setSpacing(10)

        ram_title_lbl = QLabel("// SYSTEM MEMORY (RAM)")
        ram_title_lbl.setObjectName("CardTitle")
        ram_layout.addWidget(ram_title_lbl)

        ram_top = QHBoxLayout()
        self.ram_gauge = GaugeWidget(title="Used", unit="%", min_value=0, max_value=100)
        ram_top.addWidget(self.ram_gauge, alignment=Qt.AlignmentFlag.AlignCenter)

        ram_details = QVBoxLayout()
        ram_details.setSpacing(4)
        self.ram_breakdown_lbl = QLabel("Memory: -- GB / -- GB")
        self.ram_breakdown_lbl.setStyleSheet("font-weight: 600; color: #ffffff;")
        ram_details.addWidget(self.ram_breakdown_lbl)

        self.ram_avail_lbl = QLabel("Available: -- GB")
        self.ram_avail_lbl.setObjectName("SubText")
        ram_details.addWidget(self.ram_avail_lbl)

        self.ram_swap_lbl = QLabel("Pagefile / Swap: -- %")
        self.ram_swap_lbl.setObjectName("SubText")
        ram_details.addWidget(self.ram_swap_lbl)

        ram_top.addLayout(ram_details)
        ram_layout.addLayout(ram_top)

        # Sparkline Graph (60 seconds history)
        spark_title = QLabel("60s RAM History:")
        spark_title.setObjectName("SubText")
        ram_layout.addWidget(spark_title)
        self.ram_sparkline = SparklineWidget(max_points=60, line_color="#00a8ff")
        ram_layout.addWidget(self.ram_sparkline)
        grid.addWidget(self.ram_card, 1, 1)

        # 3. Storage / Disk Card
        self.disk_card = self._create_card("// STORAGE DRIVES")
        self.disk_layout = QVBoxLayout(self.disk_card)
        self.disk_layout.setContentsMargins(16, 16, 16, 16)
        self.disk_layout.setSpacing(8)

        disk_title_lbl = QLabel("// STORAGE DRIVES")
        disk_title_lbl.setObjectName("CardTitle")
        self.disk_layout.addWidget(disk_title_lbl)

        self.disk_io_lbl = QLabel("I/O Activity: Read 0.0 MB/s | Write 0.0 MB/s")
        self.disk_io_lbl.setObjectName("SubText")
        self.disk_layout.addWidget(self.disk_io_lbl)

        self.drives_container = QVBoxLayout()
        self.drives_container.setSpacing(8)
        self.disk_layout.addLayout(self.drives_container)
        self.disk_layout.addStretch()
        grid.addWidget(self.disk_card, 1, 2)

        # -------------------------------------------------------------
        # ROW 2: GPU, Network, and Battery Cards
        # -------------------------------------------------------------
        # 4. GPU Card
        self.gpu_card = self._create_card("// GRAPHICS (GPU)")
        gpu_layout = QVBoxLayout(self.gpu_card)
        gpu_layout.setContentsMargins(16, 16, 16, 16)
        gpu_layout.setSpacing(6)

        gpu_title = QLabel("// GRAPHICS (GPU)")
        gpu_title.setObjectName("CardTitle")
        gpu_layout.addWidget(gpu_title)

        self.gpu_status_lbl = QLabel("Scanning for dedicated GPU...")
        self.gpu_status_lbl.setObjectName("SubText")
        self.gpu_status_lbl.setWordWrap(True)
        gpu_layout.addWidget(self.gpu_status_lbl)
        gpu_layout.addStretch()
        grid.addWidget(self.gpu_card, 2, 0)

        # 5. Network Card
        self.net_card = self._create_card("// NETWORK ACTIVITY")
        net_layout = QVBoxLayout(self.net_card)
        net_layout.setContentsMargins(16, 16, 16, 16)
        net_layout.setSpacing(6)

        net_title = QLabel("// NETWORK ACTIVITY")
        net_title.setObjectName("CardTitle")
        net_layout.addWidget(net_title)

        speeds_layout = QHBoxLayout()
        self.net_down_lbl = QLabel("⬇ 0.0 KB/s")
        self.net_down_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #00d2ff;")
        speeds_layout.addWidget(self.net_down_lbl)

        self.net_up_lbl = QLabel("⬆ 0.0 KB/s")
        self.net_up_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #00a8ff;")
        speeds_layout.addWidget(self.net_up_lbl)
        net_layout.addLayout(speeds_layout)

        self.net_totals_lbl = QLabel("Total: 0 MB recv | 0 MB sent")
        self.net_totals_lbl.setObjectName("SubText")
        net_layout.addWidget(self.net_totals_lbl)
        net_layout.addStretch()
        grid.addWidget(self.net_card, 2, 1)

        # 6. Battery Card
        self.battery_card = self._create_card("// BATTERY & POWER")
        self.battery_layout = QVBoxLayout(self.battery_card)
        self.battery_layout.setContentsMargins(16, 16, 16, 16)
        self.battery_layout.setSpacing(6)

        bat_title = QLabel("// BATTERY & POWER")
        bat_title.setObjectName("CardTitle")
        self.battery_layout.addWidget(bat_title)

        self.battery_status_lbl = QLabel("AC Power Connected (Desktop / Plugged In)")
        self.battery_status_lbl.setStyleSheet("font-weight: 600; color: #ffffff;")
        self.battery_layout.addWidget(self.battery_status_lbl)

        self.battery_bar = QProgressBar()
        self.battery_bar.setFixedHeight(12)
        self.battery_layout.addWidget(self.battery_bar)

        self.battery_estimate_lbl = QLabel("Time remaining: Calculating...")
        self.battery_estimate_lbl.setObjectName("SubText")
        self.battery_layout.addWidget(self.battery_estimate_lbl)
        self.battery_layout.addStretch()
        grid.addWidget(self.battery_card, 2, 2)

        # -------------------------------------------------------------
        # ROW 3: System Info Card spanning all columns
        # -------------------------------------------------------------
        self.sys_info_card = self._create_card("// SYSTEM VITALS")
        sys_layout = QHBoxLayout(self.sys_info_card)
        sys_layout.setContentsMargins(20, 16, 20, 16)

        self.sys_os_lbl = QLabel("OS: Windows")
        self.sys_os_lbl.setObjectName("SubText")
        sys_layout.addWidget(self.sys_os_lbl)

        self.sys_host_lbl = QLabel("Host: --")
        self.sys_host_lbl.setObjectName("SubText")
        sys_layout.addWidget(self.sys_host_lbl)

        self.sys_user_lbl = QLabel("User: --")
        self.sys_user_lbl.setObjectName("SubText")
        sys_layout.addWidget(self.sys_user_lbl)

        self.sys_uptime_lbl = QLabel("Uptime: --")
        self.sys_uptime_lbl.setObjectName("SubText")
        sys_layout.addWidget(self.sys_uptime_lbl)

        grid.addWidget(self.sys_info_card, 3, 0, 1, 3)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _on_hero_flush_clicked(self):
        """Instant RAM working set trim triggered from Hero Banner."""
        from app.utils.ram_api import clean_ram
        res = clean_ram()
        freed = res.get("freed_gb", 0.0)
        self.hero_sub.setText(f"⚡ RAM FLUSH COMPLETE // Freed {freed:.2f} GB memory caches instantly.")
        self.hero_sub.setStyleSheet("font-size: 11px; color: #00e676; font-weight: bold;")
        parent = self.window()
        if hasattr(parent, "toast") and parent.toast:
            parent.toast.show_message("⚡ Instant RAM Flush", f"Successfully cleared {freed:.2f} GB from working sets.", level="success")

    def _create_card(self, name: str) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        return card

    def update_metrics(self, data: dict):
        """Handle incoming telemetry from SystemMonitorWorker."""
        # 1. Update CPU
        cpu = data.get("cpu", {})
        cpu_pct = cpu.get("percent", 0.0)
        self.cpu_gauge.set_value(cpu_pct)
        self.cpu_model_lbl.setText(cpu.get("model", "CPU"))
        self.cpu_freq_lbl.setText(f"Clock: {cpu.get('freq_current', 0):.0f} MHz (Max: {cpu.get('freq_max', 0):.0f} MHz)")

        cpu_temp = cpu.get("temp")
        if cpu_temp is not None:
            self.cpu_temp_lbl.setText(f"Core Temperature: {cpu_temp}°C")
            if cpu_temp >= 85:
                self.cpu_temp_lbl.setStyleSheet("color: #f85149; font-weight: bold;")
            elif cpu_temp >= 75:
                self.cpu_temp_lbl.setStyleSheet("color: #d29922; font-weight: bold;")
            else:
                self.cpu_temp_lbl.setStyleSheet("color: #3fb950;")
        else:
            self.cpu_temp_lbl.setText("Temp: N/A — Install OpenHardwareMonitor for temps")
            self.cpu_temp_lbl.setStyleSheet("color: #8b949e;")

        # Update Per-Core Bars
        per_core = cpu.get("per_core", [])
        if len(self._core_bars) != len(per_core):
            # Clear old bars
            for b in self._core_bars:
                b.deleteLater()
            self._core_bars.clear()
            for i in range(len(per_core)):
                h_box = QHBoxLayout()
                h_box.setSpacing(6)
                lbl = QLabel(f"C{i}")
                lbl.setFixedWidth(22)
                lbl.setStyleSheet("font-size: 10px; color: #8b949e;")
                bar = QProgressBar()
                bar.setFixedHeight(8)
                bar.setTextVisible(False)
                bar.setRange(0, 100)
                h_box.addWidget(lbl)
                h_box.addWidget(bar)
                self.cores_container.addLayout(h_box)
                self._core_bars.append(bar)

        for bar, val in zip(self._core_bars, per_core):
            bar.setValue(int(val))
            tier = 0 if val < 70 else (1 if val < 90 else 2)
            if getattr(bar, "_tier", -1) != tier:
                bar._tier = tier
                if tier == 0:
                    gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0052cc, stop:1 #00a8ff)"
                elif tier == 1:
                    gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #cc7000, stop:1 #ff9f1a)"
                else:
                    gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b30024, stop:1 #ff2a51)"
                bar.setStyleSheet(f"QProgressBar::chunk {{ background: {gradient}; border-radius: 2px; }}")

        # 2. Update RAM
        ram = data.get("ram", {})
        ram_pct = ram.get("percent", 0.0)
        self.ram_gauge.set_value(ram_pct)
        self.ram_breakdown_lbl.setText(f"{ram.get('used_gb', 0)} GB used / {ram.get('total_gb', 0)} GB total")
        self.ram_avail_lbl.setText(f"Available: {ram.get('available_gb', 0)} GB")
        self.ram_swap_lbl.setText(f"Pagefile / Swap: {ram.get('swap_percent', 0)}% ({ram.get('swap_used_gb', 0)} GB / {ram.get('swap_total_gb', 0)} GB)")
        self.ram_sparkline.add_point(ram_pct)

        # 3. Update Drives
        disk = data.get("disk", {})
        self.disk_io_lbl.setText(f"I/O Rates: Read {disk.get('read_mbs', 0):.2f} MB/s | Write {disk.get('write_mbs', 0):.2f} MB/s")

        partitions = disk.get("partitions", [])
        if len(self._drive_widgets) != len(partitions):
            for dw_info in self._drive_widgets:
                if isinstance(dw_info, tuple):
                    dw_info[0].deleteLater()
                else:
                    dw_info.deleteLater()
            self._drive_widgets.clear()

            for part in partitions:
                d_frame = QFrame()
                d_layout = QVBoxLayout(d_frame)
                d_layout.setContentsMargins(0, 2, 0, 2)
                d_layout.setSpacing(2)

                info_h = QHBoxLayout()
                name_lbl = QLabel(f"Drive {part.get('mountpoint', '')} ({part.get('fstype', '')})")
                name_lbl.setStyleSheet("font-weight: 600; font-size: 11px; color: #ffffff;")
                size_lbl = QLabel(f"{part.get('free_gb', 0)} GB free of {part.get('total_gb', 0)} GB")
                size_lbl.setStyleSheet("font-size: 11px; color: #8b949e;")
                info_h.addWidget(name_lbl)
                info_h.addStretch()
                info_h.addWidget(size_lbl)
                d_layout.addLayout(info_h)

                pbar = QProgressBar()
                pbar.setFixedHeight(8)
                pbar.setTextVisible(False)
                d_layout.addWidget(pbar)
                self.drives_container.addWidget(d_frame)
                self._drive_widgets.append((d_frame, size_lbl, pbar))

        for (d_frame, size_lbl, pbar), part in zip(self._drive_widgets, partitions):
            size_lbl.setText(f"{part.get('free_gb', 0)} GB free of {part.get('total_gb', 0)} GB")
            pct = part.get("percent", 0)
            pbar.setValue(int(pct))
            tier = 0 if pct < 70 else (1 if pct < 90 else 2)
            if getattr(pbar, "_tier", -1) != tier:
                pbar._tier = tier
                if tier == 0:
                    gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0052cc, stop:1 #00a8ff)"
                elif tier == 1:
                    gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #cc7000, stop:1 #ff9f1a)"
                else:
                    gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b30024, stop:1 #ff2a51)"
                pbar.setStyleSheet(f"QProgressBar::chunk {{ background: {gradient}; border-radius: 2px; }}")

        # 4. Update GPU
        gpus = data.get("gpu", [])
        if gpus:
            g_lines = []
            for g in gpus:
                g_lines.append(f"<b>{g.get('name', 'GPU')}</b><br>"
                               f"Load: {g.get('load', 0)}% | Memory: {g.get('memory_used', 0):.0f} / {g.get('memory_total', 0):.0f} MB<br>"
                               f"Temp: {g.get('temperature', '--')}°C")
            self.gpu_status_lbl.setText("<hr>".join(g_lines))
        else:
            self.gpu_status_lbl.setText("No dedicated GPU detected.<br><span style='color: #8b949e;'>Operating on integrated display adapter.</span>")

        # 5. Update Network
        net = data.get("network", {})
        down_str = format_bytes_speed(net.get("down_kbs", 0.0))
        up_str = format_bytes_speed(net.get("up_kbs", 0.0))
        self.net_down_lbl.setText(f"⬇ {down_str}")
        self.net_up_lbl.setText(f"⬆ {up_str}")
        self.net_totals_lbl.setText(f"Total Boot I/O: {net.get('total_recv_mb', 0)} MB down | {net.get('total_sent_mb', 0)} MB up")

        # 6. Update Battery
        bat = data.get("battery")
        if bat:
            self.battery_card.show()
            bat_pct = bat.get("percent", 0)
            self.battery_bar.setValue(int(bat_pct))
            plugged = bat.get("power_plugged", False)
            state_text = "Plugged In (Charging)" if plugged else "On Battery"
            self.battery_status_lbl.setText(f"{bat_pct:.0f}% — {state_text}")

            secs = bat.get("secsleft", -1)
            if secs and secs > 0:
                mins = int(secs // 60)
                hrs = mins // 60
                m = mins % 60
                self.battery_estimate_lbl.setText(f"Estimated: {hrs}h {m}m remaining")
            else:
                self.battery_estimate_lbl.setText("Power source: AC Adapter")
        else:
            self.battery_status_lbl.setText("AC Connected")
            self.battery_bar.setValue(100)
            self.battery_estimate_lbl.setText("Desktop workstation (no battery sensor)")

        # 7. Update System Card
        sys_data = data.get("system", {})
        self.sys_os_lbl.setText(f"<b>OS:</b> {sys_data.get('os', 'Windows')}")
        self.sys_host_lbl.setText(f"<b>Host:</b> {sys_data.get('hostname', '')}")
        self.sys_user_lbl.setText(f"<b>User:</b> {sys_data.get('username', '')}")
        self.sys_uptime_lbl.setText(f"<b>Uptime:</b> {sys_data.get('uptime', '')}")
