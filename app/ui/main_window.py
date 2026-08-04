"""
main_window.py - Hauptfenster der ADS_KI_Analyse-Anwendung (PySide6).

Änderungen gegenüber Vorgängerversion:
  - Aufgabe 3: Rechter Bereich (Analyse-Panel + Tab-Widget) in einen
    vertikalen QSplitter gepackt; setMaximumHeight(260) entfernt.
    Initiale Aufteilung ca. 65 % oben / 35 % unten.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDateTimeEdit,
    QGroupBox,
    QHBoxLayout,
    QFormLayout,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QDoubleSpinBox,
    QPlainTextEdit,
    QTextBrowser,
    QComboBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QFileDialog,
    QScrollArea,
    QColorDialog,
)

from app.ads.ads_client import AdsClient, AdsSymbolInfo
from app.config.settings import load_config, save_config
from app.domain.history_model import HistoryModel
from app.domain.state_model import StateModel, VariableState, DEFAULT_PLOT_COLORS
from app.llm.lm_studio_client import LmStudioClient
from app.llm.prompt_builder import build_user_message

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    log_message = Signal(str)
    status_message = Signal(str)
    connection_result = Signal(bool, str)
    symbols_loaded = Signal(list)
    value_updated = Signal(str, object, object)
    analysis_result = Signal(str, bool)


class DigitalTimelineWidget(QWidget):
    """Zeigt aufgezeichnete BOOL-Werte als gestapelte digitale Zeitlinien.

    Dies ist bewusst ein Zeitdiagramm und kein statistisches Histogramm:
    TRUE wird als 1, FALSE als 0 und jede Wertänderung als Flanke dargestellt.
    Die Daten stammen ausschließlich aus der HistoryModel-Historie.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._from_dt = None
        self._to_dt = None
        self._message = "Noch keine aufgezeichneten BOOL-Daten vorhanden."
        self.setMinimumWidth(900)
        self.setMinimumHeight(160)

    def set_data(self, rows, from_dt=None, to_dt=None):
        self._rows = list(rows)
        self._from_dt = from_dt
        self._to_dt = to_dt
        if not self._rows:
            self._message = "Keine aufgezeichneten BOOL-Daten vorhanden."
        else:
            self._message = ""
        height = max(160, 72 + len(self._rows) * 58)
        self.setMinimumHeight(height)
        self.resize(self.width(), height)
        self.update()

    @staticmethod
    def _time_text(value):
        return value.strftime("%H:%M:%S") if value else "-"

    def _x_for(self, timestamp, start, end, left, plot_width):
        total = (end - start).total_seconds()
        if total <= 0:
            return left
        ratio = (timestamp - start).total_seconds() / total
        return left + max(0.0, min(1.0, ratio)) * plot_width

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#ffffff"))

        left = 235
        right = 35
        top = 34
        bottom = 34
        plot_width = max(120, self.width() - left - right)

        if not self._rows:
            painter.setPen(QColor("#68737d"))
            painter.drawText(20, 35, self._message)
            return

        all_entries = [entry for _, _, entries in self._rows for entry in entries]
        if not all_entries:
            painter.setPen(QColor("#68737d"))
            painter.drawText(20, 35, "Keine Historieneinträge für aufgezeichnete BOOL-Variablen.")
            return

        start = self._from_dt or min(entry.timestamp for entry in all_entries)
        end = self._to_dt or datetime.now()
        if end <= start:
            end = start + timedelta(seconds=1)

        # Header and vertical time grid.
        painter.setPen(QColor("#6b747d"))
        painter.drawText(left, 18, self._time_text(start))
        painter.drawText(left + plot_width - 48, 18, self._time_text(end))
        grid_pen = QPen(QColor("#d9e0e6"), 1)
        for index in range(11):
            x = left + plot_width * index / 10.0
            painter.setPen(grid_pen)
            painter.drawLine(int(x), top - 10, int(x), top + len(self._rows) * 58)
            if index not in (0, 10):
                stamp = start + (end - start) * index / 10.0
                painter.setPen(QColor("#7a858e"))
                painter.drawText(int(x) - 28, 18, self._time_text(stamp))

        for row_index, (symbol, color_name, entries) in enumerate(self._rows):
            row_top = top + row_index * 58
            high_y = row_top + 10
            low_y = row_top + 34
            base_color = QColor(color_name)
            if not base_color.isValid():
                base_color = QColor("#4c72b0")

            painter.setPen(QColor("#2f3942"))
            painter.drawText(10, row_top + 24, symbol)
            painter.setPen(QColor("#aeb8c1"))
            painter.drawLine(left, low_y, left + plot_width, low_y)
            painter.setPen(QColor("#c7d0d8"))
            painter.drawRect(left, row_top, plot_width, 43)

            ordered = sorted(entries, key=lambda entry: entry.timestamp)
            if not ordered:
                continue
            current = bool(ordered[0].value)
            current_time = max(start, ordered[0].timestamp)
            line_pen = QPen(base_color, 4)
            fill_color = QColor(base_color)
            fill_color.setAlpha(42)
            painter.setPen(line_pen)
            painter.setBrush(QBrush(fill_color))

            for entry in ordered[1:]:
                change_time = max(start, min(end, entry.timestamp))
                x1 = self._x_for(current_time, start, end, left, plot_width)
                x2 = self._x_for(change_time, start, end, left, plot_width)
                y = high_y if current else low_y
                painter.drawLine(int(x1), y, int(x2), y)
                painter.fillRect(int(x1), row_top + 2, max(1, int(x2 - x1)), 39, fill_color)
                new_value = bool(entry.value)
                if new_value != current:
                    painter.drawLine(int(x2), high_y, int(x2), low_y)
                current = new_value
                current_time = change_time

            x1 = self._x_for(current_time, start, end, left, plot_width)
            x2 = self._x_for(end, start, end, left, plot_width)
            y = high_y if current else low_y
            painter.drawLine(int(x1), y, int(x2), y)
            painter.fillRect(int(x1), row_top + 2, max(1, int(x2 - x1)), 39, fill_color)
            painter.setPen(QColor("#27313a"))
            painter.drawText(left + plot_width + 8, high_y + 5 if current else low_y + 5, "1" if current else "0")

        painter.setPen(QColor("#68737d"))
        painter.drawText(10, top + len(self._rows) * 58 + 22, "TRUE = 1   |   FALSE = 0   |   Zeitraum: echte ADS-Historie")


class SettingsDialog(QDialog):
    """Separates, scrollbar-friendly settings window."""

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ADS_KI_Analyse - Einstellungen")
        self.resize(720, 760)
        self.setMinimumSize(620, 600)
        self.cfg = cfg
        self._build()
        self._load_from_cfg()

    def _build(self):
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form_box = QVBoxLayout(content)

        ads_box = QGroupBox("ADS-Verbindung")
        ads_form = QFormLayout(ads_box)
        self.ads_timeout = QDoubleSpinBox()
        self.ads_timeout.setRange(0.1, 120)
        self.ads_timeout.setDecimals(1)
        self.ads_timeout.setSuffix(" s")
        self.cycle_ms = QSpinBox()
        self.cycle_ms.setRange(1, 60000)
        self.cycle_ms.setSuffix(" ms")
        ads_form.addRow("Verbindungs-Timeout:", self.ads_timeout)
        ads_form.addRow("Notification-Zyklus:", self.cycle_ms)
        form_box.addWidget(ads_box)

        llm_box = QGroupBox("LM Studio / LLM")
        llm_form = QFormLayout(llm_box)
        self.llm_timeout = QDoubleSpinBox()
        self.llm_timeout.setRange(1, 3600)
        self.llm_timeout.setDecimals(1)
        self.llm_timeout.setSuffix(" s")
        self.context = QSpinBox()
        self.context.setRange(256, 1048576)
        self.context.setSingleStep(256)
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0, 2)
        self.temperature.setDecimals(3)
        self.temperature.setSingleStep(0.05)
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(1, 1048576)
        self.top_p = QDoubleSpinBox()
        self.top_p.setRange(0, 1)
        self.top_p.setDecimals(3)
        self.top_p.setSingleStep(0.05)
        self.top_k = QSpinBox()
        self.top_k.setRange(0, 100000)
        self.repeat_penalty = QDoubleSpinBox()
        self.repeat_penalty.setRange(0, 10)
        self.repeat_penalty.setDecimals(3)
        self.repeat_penalty.setSingleStep(0.05)
        self.stream = QCheckBox("Streaming aktivieren")
        llm_form.addRow("LLM-Timeout:", self.llm_timeout)
        llm_form.addRow("Kontextlänge (n_ctx):", self.context)
        llm_form.addRow("Temperatur:", self.temperature)
        llm_form.addRow("Maximale Antworttoken:", self.max_tokens)
        llm_form.addRow("Top-P:", self.top_p)
        llm_form.addRow("Top-K:", self.top_k)
        llm_form.addRow("Repeat Penalty:", self.repeat_penalty)
        llm_form.addRow("Übertragung:", self.stream)
        form_box.addWidget(llm_box)

        log_box = QGroupBox("Logging")
        log_form = QFormLayout(log_box)
        self.max_entries = QSpinBox()
        self.max_entries.setRange(100, 1000000)
        self.log_file = QLineEdit()
        log_form.addRow("Maximale Verlaufseinträge:", self.max_entries)
        log_form.addRow("Logdatei:", self.log_file)
        form_box.addWidget(log_box)

        prompt_box = QGroupBox("System-Prompt")
        prompt_form = QVBoxLayout(prompt_box)
        self.prompt = QPlainTextEdit()
        self.prompt.setMinimumHeight(150)
        prompt_form.addWidget(self.prompt)
        form_box.addWidget(prompt_box)

        form_box.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _load_from_cfg(self):
        ads = self.cfg.get("ads", {})
        llm = self.cfg.get("llm", {})
        logging_cfg = self.cfg.get("logging", {})
        self.ads_timeout.setValue(float(ads.get("timeout_seconds", 3.0)))
        self.cycle_ms.setValue(int(ads.get("notification_cycle_ms", 10)))
        self.llm_timeout.setValue(float(llm.get("timeout_seconds", 60.0)))
        self.context.setValue(int(llm.get("context_length", 4096)))
        self.temperature.setValue(float(llm.get("temperature", 0.1)))
        self.max_tokens.setValue(int(llm.get("max_tokens", 1200)))
        self.top_p.setValue(float(llm.get("top_p", 0.95)))
        self.top_k.setValue(int(llm.get("top_k", 40)))
        self.repeat_penalty.setValue(float(llm.get("repeat_penalty", 1.1)))
        self.stream.setChecked(bool(llm.get("stream", False)))
        self.max_entries.setValue(int(logging_cfg.get("max_entries", 5000)))
        self.log_file.setText(logging_cfg.get("file", "logs/app.log"))
        self.prompt.setPlainText(llm.get("system_prompt", ""))

    def values(self) -> dict:
        return {
            "ads": {
                **self.cfg.get("ads", {}),
                "timeout_seconds": self.ads_timeout.value(),
                "notification_cycle_ms": self.cycle_ms.value(),
            },
            "llm": {
                **self.cfg.get("llm", {}),
                "timeout_seconds": self.llm_timeout.value(),
                "context_length": self.context.value(),
                "temperature": self.temperature.value(),
                "max_tokens": self.max_tokens.value(),
                "top_p": self.top_p.value(),
                "top_k": self.top_k.value(),
                "repeat_penalty": self.repeat_penalty.value(),
                "stream": self.stream.isChecked(),
                "system_prompt": self.prompt.toPlainText(),
            },
            "logging": {
                **self.cfg.get("logging", {}),
                "max_entries": self.max_entries.value(),
                "file": self.log_file.text().strip() or "logs/app.log",
                "timestamp_precision": "milliseconds",
            },
            "variables": self.cfg.get("variables", []),
        }


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ADS_KI_Analyse")
        self.resize(1500, 950)
        self.cfg = load_config()
        self.state_model = StateModel()
        self.history_model = HistoryModel(
            max_entries=self.cfg.get("logging", {}).get("max_entries", 5000)
        )
        self.ads_client: Optional[AdsClient] = None
        self.llm_client: Optional[LmStudioClient] = None
        self.signals = WorkerSignals()
        self._last_values: Dict[str, object] = {}
        self._trigger_symbol: Optional[str] = None
        self._trigger_armed = False
        self._trigger_last_value: Optional[bool] = None
        self._trigger_edge = "rising"
        self._trigger_window_seconds = 120
        self._trigger_post_seconds = 10
        self._trigger_analysis_running = False
        self._pending_trigger_timestamp: Optional[datetime] = None
        self._recording_status = "STOPPED"
        self._recording_error = ""
        self._recording_generation = 0
        self._recording_worker_active = False
        # Das Diagramm verwendet ein rollierendes Anzeigezeitfenster. Der
        # Endzeitpunkt wird beim Stoppen eingefroren; die Historie bleibt davon
        # unberührt und steht weiterhin vollständig für die KI-Analyse bereit.
        self._timeline_window_seconds = 60
        self._timeline_end: Optional[datetime] = None
        self._build_ui()
        self._connect_signals()
        self._apply_config_to_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_table)
        self._refresh_timer.timeout.connect(self._refresh_timeline)
        self._refresh_timer.start(500)

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Linke Seite: Verbindung + Variablen
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(self._build_connection_panel())
        left_layout.addWidget(self._build_variable_panel())
        splitter.addWidget(left_widget)

        # Rechte Seite: vertikaler Splitter (Analyse oben / Tabs unten)
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self._build_analysis_panel())
        right_splitter.addWidget(self._build_right_tabs())

        # Initiale Aufteilung: ca. 65 % oben / 35 % unten
        # Werte werden nach dem ersten Show gesetzt; wir merken uns den Splitter.
        self._right_splitter = right_splitter
        splitter.addWidget(right_splitter)

        splitter.setSizes([720, 780])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit")

    def showEvent(self, event) -> None:
        """Setzt die initiale Splitter-Aufteilung nach dem ersten Anzeigen."""
        super().showEvent(event)
        total = self._right_splitter.height()
        if total > 0:
            self._right_splitter.setSizes([int(total * 0.65), int(total * 0.35)])

    def _build_connection_panel(self) -> QGroupBox:
        box = QGroupBox("Verbindung")
        layout = QVBoxLayout(box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Host / IP:"))
        self.le_host = QLineEdit()
        self.le_host.setPlaceholderText("z.B. 192.168.0.1")
        row1.addWidget(self.le_host)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("AMS Net ID:"))
        self.le_ams = QLineEdit()
        self.le_ams.setPlaceholderText("z.B. 192.168.0.1.1.1")
        row2.addWidget(self.le_ams)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("ADS-Port:"))
        self.sb_port = QSpinBox()
        self.sb_port.setRange(1, 65535)
        self.sb_port.setValue(851)
        row3.addWidget(self.sb_port)
        row3.addStretch()
        layout.addLayout(row3)

        btn_row = QHBoxLayout()
        self.btn_connect = QPushButton("Verbinden")
        self.btn_connect.setStyleSheet(
            "background-color: #2e7d32; color: white; font-weight: bold;"
        )
        self.btn_disconnect = QPushButton("Trennen")
        self.btn_disconnect.setEnabled(False)
        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(self.btn_disconnect)
        layout.addLayout(btn_row)

        self.lbl_conn_status = QLabel("Nicht verbunden")
        self.lbl_conn_status.setStyleSheet("color: gray; font-weight: bold;")
        layout.addWidget(self.lbl_conn_status)

        self.btn_settings = QPushButton("Einstellungen öffnen...")
        self.btn_settings.setToolTip("ADS-, LLM-, Logging- und Prompt-Einstellungen")
        layout.addWidget(self.btn_settings)

        return box

    def _build_variable_panel(self) -> QGroupBox:
        box = QGroupBox("Variablen")
        layout = QVBoxLayout(box)

        btn_row = QHBoxLayout()
        self.btn_load_symbols = QPushButton("Alle Symbole auslesen")
        self.btn_load_symbols.setEnabled(False)
        self.btn_recording = QPushButton("Aufzeichnung starten")
        self.btn_recording.setEnabled(False)
        btn_row.addWidget(self.btn_load_symbols)
        btn_row.addWidget(self.btn_recording)
        layout.addLayout(btn_row)
        self.lbl_recording_status = QLabel("Aufzeichnung: gestoppt")
        self.lbl_recording_status.setStyleSheet("color: #666; font-weight: bold;")
        layout.addWidget(self.lbl_recording_status)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.le_filter = QLineEdit()
        self.le_filter.setPlaceholderText("Symbolname filtern...")
        self.le_filter.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.le_filter)
        layout.addLayout(filter_row)

        self.var_table = QTableWidget()
        self.var_table.setColumnCount(7)
        self.var_table.setHorizontalHeaderLabels(
            ["Symbol", "Typ", "TC-Typ", "Kommentar", "Farbe", "Aufzeichnen", "Wert"]
        )
        self.var_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.var_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.var_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.var_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.var_table.setSortingEnabled(True)
        layout.addWidget(self.var_table)

        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("Max. Logeintraege:"))
        self.sb_max_entries = QSpinBox()
        self.sb_max_entries.setRange(100, 100000)
        self.sb_max_entries.setValue(5000)
        self.sb_max_entries.valueChanged.connect(self._on_max_entries_changed)
        max_row.addWidget(self.sb_max_entries)
        max_row.addStretch()
        layout.addLayout(max_row)

        trigger_box = QGroupBox("Automatische Triggeranalyse")
        trigger_layout = QHBoxLayout(trigger_box)
        trigger_layout.addWidget(QLabel("BOOL-Trigger:"))
        self.cb_trigger_symbol = QComboBox()
        self.cb_trigger_symbol.setPlaceholderText("Nach Symbolladen auswählen")
        self.cb_trigger_symbol.setMinimumWidth(220)
        trigger_layout.addWidget(self.cb_trigger_symbol)
        trigger_layout.addWidget(QLabel("auslösen bei:"))
        self.cb_trigger_edge = QComboBox()
        self.cb_trigger_edge.addItem("FALSE → TRUE", "rising")
        self.cb_trigger_edge.addItem("TRUE → FALSE", "falling")
        self.cb_trigger_edge.addItem("beide Flanken", "both")
        trigger_layout.addWidget(self.cb_trigger_edge)
        trigger_layout.addWidget(QLabel("Rückblick:"))
        self.cb_trigger_window = QComboBox()
        for seconds, label in [(30, "30 s"), (60, "1 min"), (120, "2 min"), (300, "5 min"), (600, "10 min")]:
            self.cb_trigger_window.addItem(label, seconds)
        self.cb_trigger_window.setCurrentIndex(2)
        trigger_layout.addWidget(self.cb_trigger_window)
        trigger_layout.addWidget(QLabel("Nachlauf:"))
        self.sb_trigger_post = QSpinBox()
        self.sb_trigger_post.setRange(0, 300)
        self.sb_trigger_post.setValue(10)
        self.sb_trigger_post.setSuffix(" s")
        trigger_layout.addWidget(self.sb_trigger_post)
        self.btn_trigger_arm = QPushButton("Trigger scharf schalten")
        self.btn_trigger_arm.setEnabled(False)
        self.btn_trigger_arm.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        trigger_layout.addWidget(self.btn_trigger_arm)
        self.lbl_trigger_status = QLabel("Nicht scharf")
        self.lbl_trigger_status.setStyleSheet("color: gray; font-weight: bold;")
        trigger_layout.addWidget(self.lbl_trigger_status)
        layout.addWidget(trigger_box)

        return box

    def _build_analysis_panel(self) -> QGroupBox:
        box = QGroupBox("KI-Analyse")
        layout = QVBoxLayout(box)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Von:"))
        self.dt_from = QDateTimeEdit()
        self.dt_from.setDisplayFormat("dd.MM.yyyy HH:mm:ss")
        self.dt_from.setDateTime(datetime.now().replace(hour=0, minute=0, second=0))
        time_row.addWidget(self.dt_from)
        time_row.addWidget(QLabel("Bis:"))
        self.dt_to = QDateTimeEdit()
        self.dt_to.setDisplayFormat("dd.MM.yyyy HH:mm:ss")
        self.dt_to.setDateTime(datetime.now())
        time_row.addWidget(self.dt_to)
        self.btn_now = QPushButton("Jetzt")
        self.btn_now.clicked.connect(lambda: self.dt_to.setDateTime(datetime.now()))
        time_row.addWidget(self.btn_now)
        layout.addLayout(time_row)

        layout.addWidget(QLabel("System-Prompt (editierbar):"))
        self.te_prompt = QPlainTextEdit()
        self.te_prompt.setMaximumHeight(80)
        self.te_prompt.setPlainText(
            self.cfg.get("llm", {}).get("system_prompt", "")
        )
        layout.addWidget(self.te_prompt)

        llm_row = QHBoxLayout()
        llm_row.addWidget(QLabel("LM Studio URL:"))
        self.le_llm_url = QLineEdit()
        self.le_llm_url.setPlaceholderText("http://127.0.0.1:1234/v1")
        llm_row.addWidget(self.le_llm_url)
        llm_row.addWidget(QLabel("Modell:"))
        self.le_model = QLineEdit()
        self.le_model.setPlaceholderText("Modellname")
        llm_row.addWidget(self.le_model)
        layout.addLayout(llm_row)

        btn_row = QHBoxLayout()
        self.btn_analyze = QPushButton("Zeitfenster analysieren")
        self.btn_analyze.setStyleSheet(
            "background-color: #1565c0; color: white; font-weight: bold;"
        )
        self.btn_check_llm = QPushButton("LM Studio pruefen")
        btn_row.addWidget(self.btn_analyze)
        btn_row.addWidget(self.btn_check_llm)
        layout.addLayout(btn_row)

        self.lbl_last_analysis = QLabel("Letzte Analyse: -")
        layout.addWidget(self.lbl_last_analysis)

        layout.addWidget(QLabel("KI-Antwort:"))
        self.te_result = QTextBrowser()
        self.te_result.setOpenExternalLinks(False)
        self.te_result.setOpenLinks(False)
        self.te_result.setReadOnly(True)
        self.te_result.setPlaceholderText("Hier erscheint die KI-Analyse...")
        self.te_result.setStyleSheet(
            """
            QTextBrowser {
                background: #fbfcfe;
                border: 1px solid #b8c2cc;
                border-radius: 4px;
                padding: 8px;
                color: #17212b;
            }
            """
        )
        layout.addWidget(self.te_result)

        return box

    def _build_right_tabs(self) -> QTabWidget:
        """
        Tabs: Protokoll (nur geloggte Änderungen) + Systemmeldungen + Prompt-Vorschau.

        HINWEIS: setMaximumHeight() wurde entfernt. Die Höhe wird jetzt durch
        den vertikalen QSplitter (_right_splitter) gesteuert.
        """
        tabs = QTabWidget()
        mono = QFont("Courier New", 9)

        # --- Tab 1: Protokoll ---
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        info = QLabel(
            "Aufgezeichnete Variablen werden live überwacht, historisch gespeichert und für die KI verwendet."
        )
        info.setStyleSheet("color: gray; font-size: 10px;")
        log_layout.addWidget(info)
        self.te_log = QPlainTextEdit()
        self.te_log.setReadOnly(True)
        self.te_log.setMaximumBlockCount(2000)
        self.te_log.setFont(mono)
        self.te_log.setPlaceholderText("Hier erscheinen Änderungen geloggter Variablen...")
        log_layout.addWidget(self.te_log)
        btn_row = QHBoxLayout()
        btn_clear_log = QPushButton("Protokoll leeren")
        btn_clear_log.clicked.connect(self.te_log.clear)
        btn_row.addWidget(btn_clear_log)
        btn_row.addStretch()
        log_layout.addLayout(btn_row)
        tabs.addTab(log_widget, "Protokoll (Aufzeichnung)")

        # --- Tab 2: Systemmeldungen ---
        sys_widget = QWidget()
        sys_layout = QVBoxLayout(sys_widget)
        sys_info = QLabel("Verbindung, Notifications, Fehler und Systemereignisse.")
        sys_info.setStyleSheet("color: gray; font-size: 10px;")
        sys_layout.addWidget(sys_info)
        self.te_sys = QPlainTextEdit()
        self.te_sys.setReadOnly(True)
        self.te_sys.setMaximumBlockCount(500)
        self.te_sys.setFont(mono)
        sys_layout.addWidget(self.te_sys)
        btn_clear_sys = QPushButton("Leeren")
        btn_clear_sys.clicked.connect(self.te_sys.clear)
        sys_layout.addWidget(btn_clear_sys)
        tabs.addTab(sys_widget, "Systemmeldungen")

        # --- Tab 3: Prompt-Vorschau ---
        prompt_widget = QWidget()
        prompt_layout = QVBoxLayout(prompt_widget)
        prompt_info = QLabel("Genau das wird bei der nächsten Analyse an die KI gesendet.")
        prompt_info.setStyleSheet("color: gray; font-size: 10px;")
        prompt_layout.addWidget(prompt_info)
        self.te_prompt_preview = QPlainTextEdit()
        self.te_prompt_preview.setReadOnly(True)
        self.te_prompt_preview.setFont(mono)
        self.te_prompt_preview.setPlaceholderText(
            "Klicken Sie auf 'Vorschau aktualisieren' um zu sehen, was an die KI gesendet wird..."
        )
        prompt_layout.addWidget(self.te_prompt_preview)
        btn_preview = QPushButton("Vorschau aktualisieren")
        btn_preview.setStyleSheet("font-weight: bold;")
        btn_preview.clicked.connect(self._update_prompt_preview)
        prompt_layout.addWidget(btn_preview)
        tabs.addTab(prompt_widget, "Prompt-Vorschau (was geht an die KI?)")

        # --- Tab 4: BOOL-Zeitdiagramm ---
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        chart_info = QLabel(
            "Digitale Zeitlinien der aufgezeichneten BOOL-Variablen. "
            "TRUE = 1, FALSE = 0. Farben werden in der Variablentabelle festgelegt."
        )
        chart_info.setStyleSheet("color: gray; font-size: 10px;")
        chart_layout.addWidget(chart_info)
        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_chart = DigitalTimelineWidget()
        self.timeline_scroll.setWidget(self.timeline_chart)
        chart_layout.addWidget(self.timeline_scroll)

        timeline_controls = QHBoxLayout()
        timeline_controls.addWidget(QLabel("Angezeigtes Zeitfenster:"))
        self.cb_timeline_window = QComboBox()
        for seconds, label in [
            (30, "30 Sekunden"),
            (60, "1 Minute"),
            (120, "2 Minuten"),
            (300, "5 Minuten"),
            (600, "10 Minuten"),
            (1800, "30 Minuten"),
        ]:
            self.cb_timeline_window.addItem(label, seconds)
        self.cb_timeline_window.setCurrentIndex(1)
        self.cb_timeline_window.setToolTip(
            "Nur dieses Zeitfenster wird im BOOL-Zeitdiagramm angezeigt. "
            "Ältere Daten bleiben für Historie und KI erhalten."
        )
        self.cb_timeline_window.currentIndexChanged.connect(self._on_timeline_window_changed)
        timeline_controls.addWidget(self.cb_timeline_window)
        self.lbl_timeline_info = QLabel("Diagramm: rollierend | Aufzeichnung gestoppt")
        self.lbl_timeline_info.setStyleSheet("color: #68737d; font-size: 10px;")
        timeline_controls.addWidget(self.lbl_timeline_info)
        timeline_controls.addStretch()
        chart_layout.addLayout(timeline_controls)
        tabs.addTab(chart_widget, "BOOL-Zeitdiagramm")

        return tabs

    # ------------------------------------------------------------------
    # Signale verbinden
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        self.btn_load_symbols.clicked.connect(self._on_load_symbols)
        self.btn_recording.clicked.connect(self._toggle_recording)
        self.btn_analyze.clicked.connect(self._on_analyze)
        self.btn_check_llm.clicked.connect(self._on_check_llm)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_trigger_arm.clicked.connect(self._arm_trigger)
        self.cb_trigger_symbol.currentIndexChanged.connect(self._on_trigger_config_changed)
        self.cb_trigger_edge.currentIndexChanged.connect(self._on_trigger_config_changed)
        self.cb_trigger_window.currentIndexChanged.connect(self._on_trigger_config_changed)
        self.sb_trigger_post.valueChanged.connect(self._on_trigger_config_changed)
        self.signals.log_message.connect(self._append_sys)
        self.signals.status_message.connect(self._on_recording_worker_status)
        self.signals.connection_result.connect(self._on_connection_result)
        self.signals.symbols_loaded.connect(self._on_symbols_loaded)
        self.signals.value_updated.connect(self._on_value_updated)
        self.signals.analysis_result.connect(self._on_analysis_result)

    def _apply_config_to_ui(self) -> None:
        ads = self.cfg.get("ads", {})
        self.le_host.setText(ads.get("host", ""))
        self.le_ams.setText(ads.get("ams_net_id", ""))
        self.sb_port.setValue(ads.get("port", 851))
        llm = self.cfg.get("llm", {})
        self.le_llm_url.setText(llm.get("base_url", "http://127.0.0.1:1234/v1"))
        self.le_model.setText(llm.get("model", ""))
        self.sb_max_entries.setValue(
            self.cfg.get("logging", {}).get("max_entries", 5000)
        )

    # ------------------------------------------------------------------
    # Verbindung
    # ------------------------------------------------------------------

    def _on_connect(self) -> None:
        host = self.le_host.text().strip()
        ams = self.le_ams.text().strip()
        port = self.sb_port.value()
        if not host or not ams:
            QMessageBox.warning(self, "Eingabe fehlt", "Bitte Host und AMS Net ID eingeben.")
            return
        self.btn_connect.setEnabled(False)
        self.lbl_conn_status.setText("Verbinde...")
        self.lbl_conn_status.setStyleSheet("color: orange; font-weight: bold;")
        self._append_sys("Verbindungsversuch: " + host + " / " + ams + " / Port " + str(port))
        self.ads_client = AdsClient(
            host=host,
            ams_net_id=ams,
            port=port,
            timeout_seconds=float(self.cfg.get("ads", {}).get("timeout_seconds", 3.0)),
            notification_cycle_ms=int(self.cfg.get("ads", {}).get("notification_cycle_ms", 10)),
        )
        self.ads_client.on_value_changed = self._ads_value_callback
        self.ads_client.on_error = lambda msg: self.signals.log_message.emit("[ADS-FEHLER] " + msg)

        def _worker():
            ok, msg = self.ads_client.connect()
            self.signals.connection_result.emit(ok, msg)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_connection_result(self, ok: bool, msg: str) -> None:
        if ok:
            self.lbl_conn_status.setText("ADS verifiziert – echte TwinCAT-Runtime")
            self.lbl_conn_status.setStyleSheet("color: green; font-weight: bold;")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.btn_load_symbols.setEnabled(True)
            self._append_sys("[VERBUNDEN] " + msg)
            self.status_bar.showMessage("ADS verbunden")
            self._save_connection_config()
        else:
            self.lbl_conn_status.setText("Verbindung fehlgeschlagen")
            self.lbl_conn_status.setStyleSheet("color: red; font-weight: bold;")
            self.btn_connect.setEnabled(True)
            self._append_sys("[FEHLER] " + msg)
            QMessageBox.critical(self, "Verbindungsfehler", msg)

    def _on_disconnect(self) -> None:
        # Notifications vor dem Schließen der ADS-Verbindung entfernen.
        self._stop_recording()
        if self.ads_client:
            self.ads_client.disconnect()
        self.lbl_conn_status.setText("Getrennt")
        self.lbl_conn_status.setStyleSheet("color: gray; font-weight: bold;")
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.btn_load_symbols.setEnabled(False)
        self._timeline_end = None
        self.state_model.clear()
        self.var_table.setRowCount(0)
        self._last_values.clear()
        self._append_sys("[GETRENNT] ADS-Verbindung getrennt")

    def _save_connection_config(self) -> None:
        self.cfg.setdefault("ads", {})
        self.cfg["ads"]["host"] = self.le_host.text().strip()
        self.cfg["ads"]["ams_net_id"] = self.le_ams.text().strip()
        self.cfg["ads"]["port"] = self.sb_port.value()
        save_config(self.cfg)

    # ------------------------------------------------------------------
    # Symbole laden
    # ------------------------------------------------------------------

    def _on_load_symbols(self) -> None:
        if not self.ads_client or not self.ads_client.connected:
            return
        self._append_sys("Lade alle ADS-Symbole...")
        self.btn_load_symbols.setEnabled(False)

        def _worker():
            symbols, err = self.ads_client.read_all_symbols()
            if err:
                self.signals.log_message.emit("[FEHLER] " + err)
            self.signals.symbols_loaded.emit(symbols)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_symbols_loaded(self, symbols: list) -> None:
        self.btn_load_symbols.setEnabled(True)
        if not symbols:
            self._append_sys("Keine Symbole geladen.")
            return
        var_states = []
        for index, sym in enumerate(symbols):
            vs = VariableState(
                symbol=sym.name,
                data_type=sym.data_type,
                tc_type=sym.tc_type,
                comment=sym.comment,
                supported=sym.supported,
                plot_color=DEFAULT_PLOT_COLORS[index % len(DEFAULT_PLOT_COLORS)],
            )
            var_states.append(vs)
        self.state_model.set_symbols(var_states)
        self._populate_table(var_states)
        self._populate_trigger_symbols(var_states)
        self._update_control_states()
        self._append_sys(str(len(symbols)) + " Symbole geladen.")

    def _populate_trigger_symbols(self, var_states: list) -> None:
        current = self._trigger_symbol
        self.cb_trigger_symbol.blockSignals(True)
        self.cb_trigger_symbol.clear()
        self.cb_trigger_symbol.addItem("-- kein Trigger ausgewählt --", None)
        for vs in var_states:
            if vs.supported and vs.data_type == "BOOL":
                self.cb_trigger_symbol.addItem(vs.symbol, vs.symbol)
        if current:
            index = self.cb_trigger_symbol.findData(current)
            if index >= 0:
                self.cb_trigger_symbol.setCurrentIndex(index)
        self.cb_trigger_symbol.blockSignals(False)
        self.btn_trigger_arm.setEnabled(bool(self.cb_trigger_symbol.currentData()))

    def _on_trigger_config_changed(self) -> None:
        self._trigger_symbol = self.cb_trigger_symbol.currentData()
        self._trigger_edge = self.cb_trigger_edge.currentData() or "rising"
        self._trigger_window_seconds = int(self.cb_trigger_window.currentData() or 120)
        self._trigger_post_seconds = int(self.sb_trigger_post.value())
        self._trigger_last_value = None
        self._trigger_armed = False
        self.lbl_trigger_status.setText("Nicht scharf")
        self.lbl_trigger_status.setStyleSheet("color: gray; font-weight: bold;")
        self.btn_trigger_arm.setText("Trigger scharf schalten")
        self.btn_trigger_arm.setEnabled(bool(self._trigger_symbol) and self._recording_status == "RECORDING")
        self._update_control_states()

    def _arm_trigger(self) -> None:
        if self._recording_status != "RECORDING":
            return
        self._trigger_symbol = self.cb_trigger_symbol.currentData()
        self._trigger_edge = self.cb_trigger_edge.currentData() or "rising"
        self._trigger_window_seconds = int(self.cb_trigger_window.currentData() or 120)
        self._trigger_post_seconds = int(self.sb_trigger_post.value())
        if not self._trigger_symbol:
            return
        trigger_state = self.state_model.get(self._trigger_symbol)
        if trigger_state is None or not trigger_state.recording:
            QMessageBox.warning(
                self,
                "Trigger nicht aufgezeichnet",
                "Der Trigger muss in der Tabelle mit 'Aufzeichnen' ausgewählt sein.",
            )
            return
        if self._trigger_armed:
            self._trigger_armed = False
            self._trigger_last_value = None
            self.lbl_trigger_status.setText("Trigger gestoppt")
            self.lbl_trigger_status.setStyleSheet("color: #ef6c00; font-weight: bold;")
            self.btn_trigger_arm.setText("Trigger scharf schalten")
            self._append_sys("[TRIGGER] manuell gestoppt")
            self._update_control_states()
            return
        self._trigger_last_value = None
        self._trigger_armed = True
        self.lbl_trigger_status.setText("SCHARF")
        self.lbl_trigger_status.setStyleSheet("color: #087f23; font-weight: bold;")
        self.btn_trigger_arm.setText("Trigger stoppen")
        self.btn_trigger_arm.setStyleSheet("background-color: #ef6c00; color: white; font-weight: bold;")
        self._append_sys(
            "[TRIGGER] scharf: " + self._trigger_symbol
            + " | Flanke=" + self._trigger_edge
            + " | Rückblick=" + str(self._trigger_window_seconds) + " s"
            + " | Nachlauf=" + str(self._trigger_post_seconds) + " s"
        )
        self._update_control_states()

    def _trigger_matches(self, previous: object, current: object) -> bool:
        if previous is None or not isinstance(current, bool) or not isinstance(previous, bool):
            return False
        rising = not previous and current
        falling = previous and not current
        return ((self._trigger_edge in ("rising", "both") and rising) or
                (self._trigger_edge in ("falling", "both") and falling))

    def _set_color_button_style(self, button: QPushButton, color_name: str) -> None:
        color = QColor(color_name)
        if not color.isValid():
            color = QColor("#4c72b0")
        button.setStyleSheet(
            "QPushButton { background-color: %s; border: 1px solid #59636d; "
            "border-radius: 3px; min-width: 24px; max-width: 34px; }"
            % color.name()
        )
        button.setToolTip("Diagrammfarbe: " + color.name().upper())

    def _populate_table(self, var_states: list) -> None:
        self.var_table.setSortingEnabled(False)
        self.var_table.setRowCount(0)
        for vs in var_states:
            row = self.var_table.rowCount()
            self.var_table.insertRow(row)
            self.var_table.setItem(row, 0, QTableWidgetItem(vs.symbol))
            self.var_table.setItem(row, 1, QTableWidgetItem(vs.data_type))
            self.var_table.setItem(row, 2, QTableWidgetItem(vs.tc_type))
            self.var_table.setItem(row, 3, QTableWidgetItem(vs.comment))

            color_button = QPushButton()
            self._set_color_button_style(color_button, vs.plot_color)
            color_button.setEnabled(vs.supported)
            color_button.clicked.connect(
                lambda _checked=False, symbol=vs.symbol: self._choose_plot_color(symbol)
            )
            color_cell = QWidget()
            color_layout = QHBoxLayout(color_cell)
            color_layout.addWidget(color_button)
            color_layout.setAlignment(Qt.AlignCenter)
            color_layout.setContentsMargins(0, 0, 0, 0)
            self.var_table.setCellWidget(row, 4, color_cell)

            cb = QCheckBox()
            cb.setChecked(bool(vs.recording))
            if not vs.supported:
                cb.setEnabled(False)
                cb.setToolTip("Komplexer oder unbekannter Typ - nicht unterstützt")
            cb.stateChanged.connect(
                lambda state, symbol=vs.symbol: self._on_recording_checkbox_changed(symbol, state)
            )
            cell_widget = QWidget()
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.addWidget(cb)
            cell_layout.setAlignment(Qt.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            self.var_table.setCellWidget(row, 5, cell_widget)

            val_item = QTableWidgetItem("-")
            if not vs.supported:
                val_item.setForeground(QColor("gray"))
                val_item.setText("(nicht unterstützt)")
            self.var_table.setItem(row, 6, val_item)
        self.var_table.setSortingEnabled(True)
        self._apply_filter()

    def _choose_plot_color(self, symbol: str) -> None:
        if self._recording_status in ("STARTING", "RECORDING", "STOPPING"):
            return
        state = self.state_model.get(symbol)
        if state is None:
            return
        selected = QColorDialog.getColor(QColor(state.plot_color), self, "Diagrammfarbe auswählen")
        if not selected.isValid():
            return
        self.state_model.set_plot_color(symbol, selected.name())
        for row in range(self.var_table.rowCount()):
            item = self.var_table.item(row, 0)
            if item and item.text() == symbol:
                cell = self.var_table.cellWidget(row, 4)
                if cell:
                    button = cell.findChild(QPushButton)
                    if button:
                        self._set_color_button_style(button, selected.name())
                break
        self._refresh_timeline()
        self._append_sys("[DIAGRAMM] Farbe geändert: " + symbol + " = " + selected.name().upper())

    def _on_recording_checkbox_changed(self, symbol: str, state: int) -> None:
        self.state_model.set_recording(symbol, state == Qt.Checked)
        self._update_control_states()

    def _sync_selection_from_table(self) -> None:
        for row in range(self.var_table.rowCount()):
            sym_item = self.var_table.item(row, 0)
            if sym_item is None:
                continue
            self.state_model.set_recording(
                sym_item.text(), self._get_checkbox_state(row, 5)
            )

    def _get_checkbox_state(self, row: int, col: int) -> bool:
        cell = self.var_table.cellWidget(row, col)
        if cell is None:
            return False
        cb = cell.findChild(QCheckBox)
        return cb.isChecked() if cb else False

    def _apply_filter(self) -> None:
        text = self.le_filter.text().lower()
        for row in range(self.var_table.rowCount()):
            item = self.var_table.item(row, 0)
            if item:
                self.var_table.setRowHidden(row, text not in item.text().lower())

    # ------------------------------------------------------------------
    # Aufzeichnung
    # ------------------------------------------------------------------

    def _on_timeline_window_changed(self, index: int) -> None:
        value = self.cb_timeline_window.itemData(index)
        if value is None:
            return
        self._timeline_window_seconds = int(value)
        self._refresh_timeline()
        self._append_sys(
            "[DIAGRAMM] Anzeigezeitfenster: "
            + self.cb_timeline_window.currentText()
        )

    def _timeline_current_end(self) -> datetime:
        """Liefert den Live- oder eingefrorenen Endzeitpunkt des Diagramms."""
        if self._recording_status in ("STARTING", "RECORDING"):
            self._timeline_end = datetime.now()
        elif self._timeline_end is None:
            # Beim initialen Anzeigen ohne laufende Aufzeichnung nicht ständig
            # weiterlaufen: vorhandene Historie ist der feste Bezugspunkt.
            entries = self.history_model.get_window(None, None)
            self._timeline_end = max(
                (entry.timestamp for entry in entries),
                default=datetime.now(),
            )
        return self._timeline_end

    def _toggle_recording(self) -> None:
        if self._recording_status in ("STARTING", "RECORDING") or self._recording_worker_active:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        if not self.ads_client or not self.ads_client.connected:
            return
        if self._recording_worker_active or self._recording_status in ("STARTING", "RECORDING", "STOPPING"):
            return
        self._sync_selection_from_table()
        selected = [v for v in self.state_model.get_recorded_symbols() if v.supported]
        if not selected:
            QMessageBox.information(
                self, "Keine Auswahl", "Bitte mindestens ein unterstütztes Symbol mit 'Aufzeichnen' auswählen."
            )
            return
        self._recording_generation += 1
        run_id = self._recording_generation
        self._recording_status = "STARTING"
        self._recording_error = ""
        self._timeline_end = datetime.now()
        self._recording_worker_active = True
        self._update_control_states()
        self.ads_client.stop_all_notifications()
        self._last_values.clear()
        self._trigger_last_value = None
        self._append_sys("[AUFZEICHNUNG] Start wird vorbereitet")

        def _worker():
            failed = []
            for vs in selected:
                if run_id != self._recording_generation:
                    self.signals.status_message.emit(f"__RECORDING_CANCELLED__{run_id}")
                    return
                value, ok, err = self.ads_client.read_value(vs.symbol, vs.data_type)
                if ok:
                    # Initialwerte sind echte ADS-Werte; der ADS-Client liefert hier
                    # den Zeitpunkt der UI-Zustellung, nicht einen künstlichen Wert.
                    self.signals.value_updated.emit(vs.symbol, value, datetime.now())
                else:
                    failed.append(vs.symbol + ": " + err)
                    self.signals.log_message.emit("[LESEN-FEHLER] " + vs.symbol + ": " + err)
                    continue
                if run_id != self._recording_generation:
                    self.signals.status_message.emit(f"__RECORDING_CANCELLED__{run_id}")
                    return
                ok2, err2 = self.ads_client.start_notification(vs.symbol, vs.data_type)
                if ok2:
                    self.signals.log_message.emit("[NOTIFICATION] " + vs.symbol + " registriert")
                else:
                    failed.append(vs.symbol + ": " + err2)
                    self.signals.log_message.emit("[NOTIFICATION-FEHLER] " + vs.symbol + ": " + err2)
            self.signals.status_message.emit(
                f"__RECORDING_DONE__{run_id}" + ("|" + "\n".join(failed) if failed else "")
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _stop_recording(self) -> None:
        was_active = self._recording_status != "STOPPED" or self._recording_worker_active
        if was_active:
            # Danach darf _refresh_timeline() nicht mehr datetime.now() als
            # Endpunkt verwenden. Das Diagramm bleibt visuell stehen.
            self._timeline_end = datetime.now()
        self._recording_generation += 1
        if self._recording_worker_active:
            self._recording_status = "STOPPING"
        if self.ads_client:
            self.ads_client.stop_all_notifications()
        self._recording_status = "STOPPED"
        self._trigger_armed = False
        self._trigger_last_value = None
        if was_active:
            self.lbl_trigger_status.setText("Aufzeichnung gestoppt")
            self.lbl_trigger_status.setStyleSheet("color: #666; font-weight: bold;")
            self._append_sys("[AUFZEICHNUNG] gestoppt; Historie bleibt erhalten")
        self._update_control_states()

    def _on_recording_worker_status(self, message: str) -> None:
        if message.startswith("__RECORDING_CANCELLED__"):
            run_id = int(message[len("__RECORDING_CANCELLED__"):])
            if run_id == self._recording_generation - 1 or run_id == self._recording_generation:
                self._recording_worker_active = False
                self._append_sys("[AUFZEICHNUNG] Start abgebrochen")
                self._update_control_states()
            return
        if not message.startswith("__RECORDING_DONE__"):
            self.status_bar.showMessage(message)
            return
        payload = message[len("__RECORDING_DONE__"):]
        run_text, separator, details = payload.partition("|")
        run_id = int(run_text)
        if run_id != self._recording_generation:
            return
        self._recording_worker_active = False
        if separator:
            self._recording_status = "ERROR"
            self._recording_error = details
            self._append_sys("[AUFZEICHNUNG-FEHLER] " + self._recording_error)
        else:
            self._recording_status = "RECORDING"
            self._append_sys("[AUFZEICHNUNG] läuft")
        self._update_control_states()

    def _update_control_states(self) -> None:
        connected = bool(self.ads_client and self.ads_client.connected)
        has_symbols = self.var_table.rowCount() > 0
        active = self._recording_status in ("STARTING", "RECORDING", "STOPPING")
        is_recording = self._recording_status == "RECORDING"

        if self._recording_status == "STARTING":
            self.lbl_recording_status.setText("Aufzeichnung: wird gestartet ...")
            self.lbl_recording_status.setStyleSheet("color: #1565c0; font-weight: bold;")
            self.btn_recording.setText("Aufzeichnung wird gestartet ...")
            self.btn_recording.setEnabled(False)
            self.btn_recording.setStyleSheet("background-color: #1565c0; color: white; font-weight: bold;")
        elif self._recording_status == "RECORDING":
            self.lbl_recording_status.setText("Aufzeichnung: AKTIV")
            self.lbl_recording_status.setStyleSheet("color: #087f23; font-weight: bold;")
            self.btn_recording.setText("Aufzeichnung stoppen")
            self.btn_recording.setEnabled(True)
            self.btn_recording.setStyleSheet("background-color: #c62828; color: white; font-weight: bold;")
        elif self._recording_status == "STOPPING":
            self.lbl_recording_status.setText("Aufzeichnung: wird gestoppt ...")
            self.lbl_recording_status.setStyleSheet("color: #ef6c00; font-weight: bold;")
            self.btn_recording.setText("Aufzeichnung wird gestoppt ...")
            self.btn_recording.setEnabled(False)
            self.btn_recording.setStyleSheet("background-color: #ef6c00; color: white; font-weight: bold;")
        elif self._recording_status == "ERROR":
            self.lbl_recording_status.setText("Aufzeichnung: FEHLER")
            self.lbl_recording_status.setStyleSheet("color: #c62828; font-weight: bold;")
            self.btn_recording.setText("Aufzeichnung erneut starten")
            self.btn_recording.setEnabled(connected and has_symbols and not self._recording_worker_active)
            self.btn_recording.setStyleSheet("background-color: #ef6c00; color: white; font-weight: bold;")
        else:
            self.lbl_recording_status.setText("Aufzeichnung: gestoppt")
            self.lbl_recording_status.setStyleSheet("color: #666; font-weight: bold;")
            self.btn_recording.setText("Aufzeichnung starten")
            self.btn_recording.setEnabled(connected and has_symbols and not self._recording_worker_active)
            self.btn_recording.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")

        if hasattr(self, "lbl_timeline_info"):
            mode = "live" if self._recording_status in ("STARTING", "RECORDING") else "eingefroren"
            self.lbl_timeline_info.setText(
                "Diagramm: rollierend | " + mode
                + " | Fenster: " + self.cb_timeline_window.currentText()
            )

        # Auswahl und Farben bleiben während einer laufenden Aufzeichnung fest.
        for row in range(self.var_table.rowCount()):
            symbol_item = self.var_table.item(row, 0)
            if symbol_item is None:
                continue
            state = self.state_model.get(symbol_item.text())
            if state is None:
                continue
            self.var_table.setRowHidden(row, active and not state.recording)
            check_cell = self.var_table.cellWidget(row, 5)
            if check_cell:
                checkbox = check_cell.findChild(QCheckBox)
                if checkbox:
                    checkbox.setEnabled(not active and state.supported)
            color_cell = self.var_table.cellWidget(row, 4)
            if color_cell:
                color_button = color_cell.findChild(QPushButton)
                if color_button:
                    color_button.setEnabled(not active and state.supported)

        has_trigger = bool(self.cb_trigger_symbol.currentData())
        self.btn_trigger_arm.setEnabled(
            connected and is_recording and has_trigger and not self._trigger_analysis_running
        )
        if not self._trigger_armed and has_trigger and is_recording:
            self.btn_trigger_arm.setText("Trigger scharf schalten")
            self.btn_trigger_arm.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")

    def _ads_value_callback(self, symbol: str, value: object, ts: datetime) -> None:
        self.signals.value_updated.emit(symbol, value, ts)

    def _on_value_updated(self, symbol: str, value: object, ts: object) -> None:
        if isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = datetime.now()
        has_previous = symbol in self._last_values
        prev = self._last_values.get(symbol)
        changed = (not has_previous) or (type(prev) is not type(value)) or (prev != value)
        self._last_values[symbol] = value
        if self._recording_status not in ("STARTING", "RECORDING"):
            return
        self.state_model.update_value(symbol, value, timestamp)
        vs = self.state_model.get(symbol)
        if vs is None:
            return

        if symbol == self._trigger_symbol and isinstance(value, bool):
            if self._trigger_last_value is None:
                self._trigger_last_value = value
            elif self._trigger_armed and self._trigger_matches(self._trigger_last_value, value):
                self._trigger_armed = False
                self.lbl_trigger_status.setText("AUSGELÖST - Analyse läuft")
                self.lbl_trigger_status.setStyleSheet("color: #1565c0; font-weight: bold;")
                self.btn_trigger_arm.setText("Trigger erneut scharf schalten")
                self.btn_trigger_arm.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
                self._append_sys("[TRIGGER] ausgelöst durch " + symbol)
                self._pending_trigger_timestamp = timestamp
                self.lbl_trigger_status.setText("AUSGELÖST - Nachlauf läuft")
                self.lbl_trigger_status.setStyleSheet("color: #ef6c00; font-weight: bold;")
                QTimer.singleShot(
                    self._trigger_post_seconds * 1000,
                    lambda ts=timestamp: self._start_trigger_analysis(ts),
                )
            self._trigger_last_value = value

        # Jede aufgezeichnete Variable ist zugleich Anzeige-, Historie-, KI-
        # und Notification-Auswahl. Nicht ausgewählte Symbole bleiben außen vor.
        if changed and vs.recording:
            # Den Zeitstempel aus dem ADS-Callback verwenden. Dadurch bleibt
            # der Trigger-Rueckblick auch bei Qt-Queue-/Thread-Verzoegerungen
            # zeitlich korrekt.
            self.history_model.add(
                symbol,
                vs.data_type,
                value,
                timestamp=timestamp,
            )

        if changed and vs.recording:

            ts_str = timestamp.strftime("%H:%M:%S.%f")[:-3]
            prev_str = str(prev) if prev is not None else "?"
            self.te_log.appendPlainText(
                "[" + ts_str + "] " + symbol + " = " + str(value) + " (vorher: " + prev_str + ")"
            )

    def _start_trigger_analysis(self, trigger_ts: datetime) -> None:
        if self._trigger_analysis_running:
            return
        self._trigger_analysis_running = True
        window_from = trigger_ts - timedelta(seconds=self._trigger_window_seconds)
        # Nach dem Trigger laufen die ADS-Notifications weiter. Der Endzeitpunkt
        # ist deshalb der tatsächliche Analysezeitpunkt nach dem Nachlauf.
        window_to = datetime.now()
        self.lbl_trigger_status.setText("AUSGELÖST - Analyse läuft")
        self.lbl_trigger_status.setStyleSheet("color: #1565c0; font-weight: bold;")
        ai_vars = self.state_model.get_recorded_symbols()
        history = self.history_model.get_window(
            from_dt=window_from,
            to_dt=window_to,
            symbols=[v.symbol for v in ai_vars],
        )
        system_prompt = self.te_prompt.toPlainText().strip()
        ads_connected = self.ads_client.connected if self.ads_client else False
        user_message = build_user_message(
            ai_variables=ai_vars,
            history=history,
            from_dt=window_from,
            to_dt=window_to,
            ads_connected=ads_connected,
        )
        history_symbols = sorted({entry.symbol for entry in history})
        self._append_sys(
            "[TRIGGER] Snapshot erstellt | Historie: " + str(len(history))
            + " Einträge | Symbole: " + (", ".join(history_symbols) if history_symbols else "keine")
            + " | Zeitraum: " + window_from.strftime("%H:%M:%S.%f")[:-3]
            + " bis " + window_to.strftime("%H:%M:%S.%f")[:-3]
            + " | Notifications bleiben aktiv"
        )
        if not history:
            self._append_sys(
                "[TRIGGER-WARNUNG] Keine Historieneinträge im Analysefenster. "
                "Prüfe KI-Auswahl, Auswahl anwenden und Notification-Status."
            )
        self._set_prompt_preview(
            system_prompt=system_prompt,
            user_message=user_message,
            metadata={
                "trigger_symbol": self._trigger_symbol or "-",
                "trigger_timestamp": trigger_ts,
                "window_from": window_from,
                "window_to": window_to,
                "history_count": len(history),
                "post_seconds": self._trigger_post_seconds,
            },
        )
        self._append_sys("[TRIGGER] Prompt-Vorschau aktualisiert")
        self.te_result.setMarkdown("*Automatische Triggeranalyse läuft ...*")
        self.btn_analyze.setEnabled(False)
        self._update_control_states()

        llm = self.llm_client or LmStudioClient(
            base_url=self.le_llm_url.text().strip() or "http://127.0.0.1:1234/v1",
            model=self.le_model.text().strip(),
            timeout_seconds=float(self.cfg.get("llm", {}).get("timeout_seconds", 60.0)),
            temperature=float(self.cfg.get("llm", {}).get("temperature", 0.1)),
            max_tokens=int(self.cfg.get("llm", {}).get("max_tokens", 1200)),
            context_length=int(self.cfg.get("llm", {}).get("context_length", 4096)),
            top_p=float(self.cfg.get("llm", {}).get("top_p", 0.95)),
            top_k=int(self.cfg.get("llm", {}).get("top_k", 40)),
            repeat_penalty=float(self.cfg.get("llm", {}).get("repeat_penalty", 1.1)),
            stream=bool(self.cfg.get("llm", {}).get("stream", False)),
        )
        self.llm_client = llm

        def _worker():
            answer, ok = llm.analyze(system_prompt, user_message)
            self.signals.analysis_result.emit(answer, ok)

        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_table(self) -> None:
        for row in range(self.var_table.rowCount()):
            item = self.var_table.item(row, 0)
            if item is None:
                continue
            symbol = item.text()
            vs = self.state_model.get(symbol)
            if vs is None:
                continue
            val_item = self.var_table.item(row, 6)
            if val_item is None:
                continue
            if not vs.recording:
                val_item.setText("-")
                val_item.setBackground(QColor("#f2f2f2"))
                val_item.setForeground(QColor("#777777"))
                continue
            if not vs.valid or vs.value is None:
                val_item.setText("(noch nicht gelesen)")
                val_item.setBackground(QColor("#fff3cd"))
                val_item.setForeground(QColor("#7a5b00"))
                continue
            ts_str = vs.timestamp.strftime("%H:%M:%S.%f")[:-3] if vs.timestamp else "-"
            val_item.setText(str(vs.value) + " [" + ts_str + "]")
            val_item.setForeground(QColor("#17212b"))
            if vs.data_type.upper() == "BOOL" and isinstance(vs.value, bool):
                if vs.value:
                    val_item.setBackground(QColor("#b7e4c7"))
                else:
                    val_item.setBackground(QColor("#eeeeee"))
            else:
                val_item.setBackground(QColor("#ffffff"))

    def _refresh_timeline(self) -> None:
        """Aktualisiert nur das rollierende/fixierte Diagrammfenster.

        Die HistoryModel-Einträge werden nicht gelöscht. Für die Darstellung
        werden lediglich Einträge außerhalb des gewählten Zeitfensters
        herausgefiltert.
        """
        recorded = [
            v for v in self.state_model.get_recorded_symbols()
            if v.data_type.upper() == "BOOL"
        ]
        end = self._timeline_current_end()
        start = end - timedelta(seconds=self._timeline_window_seconds)
        symbols = [v.symbol for v in recorded]
        history = self.history_model.get_window(
            start, end, symbols=symbols
        )
        rows = []
        for state in recorded:
            entries = [entry for entry in history if entry.symbol == state.symbol]
            rows.append((state.symbol, state.plot_color, entries))
        self.timeline_chart.set_data(rows, from_dt=start, to_dt=end)
        if hasattr(self, "lbl_timeline_info"):
            mode = "live" if self._recording_status in ("STARTING", "RECORDING") else "eingefroren"
            self.lbl_timeline_info.setText(
                "Diagramm: rollierend | " + mode
                + " | Fenster: " + self.cb_timeline_window.currentText()
            )

    # ------------------------------------------------------------------
    # Prompt-Vorschau
    # ------------------------------------------------------------------

    def _set_prompt_preview(self, system_prompt: str, user_message: str, metadata: Optional[dict] = None) -> None:
        meta_lines = []
        if metadata:
            def fmt(value):
                return value.isoformat(timespec="milliseconds") if isinstance(value, datetime) else str(value)
            meta_lines = [
                "========== ANALYSE-METADATEN ==========",
                "Trigger-Variable: " + str(metadata.get("trigger_symbol", "-")),
                "Triggerzeitpunkt: " + fmt(metadata.get("trigger_timestamp", "-")),
                "Rückblick ab: " + fmt(metadata.get("window_from", "-")),
                "Analyse bis: " + fmt(metadata.get("window_to", "-")),
                "Nachlauf: " + str(metadata.get("post_seconds", "-")) + " s",
                "Verlaufseinträge: " + str(metadata.get("history_count", 0)),
                "",
            ]
            if metadata.get("history_count", 0) == 0:
                meta_lines += [
                    "Keine Verlaufsdaten im automatischen Analysefenster.",
                    "Bitte prüfen:",
                    "- Aufzeichnung gestartet?",
                    "- Variablen ausgewählt?",
                    "- Notifications registriert?",
                    "- Zeitfenster ausreichend groß?",
                    "",
                ]
        preview = "\n".join(meta_lines) + (
            "========== SYSTEM-PROMPT ==========\n" + system_prompt
            + "\n\n========== USER-NACHRICHT (Daten) ==========\n" + user_message
        )
        self.te_prompt_preview.setPlainText(preview)

    def _update_prompt_preview(self) -> None:
        from_dt = self.dt_from.dateTime().toPython()
        to_dt = self.dt_to.dateTime().toPython()
        recorded_vars = self.state_model.get_recorded_symbols()
        history = self.history_model.get_window(
            from_dt=from_dt,
            to_dt=to_dt,
            symbols=[v.symbol for v in recorded_vars],
        )
        ads_connected = self.ads_client.connected if self.ads_client else False
        system_prompt = self.te_prompt.toPlainText().strip()
        user_message = build_user_message(
            ai_variables=recorded_vars,
            history=history,
            from_dt=from_dt,
            to_dt=to_dt,
            ads_connected=ads_connected,
        )
        self._set_prompt_preview(
            system_prompt,
            user_message,
            {"history_count": len(history), "window_from": from_dt, "window_to": to_dt},
        )

    # ------------------------------------------------------------------
    # Analyse
    # ------------------------------------------------------------------

    def _on_analyze(self) -> None:
        llm_url = self.le_llm_url.text().strip() or "http://127.0.0.1:1234/v1"
        model = self.le_model.text().strip()
        system_prompt = self.te_prompt.toPlainText().strip()
        self.llm_client = LmStudioClient(
            base_url=llm_url,
            model=model,
            timeout_seconds=float(self.cfg.get("llm", {}).get("timeout_seconds", 60.0)),
            temperature=float(self.cfg.get("llm", {}).get("temperature", 0.1)),
            max_tokens=int(self.cfg.get("llm", {}).get("max_tokens", 1200)),
            context_length=int(self.cfg.get("llm", {}).get("context_length", 4096)),
            top_p=float(self.cfg.get("llm", {}).get("top_p", 0.95)),
            top_k=int(self.cfg.get("llm", {}).get("top_k", 40)),
            repeat_penalty=float(self.cfg.get("llm", {}).get("repeat_penalty", 1.1)),
            stream=bool(self.cfg.get("llm", {}).get("stream", False)),
        )
        from_dt = self.dt_from.dateTime().toPython()
        to_dt = self.dt_to.dateTime().toPython()
        ai_vars = self.state_model.get_recorded_symbols()
        history = self.history_model.get_window(
            from_dt=from_dt,
            to_dt=to_dt,
            symbols=[v.symbol for v in ai_vars],
        )
        ads_connected = self.ads_client.connected if self.ads_client else False
        user_message = build_user_message(
            ai_variables=ai_vars,
            history=history,
            from_dt=from_dt,
            to_dt=to_dt,
            ads_connected=ads_connected,
        )
        self._update_prompt_preview()
        self._append_sys(
            "[LLM] Analyse gestartet | KI-Symbole: "
            + str(len(ai_vars))
            + " | Historieneintraege: "
            + str(len(history))
        )
        self.btn_analyze.setEnabled(False)
        self.te_result.setMarkdown("*Analyse läuft ...*")

        def _worker():
            answer, ok = self.llm_client.analyze(system_prompt, user_message)
            self.signals.analysis_result.emit(answer, ok)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_analysis_result(self, answer: str, ok: bool) -> None:
        self.btn_analyze.setEnabled(True)
        self._trigger_analysis_running = False
        if ok and answer.strip():
            self.te_result.setMarkdown(answer)
        else:
            self.te_result.setMarkdown(
                "### Analyse konnte nicht dargestellt werden\\n\\n" + answer
            )
        ts = datetime.now().strftime("%d.%m.%Y %H:%M:%S.%f")[:-3]
        self.lbl_last_analysis.setText("Letzte Analyse: " + ts)
        if ok:
            self._append_sys("[LLM] Antwort empfangen (" + str(len(answer)) + " Zeichen)")
        else:
            self._append_sys("[LLM-FEHLER] " + answer[:120])

    def _on_check_llm(self) -> None:
        url = self.le_llm_url.text().strip() or "http://127.0.0.1:1234/v1"
        client = LmStudioClient(base_url=url)
        ok, msg = client.check_connection()
        self._append_sys("[LLM-CHECK] " + msg)
        if ok:
            QMessageBox.information(self, "LM Studio", msg)
        else:
            QMessageBox.warning(self, "LM Studio nicht erreichbar", msg)

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    def _on_max_entries_changed(self, value: int) -> None:
        self.history_model.max_entries = value
        self._append_sys("Max. Logeintraege geaendert: " + str(value))

    def _append_sys(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.te_sys.appendPlainText("[" + ts + "] " + message)
        logger.info(message)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.cfg, self)
        if dialog.exec() == QDialog.Accepted:
            self.cfg = dialog.values()
            save_config(self.cfg)
            self.history_model.max_entries = int(
                self.cfg.get("logging", {}).get("max_entries", 5000)
            )
            self.te_prompt.setPlainText(self.cfg.get("llm", {}).get("system_prompt", ""))
            self.le_llm_url.setText(
                self.cfg.get("llm", {}).get("base_url", "http://127.0.0.1:1234/v1")
            )
            self.le_model.setText(self.cfg.get("llm", {}).get("model", ""))
            self.sb_max_entries.setValue(self.history_model.max_entries)
            self._append_sys("[CONFIG] Einstellungen gespeichert")

    def _collect_config_from_ui(self) -> dict:
        return self.cfg

    def _save_config_from_ui(self) -> None:
        save_config(self.cfg)
        self._append_sys("[CONFIG] Konfiguration gespeichert")

    def _load_config_from_file(self) -> None:
        self.cfg = load_config()
        self._apply_config_to_ui()
        self._append_sys("[CONFIG] Konfiguration geladen")

    def _load_defaults_to_ui(self) -> None:
        from app.config.settings import _default_config
        self.cfg = _default_config()
        self._apply_config_to_ui()
        self._append_sys("[CONFIG] Standardwerte geladen")

    def closeEvent(self, event) -> None:
        self._stop_recording()
        if self.ads_client:
            self.ads_client.disconnect()
        event.accept()
