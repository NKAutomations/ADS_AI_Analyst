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
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont, QColor
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
)

from app.ads.ads_client import AdsClient, AdsSymbolInfo
from app.config.settings import load_config, save_config
from app.domain.history_model import HistoryModel
from app.domain.state_model import StateModel, VariableState
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
        self._build_ui()
        self._connect_signals()
        self._apply_config_to_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_table)
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
        self.btn_apply = QPushButton("Auswahl anwenden und Notifications starten")
        self.btn_apply.setEnabled(False)
        btn_row.addWidget(self.btn_load_symbols)
        btn_row.addWidget(self.btn_apply)
        layout.addLayout(btn_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.le_filter = QLineEdit()
        self.le_filter.setPlaceholderText("Symbolname filtern...")
        self.le_filter.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.le_filter)
        layout.addLayout(filter_row)

        self.var_table = QTableWidget()
        self.var_table.setColumnCount(8)
        self.var_table.setHorizontalHeaderLabels(
            ["Symbol", "Typ", "TC-Typ", "Kommentar", "Anzeigen", "Loggen", "KI", "Wert"]
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
        self.te_result = QPlainTextEdit()
        self.te_result.setReadOnly(True)
        self.te_result.setPlaceholderText("Hier erscheint die KI-Analyse...")
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
            "Nur Änderungen von Variablen mit gesetztem 'Loggen'-Haken werden hier angezeigt."
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
        tabs.addTab(log_widget, "Protokoll (geloggte Änderungen)")

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

        return tabs

    # ------------------------------------------------------------------
    # Signale verbinden
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.btn_connect.clicked.connect(self._on_connect)
        self.btn_disconnect.clicked.connect(self._on_disconnect)
        self.btn_load_symbols.clicked.connect(self._on_load_symbols)
        self.btn_apply.clicked.connect(self._on_apply_selection)
        self.btn_analyze.clicked.connect(self._on_analyze)
        self.btn_check_llm.clicked.connect(self._on_check_llm)
        self.btn_settings.clicked.connect(self._open_settings)
        self.signals.log_message.connect(self._append_sys)
        self.signals.status_message.connect(self.status_bar.showMessage)
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
            self.lbl_conn_status.setText("Verbunden")
            self.lbl_conn_status.setStyleSheet("color: green; font-weight: bold;")
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
        if self.ads_client:
            self.ads_client.disconnect()
        self.lbl_conn_status.setText("Getrennt")
        self.lbl_conn_status.setStyleSheet("color: gray; font-weight: bold;")
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.btn_load_symbols.setEnabled(False)
        self.btn_apply.setEnabled(False)
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
        for sym in symbols:
            vs = VariableState(
                symbol=sym.name,
                data_type=sym.data_type,
                tc_type=sym.tc_type,
                comment=sym.comment,
                supported=sym.supported,
            )
            var_states.append(vs)
        self.state_model.set_symbols(var_states)
        self._populate_table(var_states)
        self.btn_apply.setEnabled(True)
        self._append_sys(str(len(symbols)) + " Symbole geladen.")

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
            for col, attr in [(4, "show"), (5, "log"), (6, "ai")]:
                cb = QCheckBox()
                cb.setChecked(getattr(vs, attr) if attr != "show" else False)
                if not vs.supported and col in (5, 6):
                    cb.setEnabled(False)
                    cb.setToolTip("Komplexer Typ - nicht unterstuetzt")
                cb.stateChanged.connect(
                    lambda state, s=vs.symbol, c=col: self._on_checkbox_changed(s, c, state)
                )
                cell_widget = QWidget()
                cell_layout = QHBoxLayout(cell_widget)
                cell_layout.addWidget(cb)
                cell_layout.setAlignment(Qt.AlignCenter)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                self.var_table.setCellWidget(row, col, cell_widget)
            val_item = QTableWidgetItem("-")
            if not vs.supported:
                val_item.setForeground(QColor("gray"))
                val_item.setText("(nicht unterstuetzt)")
            self.var_table.setItem(row, 7, val_item)
        self.var_table.setSortingEnabled(True)
        self._apply_filter()

    def _on_checkbox_changed(self, symbol: str, col: int, state: int) -> None:
        vs = self.state_model.get(symbol)
        if vs is None:
            return
        checked = state == Qt.Checked
        if col == 4:
            self.state_model.set_selection(symbol, checked, vs.log, vs.ai)
        elif col == 5:
            self.state_model.set_selection(symbol, vs.show, checked, vs.ai)
        elif col == 6:
            self.state_model.set_selection(symbol, vs.show, vs.log, checked)

    def _apply_filter(self) -> None:
        text = self.le_filter.text().lower()
        for row in range(self.var_table.rowCount()):
            item = self.var_table.item(row, 0)
            if item:
                self.var_table.setRowHidden(row, text not in item.text().lower())

    # ------------------------------------------------------------------
    # Notifications starten
    # ------------------------------------------------------------------

    def _sync_selection_from_table(self) -> None:
        for row in range(self.var_table.rowCount()):
            sym_item = self.var_table.item(row, 0)
            if sym_item is None:
                continue
            symbol = sym_item.text()
            show = self._get_checkbox_state(row, 4)
            log = self._get_checkbox_state(row, 5)
            ai = self._get_checkbox_state(row, 6)
            self.state_model.set_selection(symbol, show, log, ai)

    def _get_checkbox_state(self, row: int, col: int) -> bool:
        cell = self.var_table.cellWidget(row, col)
        if cell is None:
            return False
        cb = cell.findChild(QCheckBox)
        return cb.isChecked() if cb else False

    def _on_apply_selection(self) -> None:
        if not self.ads_client or not self.ads_client.connected:
            return
        self._sync_selection_from_table()
        self.ads_client.stop_all_notifications()
        self._last_values.clear()
        self._append_sys("Notifications gestoppt. Starte neu...")
        all_vars = self.state_model.get_all()
        to_monitor = [v for v in all_vars if (v.show or v.log or v.ai) and v.supported]
        log_syms = [v.symbol for v in to_monitor if v.log]
        ai_syms = [v.symbol for v in to_monitor if v.ai]
        self._append_sys(
            "Loggen: " + str(len(log_syms)) + " Symbole | KI: " + str(len(ai_syms)) + " Symbole"
        )

        def _worker():
            for vs in to_monitor:
                value, ok, err = self.ads_client.read_value(vs.symbol, vs.data_type)
                if ok:
                    self.signals.value_updated.emit(vs.symbol, value, datetime.now())
                else:
                    self.signals.log_message.emit("[LESEN-FEHLER] " + vs.symbol + ": " + err)
                ok2, err2 = self.ads_client.start_notification(vs.symbol, vs.data_type)
                if ok2:
                    self.signals.log_message.emit("[NOTIFICATION] " + vs.symbol + " registriert")
                else:
                    self.signals.log_message.emit(
                        "[NOTIFICATION-FEHLER] " + vs.symbol + ": " + err2
                    )

        threading.Thread(target=_worker, daemon=True).start()

    def _ads_value_callback(self, symbol: str, value: object, ts: datetime) -> None:
        self.signals.value_updated.emit(symbol, value, ts)

    def _on_value_updated(self, symbol: str, value: object, ts: object) -> None:
        if isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = datetime.now()
        prev = self._last_values.get(symbol)
        changed = (prev is None) or (str(prev) != str(value))
        self._last_values[symbol] = value
        self.state_model.update_value(symbol, value, timestamp)
        vs = self.state_model.get(symbol)
        if vs is None:
            return
        if changed and vs.log:
            self.history_model.add(symbol, vs.data_type, value)
            ts_str = timestamp.strftime("%H:%M:%S.%f")[:-3]
            prev_str = str(prev) if prev is not None else "?"
            self.te_log.appendPlainText(
                "[" + ts_str + "] " + symbol + " = " + str(value) + " (vorher: " + prev_str + ")"
            )

    def _refresh_table(self) -> None:
        for row in range(self.var_table.rowCount()):
            item = self.var_table.item(row, 0)
            if item is None:
                continue
            symbol = item.text()
            vs = self.state_model.get(symbol)
            if vs is None or not vs.show:
                continue
            val_item = self.var_table.item(row, 7)
            if val_item and vs.value is not None:
                ts_str = vs.timestamp.strftime("%H:%M:%S.%f")[:-3] if vs.timestamp else ""
                val_item.setText(str(vs.value) + " [" + ts_str + "]")

    # ------------------------------------------------------------------
    # Prompt-Vorschau
    # ------------------------------------------------------------------

    def _update_prompt_preview(self) -> None:
        from_dt = self.dt_from.dateTime().toPython()
        to_dt = self.dt_to.dateTime().toPython()
        ai_vars = self.state_model.get_ai_symbols()
        history = self.history_model.get_window(
            from_dt=from_dt,
            to_dt=to_dt,
            symbols=[v.symbol for v in ai_vars],
        )
        ads_connected = self.ads_client.connected if self.ads_client else False
        system_prompt = self.te_prompt.toPlainText().strip()
        user_message = build_user_message(
            ai_variables=ai_vars,
            history=history,
            from_dt=from_dt,
            to_dt=to_dt,
            ads_connected=ads_connected,
        )
        preview = (
            "========== SYSTEM-PROMPT ==========\n"
            + system_prompt
            + "\n\n========== USER-NACHRICHT (Daten) ==========\n"
            + user_message
        )
        self.te_prompt_preview.setPlainText(preview)

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
        ai_vars = self.state_model.get_ai_symbols()
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
        self.te_result.setPlainText("Analyse laeuft...")

        def _worker():
            answer, ok = self.llm_client.analyze(system_prompt, user_message)
            self.signals.analysis_result.emit(answer, ok)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_analysis_result(self, answer: str, ok: bool) -> None:
        self.btn_analyze.setEnabled(True)
        self.te_result.setPlainText(answer)
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
        if self.ads_client:
            self.ads_client.disconnect()
        event.accept()
