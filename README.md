# ADS_KI_Analyse – Aufzeichnung/UI-Implementierung

Diese Referenzimplementierung setzt das Umsetzungskonzept für eine eindeutige Aufzeichnung um:

- ein Auswahlhaken `Aufzeichnen` statt `Anzeigen`/`Loggen`/`KI`,
- zentrale Zustände `STOPPED`, `STARTING`, `RECORDING`, `ERROR`,
- explizite Schaltflächen zum Starten und Stoppen,
- Notifications nur für aufgezeichnete, unterstützte Symbole,
- Historie nur bei echten ADS-Wertänderungen,
- ADS-Zeitstempel bleiben bis zur nächsten tatsächlichen Änderung erhalten,
- BOOL-Darstellung ausschließlich als UI-Hilfe,
- Trigger kann nach dem Scharfschalten über dieselbe Schaltfläche gestoppt werden,
- automatische Triggeranalyse aktualisiert dieselbe Prompt-Vorschau wie die manuelle Analyse,
- keine Simulation, kein ADS-Schreiben und kein Cloud-Endpunkt.

## Integration

Die Dateien unter `app/` ersetzen die gleichnamigen Repository-Dateien. Der Patch für `ads_client.py` übernimmt den von pyads gelieferten Notification-Zeitstempel. Danach können die Tests mit `pytest -q` ausgeführt werden.

Die Implementierung setzt voraus, dass das Repository weiterhin die vorhandenen `AdsClient`, `LmStudioClient`, `settings.py` und den bestehenden Anwendungseinstiegspunkt verwendet.
