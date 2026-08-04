# ADS_KI_Analyse

**Lokale KI-gestützte Analyse einer Beckhoff-TwinCAT-Steuerung über ADS**

> ⚠️ **Hinweis:** Diese Anwendung ist ausschließlich für isolierte Testsysteme vorgesehen und arbeitet in der aktuellen Version vollständig **read-only**. Es werden keine SPS-Variablen geschrieben und keine automatischen Steuerungsaktionen ausgeführt.

---

## Inhaltsverzeichnis

1. [Überblick](#überblick)
2. [Systemvoraussetzungen](#systemvoraussetzungen)
3. [Projektstruktur](#projektstruktur)
4. [Installation](#installation)
5. [ADS-Konfiguration und Routen](#ads-konfiguration-und-routen)
6. [LM Studio einrichten](#lm-studio-einrichten)
7. [Anwendung starten](#anwendung-starten)
8. [Bedienoberfläche](#bedienoberfläche)
9. [Konfigurationsdatei](#konfigurationsdatei)
10. [Unterstützte Datentypen](#unterstützte-datentypen)
11. [Architektur](#architektur)
12. [Tests ausführen](#tests-ausführen)
13. [Bekannte Einschränkungen](#bekannte-einschränkungen)
14. [Sicherheitshinweise und spätere Erweiterbarkeit](#sicherheitshinweise-und-spätere-erweiterbarkeit)

---

## Überblick

`ADS_KI_Analyse` ist eine lokale Desktop-Anwendung (Windows), die:

- eine **ADS-Verbindung** zu einer entfernten Beckhoff-TwinCAT-Runtime herstellt,
- alle verfügbaren **SPS-Symbole** über den integrierten Symbolbrowser ausliest,
- ausgewählte Variablen per **ADS Notifications** live überwacht,
- Wertänderungen in einer **Verlaufshistorie** speichert,
- die ausgewählten Daten strukturiert an ein **lokal laufendes LLM** (LM Studio) übergibt,
- die KI-Antwort verständlich in der Oberfläche anzeigt.

Die Anwendung benötigt **keinen Internetzugang** und sendet keine SPS-Daten an externe Dienste.

```
Benutzeroberfläche (PySide6)
        │
        ▼
Anwendungs- und Dialoglogik (main_window.py)
        │
        ├── LLM-Client (lm_studio_client.py)
        ├── Prompt-Builder (prompt_builder.py)
        ├── Zustandsmodell (state_model.py)
        ├── Verlaufshistorie (history_model.py)
        └── Variablenauswahl (StateModel)
                │
                ▼
        ADS-Client (ads_client.py)
                │
                ▼
        TwinCAT-Runtime (entfernter Rechner, ADS/LAN)
```

---

## Systemvoraussetzungen

### KI-PC (lokaler Rechner)

| Anforderung | Details |
|---|---|
| Betriebssystem | Windows 10 / 11 (64-Bit) |
| Python | 3.11, 3.12 oder 3.13 |
| TwinCAT Engineering | Installiert (für ADS-Treiber und Routing) |
| LM Studio | Lokal installiert und gestartet |
| Netzwerk | LAN-Verbindung zum Runtime-Rechner |

### Runtime-Rechner (SPS)

| Anforderung | Details |
|---|---|
| TwinCAT | TwinCAT 3 Runtime aktiv |
| ADS-Port | Standard: **851** (TwinCAT 3 PLC Runtime 1) |
| ADS-Route | Muss zum KI-PC eingerichtet sein |

---

## Projektstruktur

```
ADS_KI_Analyse/
├── INSTALL.bat              # Installation (venv + Pakete)
├── START_ADS.bat            # Anwendung starten
├── RUN_TESTS.bat            # Tests ausführen
├── OPEN_CONFIG.bat          # config.json im Editor öffnen
├── requirements.txt         # Python-Abhängigkeiten
│
├── config/
│   └── config.json          # Lokale Konfiguration (wird automatisch erstellt)
│
├── logs/
│   └── app.log              # Anwendungsprotokoll
│
├── app/
│   ├── main.py              # Einstiegspunkt
│   │
│   ├── ads/
│   │   ├── ads_client.py        # ADS-Verbindung, Notifications, Symbolbrowser
│   │   └── dll_compat.py        # pyads-DLL-Kompatibilität (Windows)
│   │
│   ├── config/
│   │   └── settings.py          # Konfiguration laden/speichern
│   │
│   ├── domain/
│   │   ├── state_model.py       # Thread-sicheres Zustandsmodell aller Variablen
│   │   └── history_model.py     # In-Memory-Verlaufshistorie mit Zeitfenster-Abfrage
│   │
│   ├── llm/
│   │   ├── lm_studio_client.py  # HTTP-Client für LM Studio (OpenAI-kompatibel)
│   │   └── prompt_builder.py    # Strukturierter Prompt aus Zustand + Historie
│   │
│   └── ui/
│       └── main_window.py       # Hauptfenster (PySide6), alle UI-Panels
│
└── tests/
    └── test_core.py             # Automatisierte Tests (pytest)
```

---

## Installation

### Schritt 1: Repository klonen oder herunterladen

```
git clone https://github.com/NKAutomations/ADS_AI_Analyst.git
```

Oder als ZIP herunterladen und entpacken.

### Schritt 2: INSTALL.bat ausführen

Doppelklick auf `INSTALL.bat` im Ordner `ADS_KI_Analyse`.

Das Skript:
1. sucht automatisch nach Python 3.11, 3.12 oder 3.13,
2. erstellt eine lokale virtuelle Umgebung (`.venv`),
3. installiert alle Abhängigkeiten aus `requirements.txt`,
4. prüft die Installation.

**Abhängigkeiten (`requirements.txt`):**

```
pyads==3.2.2
PySide6>=6.6,<7
httpx>=0.27.0
pydantic>=2.0.0
pytest>=8.0.0
```

> **Hinweis bei internen pip-Quellen:** Falls die Installation fehlschlägt, kann manuell mit explizitem Index installiert werden:
> ```
> .venv\Scripts\python.exe -m pip install -r requirements.txt --index-url https://pypi.org/simple/
> ```

---

## ADS-Konfiguration und Routen

### Was ist eine ADS-Route?

TwinCAT kommuniziert über das **ADS-Protokoll** (Automation Device Specification). Damit der KI-PC mit der TwinCAT-Runtime auf dem SPS-Rechner kommunizieren kann, muss auf **beiden Rechnern** eine ADS-Route eingerichtet sein.

### Route einrichten

**Auf dem KI-PC (TwinCAT Engineering):**

1. TwinCAT XAE (Engineering) öffnen
2. Im System Tray: TwinCAT-Symbol → **Router** → **Edit Routes**
3. **Add** → Remote-Rechner (Runtime-PC) per IP-Adresse suchen
4. Route bestätigen und speichern

**Auf dem Runtime-Rechner:**

Die Gegenseite muss ebenfalls eine Route zum KI-PC kennen. Dies geschieht entweder automatisch beim Verbindungsaufbau oder manuell über TwinCAT System Manager / XAE.

### AMS Net ID ermitteln

Die AMS Net ID des Runtime-Rechners ist in der Form `x.x.x.x.1.1` aufgebaut, wobei `x.x.x.x` typischerweise der IP-Adresse entspricht.

Beispiel: IP `192.168.0.10` → AMS Net ID `192.168.0.10.1.1`

Die genaue AMS Net ID ist im TwinCAT System Manager des Runtime-Rechners unter **System → Properties** zu finden.

### Verbindungsparameter in der Anwendung

| Parameter | Beschreibung | Beispiel |
|---|---|---|
| Host / IP | IP-Adresse des Runtime-Rechners | `192.168.0.10` |
| AMS Net ID | AMS Net ID der Runtime | `192.168.0.10.1.1` |
| ADS-Port | Port der PLC-Runtime | `851` (Standard TC3) |

---

## LM Studio einrichten

### Installation

1. [LM Studio](https://lmstudio.ai/) herunterladen und installieren
2. Ein geeignetes Modell herunterladen (z. B. Llama 3, Mistral, Phi-3)
3. Das Modell in LM Studio laden

### Lokalen Server starten

In LM Studio:
- Tab **„Local Server"** öffnen
- Modell auswählen
- **„Start Server"** klicken
- Standard-URL: `http://127.0.0.1:1234/v1`

### Verbindung prüfen

In der Anwendung: Button **„LM Studio prüfen"** → zeigt verfügbare Modelle an.

### Empfohlene Modelle

Für die Analyse von SPS-Zuständen eignen sich Modelle mit gutem Instruktions-Following:
- **Llama 3.1 8B Instruct** (gute Balance aus Geschwindigkeit und Qualität)
- **Mistral 7B Instruct**
- **Phi-3 Mini / Medium Instruct** (schnell, ressourcenschonend)

> **Hinweis:** Die Anwendung sendet keine Daten an externe Server. LM Studio läuft vollständig lokal.

---

## Anwendung starten

Doppelklick auf `START_ADS.bat`.

Alternativ manuell:
```
.venv\Scripts\python.exe app\main.py
```

---

## Bedienoberfläche

Die Oberfläche ist in vier Bereiche aufgeteilt:

### 1. Verbindung (oben links)

- **Host / IP** und **AMS Net ID** eingeben
- **ADS-Port** einstellen (Standard: 851)
- **Verbinden** / **Trennen**
- Verbindungsstatus wird farbig angezeigt (grün = verbunden, rot = Fehler)
- **Einstellungen öffnen...** → Erweiterte Parameter für ADS, LLM und Logging

### 2. Variablenübersicht (unten links)

- **Alle Symbole auslesen** → liest alle verfügbaren ADS-Symbole aus der Runtime
- **Filter** → Symbolliste nach Name filtern
- Tabelle mit Spalten:
  - **Symbol** – vollständiger ADS-Symbolname
  - **Typ** – normalisierter Datentyp (BOOL, INT, REAL, ...)
  - **TC-Typ** – originaler TwinCAT-Typ
  - **Kommentar** – Kommentar aus dem SPS-Projekt
  - **Anzeigen** ☑ – Wert wird live in der Tabelle aktualisiert
  - **Loggen** ☑ – Wertänderungen werden in der Verlaufshistorie gespeichert
  - **KI** ☑ – Variable wird bei der Analyse an das LLM übergeben
  - **Wert** – aktueller Wert mit Zeitstempel
- **Auswahl anwenden und Notifications starten** → registriert ADS-Notifications für alle markierten Variablen

> Nur Variablen mit gesetztem **„KI"**-Haken werden an das LLM übertragen. Nicht ausgewählte Variablen bleiben vollständig lokal.

### 3. KI-Analyse (oben rechts)

- **Zeitfenster** (Von / Bis) für die Verlaufshistorie wählen
- **System-Prompt** direkt editierbar
- **LM Studio URL** und **Modellname** konfigurierbar
- **Zeitfenster analysieren** → sendet aktuellen Zustand + Verlauf an LM Studio
- **LM Studio prüfen** → Verbindungstest
- **KI-Antwort** wird als Freitext angezeigt
- Zeitstempel der letzten Analyse

### 4. Tabs (unten rechts)

| Tab | Inhalt |
|---|---|
| **Protokoll (geloggte Änderungen)** | Nur Wertänderungen von Variablen mit gesetztem „Loggen"-Haken |
| **Systemmeldungen** | Verbindungsereignisse, Notifications, Fehler, LLM-Anfragen |
| **Prompt-Vorschau** | Zeigt exakt, was bei der nächsten Analyse an die KI gesendet wird |

---

## Konfigurationsdatei

Die Konfiguration wird automatisch unter `config/config.json` gespeichert.

**Beispiel:**

```json
{
  "ads": {
    "host": "192.168.0.10",
    "ams_net_id": "192.168.0.10.1.1",
    "port": 851,
    "timeout_seconds": 3.0,
    "notification_cycle_ms": 100
  },
  "variables": [],
  "llm": {
    "base_url": "http://127.0.0.1:1234/v1",
    "model": "llama-3.1-8b-instruct",
    "timeout_seconds": 60.0,
    "temperature": 0.1,
    "max_tokens": 1200,
    "context_length": 4096,
    "top_p": 0.95,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "stream": false,
    "system_prompt": "Analysiere ausschließlich die übergebenen ADS-Daten und ihren zeitlichen Verlauf. Beschreibe sachlich Beobachtungen, Auffälligkeiten und mögliche Ursachen. Erfinde keine Werte und gib keine Steuerungs- oder Schreibbefehle aus. Antworte als verständlicher Freitext."
  },
  "logging": {
    "max_entries": 5000,
    "file": "logs/app.log",
    "timestamp_precision": "milliseconds"
  }
}
```

Die Datei kann direkt bearbeitet werden (`OPEN_CONFIG.bat`) oder über den Dialog **„Einstellungen öffnen..."** in der Anwendung.

> **Sicherheitshinweis:** Keine Passwörter, API-Schlüssel oder geheimen Zugangsdaten in der Konfigurationsdatei speichern. Die Datei liegt unverschlüsselt auf dem Dateisystem.

---

## Unterstützte Datentypen

| TwinCAT-Typ | Normalisiert | Notification |
|---|---|---|
| BOOL | BOOL | ✅ |
| INT, SINT | INT | ✅ |
| DINT, LINT | DINT | ✅ |
| UINT, USINT, BYTE, WORD | UINT | ✅ |
| UDINT, ULINT, DWORD | UDINT | ✅ |
| REAL | REAL | ✅ |
| LREAL | LREAL | ✅ |
| TIME | TIME (als UDINT) | ✅ |
| STRING | STRING | ⚠️ Initialwert lesbar, Notification deaktiviert* |
| Komplexe Typen (STRUCT, ARRAY, ...) | – | ❌ nicht unterstützt |

> *STRING-Notifications sind deaktiviert, da TwinCAT STRING intern ANSI/Windows-1252 kodiert, pyads jedoch UTF-8 erwartet. Der Initialwert kann weiterhin per Einzellesung abgerufen werden.

---

## Architektur

### Datenfluss

```
TwinCAT Runtime
      │  ADS Notification (ereignisbasiert)
      ▼
AdsClient.on_value_changed()
      │  Thread-sicher via Qt Signal
      ▼
StateModel.update_value()     HistoryModel.add()
      │                              │
      ▼                              ▼
Tabelle (live, 500ms-Timer)   Verlaufshistorie (In-Memory, deque)
                                     │
                              PromptBuilder.build_user_message()
                                     │
                              LmStudioClient.analyze()
                                     │
                              KI-Antwort → UI
```

### Thread-Sicherheit

- `StateModel` und `HistoryModel` sind durch `threading.Lock` geschützt
- ADS-Callbacks laufen im pyads-Thread und kommunizieren über **Qt Signals** mit dem UI-Thread
- Verbindungsaufbau und Symbolbrowser laufen in **Daemon-Threads**, um das UI nicht zu blockieren
- LLM-Anfragen laufen ebenfalls in einem separaten Thread

### Notification-Verhalten

- Notifications werden pro Symbol registriert und beim Trennen automatisch entfernt
- Bei einem Dekodierungsfehler im Callback wird die Notification für dieses Symbol automatisch deregistriert (kein endloser Fehler-Loop)
- STRING-Notifications sind bewusst deaktiviert (ANSI/UTF-8-Konflikt)

---

## Tests ausführen

Doppelklick auf `RUN_TESTS.bat` oder manuell:

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Die Tests in `tests/test_core.py` prüfen die Kernlogik **ohne echte SPS und ohne LM Studio**:

- `StateModel`: Variablen setzen, Werte aktualisieren, ungültig markieren, Auswahl verwalten
- `HistoryModel`: Einträge hinzufügen, Zeitfenster-Abfrage, Größenbegrenzung
- `PromptBuilder`: Prompt-Erstellung mit und ohne Verlaufsdaten, Verbindungsstatus
- `LmStudioClient`: Verbindungsfehler-Behandlung ohne gestarteten Server

---

## Bekannte Einschränkungen

| Einschränkung | Details |
|---|---|
| **Read-only** | Kein Schreibzugriff auf SPS-Variablen in dieser Version |
| **STRING-Notifications** | Deaktiviert wegen ANSI/UTF-8-Konflikt; Initialwert lesbar |
| **Komplexe Typen** | STRUCT, ARRAY, ENUM werden nicht unterstützt |
| **Symbolbrowser** | Nutzt direkte ADS-Indexgruppen (pyads 3.2.2 hat kein `get_all_symbols()`); sehr große Symbollisten können langsam sein |
| **Automatische Reconnect** | Verbindungsabbrüche werden angezeigt, aber kein automatischer Reconnect |
| **Kein Simulationsmodus** | Für Tests ohne SPS sind die Unit-Tests zu verwenden |
| **Windows only** | Die ADS-DLL ist Windows-spezifisch; Linux/macOS nicht unterstützt |
| **LLM-Antwortformat** | Die KI antwortet als Freitext; kein strukturiertes JSON-Parsing in dieser Version |

---

## Sicherheitshinweise und spätere Erweiterbarkeit

### Aktuelle Version: Strikt read-only

- Es existiert **kein aktiver Schreibpfad** zur SPS
- Das LLM kann keine Steuerungsaktionen auslösen
- SPS-Daten verlassen den lokalen Rechner nicht (kein Cloud-LLM, keine Telemetrie)

### Architektur für spätere Schreibfunktion

Die Architektur ist so vorbereitet, dass ein kontrollierter Schreibzugriff später ergänzt werden kann. Dieser darf **nicht direkt aus einer LLM-Antwort** heraus erfolgen:

```
LLM schlägt strukturierte Aktion vor
        │
        ▼
Anwendung validiert Aktion, Variable und Wertebereich
        │
        ▼
Benutzer bestätigt ausdrücklich (kein Auto-Write)
        │
        ▼
ADS-Schreibmodul führt nur erlaubte Aktion aus
        │
        ▼
Ergebnis wird verifiziert und protokolliert
```

Geplante Schutzmechanismen für Schreibzugriffe:
- Whitelist freigegebener Variablen
- Datentyp- und Wertebereichsprüfung
- Pflicht zur Benutzerbestätigung
- Vollständige Protokollierung jedes Schreibvorgangs
- Globaler Schalter zum Deaktivieren aller Schreibzugriffe
- Kein direktes Ausführen von Programmcode durch das LLM

---

## Lizenz

Dieses Projekt ist ein internes Testprojekt. Bitte Rücksprache mit dem Autor halten, bevor es in Produktionsumgebungen eingesetzt wird.

---

*Erstellt für: Beckhoff TwinCAT 3 · Python 3.11+ · PySide6 · LM Studio · pyads 3.2.2*
