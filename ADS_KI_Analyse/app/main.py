"""
main.py - Einstiegspunkt der ADS_KI_Analyse-Anwendung.
"""
import logging
import sys
from pathlib import Path

# Projektpfad zum sys.path hinzufuegen
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import load_config

# Logging einrichten
cfg = load_config()
log_file = cfg.get("logging", {}).get("file", "logs/app.log")
Path(log_file).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)
logger.info("ADS_KI_Analyse wird gestartet")

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
except ImportError as e:
    print(f"FEHLER: PySide6 nicht gefunden: {e}")
    print("Bitte INSTALL.bat ausfuehren.")
    sys.exit(1)

from app.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ADS_KI_Analyse")
    app.setOrganizationName("Beckhoff TwinCAT Monitor")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
