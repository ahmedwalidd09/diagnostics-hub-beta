import math
import random
import webbrowser
from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import QWidget, QMenu, QToolTip
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QCursor, QAction
from app.utils.eco_qos import set_process_eco_qos, trim_process_working_set
import psutil

# Category Colors (Muted, professional workstation palette)
COLOR_SYSTEM = QColor(71, 85, 105, 200)       # #475569 Neutral Slate
COLOR_BROWSER = QColor(99, 102, 241, 200)     # #6366f1 Soft Indigo
COLOR_DEV_APP = QColor(14, 165, 233, 200)     # #0ea5e9 Sky Blue
COLOR_UTILITY = QColor(13, 148, 136, 200)     # #0d9488 Muted Teal
COLOR_HIGH_RAM = QColor(239, 68, 68, 210)     # #ef4444 Muted Coral Red

SYSTEM_NAMES = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe",
    "dwm.exe", "explorer.exe", "sihost.exe", "taskhostw.exe", "spoolsv.exe"
}

BROWSER_NAMES = {
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe"
}

DEV_NAMES = {
    "code.exe", "pycharm64.exe", "idea64.exe", "devenv.exe", "python.exe",
    "node.exe", "git.exe", "powershell.exe", "cmd.exe", "docker.exe"
}


class BubbleNode:
    def __init__(self, data: Dict[str, Any], cx: float, cy: float):
        self.data = data
        self.name = data.get("name", "Unknown")
        self.pids = data.get("pids", [data.get("pid", 0)])
        self.primary_pid = self.pids[0] if self.pids else 0
        self.ram_mb = float(data.get("ram_mb", 1.0))
        self.pct = float(data.get("pct", 0.0))
        self.path = data.get("path", "")
        self.count = data.get("count", 1)

        # Physics variables
        self.x = cx + random.uniform(-40, 40)
        self.y = cy + random.uniform(-40, 40)
        self.vx = 0.0
        self.vy = 0.0
        self.radius = 20.0
        self.target_radius = 20.0

        # Style & category
        self.color = self._determine_color()

    def _determine_color(self) -> QColor:
        lower = self.name.lower()
        if self.ram_mb >= 1200.0:
            return COLOR_HIGH_RAM
        if lower in SYSTEM_NAMES:
            return COLOR_SYSTEM
        if lower in BROWSER_NAMES:
            return COLOR_BROWSER
        if lower in DEV_NAMES:
            return COLOR_DEV_APP
        return COLOR_UTILITY


class RamBubbleCanvas(QWidget):
    """
    Hardware-accelerated 2D Physics Bubble Canvas for Memory Distribution.
    Area of each bubble is directly proportional to its physical RAM consumption.
    Features center gravity, anti-collision relaxation, dampening, tooltips,
    and a rich right-click context menu.
    """
    process_action_triggered = pyqtSignal(str, int)  # (action, pid)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(400, 320)

        self._nodes: List[BubbleNode] = []
        self._hovered_node: Optional[BubbleNode] = None
        self._selected_node: Optional[BubbleNode] = None
        self._grouped_mode = True

        # Physics simulation timer (30 FPS, dampening to 0 once stabilized)
        self._physics_timer = QTimer(self)
        self._physics_timer.timeout.connect(self._step_physics)
        self._physics_ticks = 0
        self._is_simulating = False

    def set_grouped_mode(self, grouped: bool):
        self._grouped_mode = grouped
        self.update()

    def update_data(self, individual_procs: List[Dict[str, Any]], grouped_procs: List[Dict[str, Any]]):
        """Re-populates nodes with smooth transition of physics."""
        dataset = grouped_procs if self._grouped_mode else individual_procs
        dataset = dataset[:35]  # Top 35 entries for optimal visual clarity

        if not dataset:
            self._nodes = []
            self.update()
            return

        cx = self.width() / 2.0 if self.width() > 50 else 250.0
        cy = self.height() / 2.0 if self.height() > 50 else 200.0

        # Calculate radius scaling
        max_ram = max((p.get("ram_mb", 1.0) for p in dataset), default=1.0)
        # Area = pi * r^2 => r = sqrt(RAM / pi) * scale
        scale_factor = 45.0 / math.sqrt(max(max_ram, 10.0))

        existing_map = {n.name.lower(): n for n in self._nodes}
        new_nodes = []

        for item in dataset:
            name_key = item.get("name", "").lower()
            ram_mb = max(1.0, float(item.get("ram_mb", 1.0)))

            # Area-proportional radius with clamp [18px, 85px]
            r = math.sqrt(ram_mb / math.pi) * scale_factor
            r = max(18.0, min(85.0, r))

            if name_key in existing_map and self._grouped_mode:
                node = existing_map[name_key]
                node.data = item
                node.ram_mb = ram_mb
                node.pct = float(item.get("pct", 0.0))
                node.pids = item.get("pids", [item.get("pid", 0)])
                node.primary_pid = node.pids[0] if node.pids else 0
                node.count = item.get("count", 1)
                node.target_radius = r
                node.color = node._determine_color()
                new_nodes.append(node)
            else:
                node = BubbleNode(item, cx, cy)
                node.radius = r
                node.target_radius = r
                new_nodes.append(node)

        self._nodes = new_nodes
        self._start_physics()

    def _start_physics(self):
        self._physics_ticks = 0
        if not self._is_simulating:
            self._is_simulating = True
            self._physics_timer.start(33)  # ~30 FPS

    def _step_physics(self):
        if not self._nodes or not self.isVisible():
            self._physics_timer.stop()
            self._is_simulating = False
            return

        self._physics_ticks += 1
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        w = float(self.width())
        h = float(self.height())

        damping = 0.85
        center_gravity = 0.035
        max_movement = 0.0

        # Animate radius towards target
        for node in self._nodes:
            if abs(node.radius - node.target_radius) > 0.5:
                node.radius += (node.target_radius - node.radius) * 0.15

        # Pairwise anti-collision repulsion
        count = len(self._nodes)
        for i in range(count):
            n1 = self._nodes[i]
            for j in range(i + 1, count):
                n2 = self._nodes[j]
                dx = n2.x - n1.x
                dy = n2.y - n1.y
                dist = math.hypot(dx, dy)
                min_dist = n1.radius + n2.radius + 6.0  # 6px gap

                if dist < min_dist:
                    overlap = min_dist - dist
                    if dist < 0.001:
                        dx = random.uniform(-1, 1)
                        dy = random.uniform(-1, 1)
                        dist = 1.0

                    nx = dx / dist
                    ny = dy / dist
                    repel_force = overlap * 0.28
                    n1.vx -= nx * repel_force
                    n1.vy -= ny * repel_force
                    n2.vx += nx * repel_force
                    n2.vy += ny * repel_force

        # Apply center attraction, boundaries, and velocity updates
        for node in self._nodes:
            # Center pull
            dx = cx - node.x
            dy = cy - node.y
            node.vx += dx * center_gravity
            node.vy += dy * center_gravity

            # Velocity integration with damping
            node.vx *= damping
            node.vy *= damping
            node.x += node.vx
            node.y += node.vy

            # Boundary constraints
            pad = node.radius + 8.0
            if node.x < pad:
                node.x = pad
                node.vx *= -0.5
            elif node.x > w - pad:
                node.x = w - pad
                node.vx *= -0.5

            if node.y < pad:
                node.y = pad
                node.vy *= -0.5
            elif node.y > h - pad:
                node.y = h - pad
                node.vy *= -0.5

            movement = math.hypot(node.vx, node.vy)
            if movement > max_movement:
                max_movement = movement

        self.update()

        # Dampen and sleep when system has stabilized (zero idle CPU consumption)
        if (self._physics_ticks > 60 and max_movement < 0.35) or self._physics_ticks > 120:
            self._physics_timer.stop()
            self._is_simulating = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Subtle dark canvas background with 1px border
        painter.fillRect(self.rect(), QColor("#12151e"))
        painter.setPen(QPen(QColor("#262a38"), 1))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

        if not self._nodes:
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Collecting process memory distribution...")
            painter.end()
            return

        # Draw bubbles
        for node in self._nodes:
            is_hovered = (node == self._hovered_node)
            is_selected = (node == self._selected_node)

            # Bubble Fill
            fill_color = QColor(node.color)
            if is_hovered:
                fill_color.setAlpha(min(255, fill_color.alpha() + 45))

            painter.setBrush(QBrush(fill_color))

            # Bubble Border / Outline
            if is_selected:
                painter.setPen(QPen(QColor("#ffffff"), 2.5))
            elif is_hovered:
                painter.setPen(QPen(QColor("#38bdf8"), 2.0))
            else:
                border_color = QColor(fill_color)
                border_color.setAlpha(min(255, border_color.alpha() + 50))
                painter.setPen(QPen(border_color, 1.2))

            painter.drawEllipse(QPointF(node.x, node.y), node.radius, node.radius)

            # Bubble Labels (Only if radius allows text)
            if node.radius >= 22.0:
                painter.setPen(QColor("#ffffff"))

                # Process name
                title_font = QFont("Segoe UI", max(8, min(11, int(node.radius * 0.28))), QFont.Weight.Bold)
                painter.setFont(title_font)

                display_name = node.name
                if node.count > 1:
                    display_name = f"{node.name} ({node.count})"

                # Truncate if long
                if len(display_name) > 13 and node.radius < 45.0:
                    display_name = display_name[:11] + "…"

                # RAM string
                if node.ram_mb >= 1024.0:
                    ram_str = f"{node.ram_mb / 1024.0:.1f} GB"
                else:
                    ram_str = f"{int(round(node.ram_mb))} MB"

                name_rect = QRectF(node.x - node.radius, node.y - node.radius * 0.6,
                                   node.radius * 2, node.radius * 0.65)
                ram_rect = QRectF(node.x - node.radius, node.y + 2,
                                  node.radius * 2, node.radius * 0.55)

                painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter, display_name)

                # Secondary RAM label
                ram_font = QFont("Segoe UI", max(7, min(10, int(node.radius * 0.24))), QFont.Weight.Normal)
                painter.setFont(ram_font)
                painter.setPen(QColor("#e2e8f0"))
                painter.drawText(ram_rect, Qt.AlignmentFlag.AlignCenter, ram_str)

        painter.end()

    def mouseMoveEvent(self, event):
        pos = event.position()
        found = None
        for node in self._nodes:
            dist = math.hypot(node.x - pos.x(), node.y - pos.y())
            if dist <= node.radius:
                found = node
                break

        if found != self._hovered_node:
            self._hovered_node = found
            self.update()
            if found:
                pids_str = ", ".join(map(str, found.pids[:4]))
                if len(found.pids) > 4:
                    pids_str += f" (+{len(found.pids) - 4} more)"

                ram_val = f"{found.ram_mb:.1f} MB ({found.pct:.1f}% of RAM)"
                if found.ram_mb >= 1024.0:
                    ram_val = f"{found.ram_mb / 1024.0:.2f} GB ({found.pct:.1f}% of RAM)"

                tip = (
                    f"<b>{found.name}</b><br/>"
                    f"PIDs: {pids_str}<br/>"
                    f"RAM Usage: {ram_val}<br/>"
                    f"Instances: {found.count}<br/>"
                    f"Path: {found.path or 'System / Protected'}<br/>"
                    f"<i>Right-click for options (EcoQoS, Trim, End)</i>"
                )
                QToolTip.showText(QCursor.pos(), tip, self)
            else:
                QToolTip.hideText()

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        pos = event.position()
        clicked_node = None
        for node in self._nodes:
            dist = math.hypot(node.x - pos.x(), node.y - pos.y())
            if dist <= node.radius:
                clicked_node = node
                break

        if event.button() == Qt.MouseButton.LeftButton:
            self._selected_node = clicked_node
            self.update()
        elif event.button() == Qt.MouseButton.RightButton and clicked_node:
            self._selected_node = clicked_node
            self.update()
            self._show_context_menu(clicked_node, event.globalPosition().toPoint())

        super().mousePressEvent(event)

    def _show_context_menu(self, node: BubbleNode, global_pt):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161922;
                border: 1px solid #262a38;
                border-radius: 6px;
                padding: 4px;
                color: #f1f5f9;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
                font-size: 12px;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
        """)

        title_act = menu.addAction(f"Process: {node.name}")
        title_act.setEnabled(False)
        menu.addSeparator()

        trim_act = menu.addAction("🧹 Trim Working Set (Release RAM)")
        eco_act = menu.addAction("🍃 Enable Efficiency Mode (EcoQoS)")
        disable_eco_act = menu.addAction("⚡ Disable Efficiency Mode")
        menu.addSeparator()
        web_act = menu.addAction("🔍 Search Process on Web")
        kill_act = menu.addAction("🛑 Terminate Process Tree")

        action = menu.exec(global_pt)
        if not action:
            return

        for pid in node.pids:
            try:
                if action == trim_act:
                    trim_process_working_set(pid)
                    self.process_action_triggered.emit("trim", pid)
                elif action == eco_act:
                    set_process_eco_qos(pid, True)
                    self.process_action_triggered.emit("eco_on", pid)
                elif action == disable_eco_act:
                    set_process_eco_qos(pid, False)
                    self.process_action_triggered.emit("eco_off", pid)
                elif action == kill_act:
                    p = psutil.Process(pid)
                    for child in p.children(recursive=True):
                        child.terminate()
                    p.terminate()
                    self.process_action_triggered.emit("kill", pid)
            except Exception:
                continue

        if action == web_act:
            webbrowser.open(f"https://www.google.com/search?q={node.name}+windows+process")
