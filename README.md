# ADS_KI_Analyse v1.2.0

Lokales Windows-Desktopwerkzeug zur read-only Überwachung, Aufzeichnung und Analyse echter Beckhoff-TwinCAT-Daten über ADS mit einem lokal betriebenen LLM über LM Studio.

## Inhaltsverzeichnis

1. [Zweck der Software](#zweck-der-software)
2. [Wichtige Grenzen](#wichtige-grenzen)
3. [Neuerungen in V1.2](#neuerungen-in-v12)
4. [Systemarchitektur](#systemarchitektur)
5. [Systemvoraussetzungen](#systemvoraussetzungen)
6. [Installation unter Windows](#installation-unter-windows)
7. [ADS-Verbindung einrichten](#ads-verbindung-einrichten)
8. [LM Studio einrichten](#lm-studio-einrichten)
9. [Anwendung starten](#anwendung-starten)
10. [Bedienung](#bedienung)
11. [BOOL-Zeitdiagramm](#bool-zeitdiagramm)
12. [Triggeranalyse](#triggeranalyse)
13. [KI-Analyse](#ki-analyse)
14. [Konfiguration](#konfiguration)
15. [Fehlerbehebung](#fehlerbehebung)
16. [Tests](#tests)
17. [Bekannte Einschränkungen](#bekannte-einschränkungen)

## Zweck der Software

ADS_KI_Analyse liest veröffentlichte Symbole einer echten Beckhoff-TwinCAT-Runtime über ADS. Der Benutzer wählt die zu beobachtenden Variablen aus, startet die Aufzeichnung und kann anschließend:

- aktuelle Werte live anzeigen,
- echte Wertänderungen mit ADS-Zeitstempeln aufzeichnen,
- BOOL-Signale als digitale Zeitlinien visualisieren,
- einen frei wählbaren Zeitraum untersuchen,
- ausgewählte Daten an LM Studio übertragen,
- eine lokale KI-Analyse als Freitext erhalten.

Die Anwendung ist ein Diagnoseassistent. Sie ersetzt weder die SPS-Logik noch eine Leitwarte oder sicherheitsgerichtete Steuerung.

## Wichtige Grenzen

Die Anwendung arbeitet vollständig **read-only**.

Nicht enthalten sind:

- ADS-Schreibfunktionen,
- Start-/Stoppbefehle für die SPS,
- automatische Steuerungsaktionen,
- SPS-Programmänderungen,
- Cloud-LLM-Endpunkte,
- künstliche Prozesswerte,
- ein Benutzer-Simulationsmodus,
- fest eingebaute Ampel- oder projektspezifische Fachregeln.

Die Anwendung darf „verbunden“ erst anzeigen, nachdem eine echte ADS-Kommunikation mit dem konfigurierten Ziel erfolgreich verifiziert wurde.

## Neuerungen in V1.2

V1.2 baut auf der Aufzeichnungsfunktion von V1.1 auf und ergänzt eine visuelle Auswertung:

- neues Register **BOOL-Zeitdiagramm**,
- digitale Zeitlinien für aufgezeichnete BOOL-Signale,
- sichtbare Flanken bei TRUE/FALSE-Änderungen,
- individuelle Farben je aufgezeichneter Variable,
- rollierendes Anzeigezeitfenster von 30 Sekunden bis 30 Minuten,
- eingefrorene Diagrammansicht nach dem Stoppen der Aufzeichnung,
- unabhängigkeit des Diagrammfensters vom KI-Analysefenster,
- unveränderte Aufzeichnung, Triggeranalyse und Prompt-Vorschau aus V1.1.

Das Diagramm verwendet ausschließlich die lokale Historie echter ADS-Wertänderungen. Es erzeugt keine zusätzlichen Prozesswerte.

## Systemarchitektur

```text
TwinCAT-Runtime
       │
       │ ADS über lokale Netzwerkverbindung
       ▼
ADS_KI_Analyse
       ├── echte ADS-Verifikation
       ├── dynamischer Symbolbrowser
       ├── read-only Wertlesen
       ├── ADS-Notifications
       ├── thread-sicheres Zustandsmodell
       ├── begrenzte In-Memory-Historie
       ├── BOOL-Zeitdiagramm
       └── lokale LM-Studio-API
                    │
                    ▼
       LM Studio auf 127.0.0.1:1234
```

## Systemvoraussetzungen

### KI-PC

- Windows 10 oder Windows 11, vorzugsweise 64-Bit
- Python 3.11, 3.12 oder 3.13
- TwinCAT Engineering beziehungsweise die benötigte ADS-Runtime-/DLL-Umgebung
- Netzwerkzugang zur TwinCAT-Runtime
- LM Studio für lokale KI-Analysen

### Runtime-Rechner

- laufende TwinCAT-3-Runtime
- korrekt eingerichtete ADS-Route
- erreichbarer ADS-Port, standardmäßig `851`
- veröffentlichte ADS-Symbole

### Python-Abhängigkeiten

```text
pyads==3.2.2
PySide6>=6.6,<7
httpx>=0.27.0
pydantic>=2.0.0
pytest>=8.0.0
```

## Installation unter Windows

### 1. Projekt beziehen

Repository klonen oder das Release-Archiv herunterladen und in einen lokalen Projektordner entpacken:

```powershell
git clone https://github.com/NKAutomations/ADS_AI_Analyst.git
cd ADS_AI_Analyst
```

### 2. Geeignete Python-Version prüfen

```powershell
py -3.13 --version
py -3.12 --version
py -3.11 --version
```

Python 3.14 sollte nicht automatisch verwendet werden, solange die eingesetzten Abhängigkeiten dafür nicht geprüft sind.

### 3. Installation ausführen

Im Projektordner:

```text
INSTALL.bat
```

Das Installationsskript:

1. wechselt in den Projektordner,
2. sucht Python 3.13, 3.12 oder 3.11,
3. erstellt `.venv`,
4. installiert `requirements.txt`,
5. prüft die wichtigsten Imports.

Alternativ manuell:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Bei einer Unternehmens-Paketquelle, die `PySide6` nicht anbietet, muss zuerst die konfigurierte Paketquelle geprüft werden. Nicht vorschnell den Anwendungscode ändern.

Nützliche Prüfungen:

```powershell
where python
where pip
python --version
python -m pip --version
python -m pip config list
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip --version
.venv\Scripts\python.exe -m pip config list
```

### 4. Installation testen

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## ADS-Verbindung einrichten

### ADS-Route

Vor dem Programmstart müssen KI-PC und Runtime-Rechner ADS-seitig verbunden sein. Die Route wird nicht automatisch durch ADS_KI_Analyse eingerichtet.

Prüfen Sie:

- IP-Adresse oder Hostname des Runtime-Rechners,
- AMS Net ID der Runtime,
- ADS-Port, normalerweise `851`,
- TwinCAT-Runtime-Zustand,
- Windows-Firewall,
- ADS-Route auf den beteiligten Rechnern.

Beispiel:

```text
Host / IP: 192.168.0.10
AMS Net ID: 192.168.0.10.1.1
ADS-Port: 851
```

Die AMS Net ID ist nicht automatisch immer identisch mit der IP-Adresse. Verwenden Sie die tatsächlich in TwinCAT konfigurierte AMS Net ID.

### Verifikation

Nach dem Klick auf **Verbinden** liest die Anwendung echte Geräteinformationen und den ADS-Zustand. Erst danach erscheint ein bestätigter Verbindungsstatus.

Bei einer falschen IP-Adresse, AMS Net ID, Portnummer oder fehlenden Route muss der Verbindungsaufbau fehlschlagen.

## LM Studio einrichten

1. LM Studio lokal installieren.
2. Ein lokales, geeignetes Modell laden.
3. In LM Studio den lokalen Server starten.
4. Standardmäßig die Basis-URL `http://127.0.0.1:1234/v1` verwenden.
5. Die tatsächlich angebotene Modell-ID in ADS_KI_Analyse eintragen.

Die Anwendung verwendet den lokalen Endpunkt:

```text
http://127.0.0.1:1234/v1/chat/completions
```

Verbindung prüfen:

```text
LM Studio prüfen
```

Die Anwendung verwendet im Normalbetrieb keinen Cloud-Dienst.

## Anwendung starten

Nach erfolgreicher Installation:

```text
START_ADS.bat
```

Alternativ:

```powershell
.venv\Scripts\python.exe app\main.py
```

## Bedienung

### 1. Verbindung herstellen

Host, AMS Net ID und ADS-Port eintragen und **Verbinden** wählen. Warten, bis die echte ADS-Verifikation erfolgreich ist.

### 2. Symbole laden

**Alle Symbole auslesen** wählen. Die Liste wird dynamisch aus der Runtime geladen. Sie enthält keine fest codierte Variablenliste.

Nicht unterstützte komplexe Datentypen werden angezeigt, können aber nicht für typisiertes Lesen oder Notifications verwendet werden.

### 3. Variablen auswählen

In V1.2 gibt es die eindeutige Auswahl **Aufzeichnen**.

Eine aufgezeichnete Variable:

- wird angezeigt,
- wird bei echten Wertänderungen historisch gespeichert,
- darf in die KI-Anfrage einfließen,
- erhält eine ADS-Notification.

### 4. Farbe auswählen

Für unterstützte Variablen kann eine Diagrammfarbe festgelegt werden. Die Farbe ist nur eine Darstellungseinstellung.

### 5. Aufzeichnung starten

**Aufzeichnung starten** wählen. Die Anwendung liest zunächst aktuelle Werte und registriert anschließend Notifications für die ausgewählten unterstützten Symbole.

### 6. Werte und Protokoll beobachten

Die Oberfläche zeigt aktuelle Werte mit dem Zeitpunkt der letzten tatsächlichen Änderung. Ein periodischer UI-Refresh erzeugt keinen neuen Zeitstempel.

### 7. Aufzeichnung stoppen

**Aufzeichnung stoppen** beendet die Notifications. Die bisherige In-Memory-Historie bleibt bis zum Beenden der Anwendung erhalten.

## BOOL-Zeitdiagramm

Das Register **BOOL-Zeitdiagramm** zeigt aufgezeichnete BOOL-Variablen als digitale Zeitlinien.

- `TRUE` entspricht der oberen Signalstufe `1`.
- `FALSE` entspricht der unteren Signalstufe `0`.
- Ein Wechsel zwischen den Zuständen erscheint als Flanke.
- Mehrere Variablen werden getrennt untereinander gezeichnet.
- Die jeweils eingestellte Variablefarbe wird verwendet.

### Anzeigezeitfenster

Das rollierende Anzeigezeitfenster kann unabhängig von der KI-Analyse eingestellt werden:

- 30 Sekunden
- 1 Minute
- 2 Minuten
- 5 Minuten
- 10 Minuten
- 30 Minuten

Während der Aufzeichnung läuft das Fenster mit. Nach dem Stoppen bleibt die Darstellung auf dem letzten Anzeigezeitpunkt stehen.

Das Anzeigezeitfenster löscht keine Historie und begrenzt nicht automatisch den Zeitraum der KI-Analyse.

### Leeres Diagramm

Wenn noch keine aufgezeichneten BOOL-Wertänderungen vorliegen, zeigt das Diagramm einen Hinweis. Mögliche Ursachen:

- Aufzeichnung wurde noch nicht gestartet.
- Keine Variable wurde mit **Aufzeichnen** ausgewählt.
- Es gibt noch keine Wertänderung.
- Die Notification wurde nicht registriert.
- Das Anzeigezeitfenster enthält noch keinen Historieneintrag.

## Triggeranalyse

Für eine unterstützte BOOL-Variable kann eine automatische Triggeranalyse eingerichtet werden.

Konfigurierbar sind:

- Trigger-Variable,
- steigende Flanke `FALSE → TRUE`,
- fallende Flanke `TRUE → FALSE`,
- beide Flanken,
- Rückblickzeitraum,
- Nachlaufzeitraum.

Nach dem Trigger bleibt die Aufzeichnung aktiv. Nach Ablauf des Nachlaufs wird der ausgewählte Zeitraum analysiert und die Prompt-Vorschau aktualisiert.

Die Triggeranalyse erzeugt keine Steueraktion. Sie startet ausschließlich eine lokale Analyse der bereits aufgezeichneten Daten.

## KI-Analyse

### Analysezeitfenster

Das KI-Analysezeitfenster wird separat über **Von** und **Bis** eingestellt. Es ist unabhängig vom rollierenden BOOL-Diagrammfenster.

### Prompt

Der System-Prompt ist editierbar. Vor der Übertragung kann die **Prompt-Vorschau** kontrolliert werden.

An LM Studio werden nur aufgezeichnete Variablen, ihre aktuellen Zustände sowie passende Historieneinträge übergeben. Nicht aufgezeichnete Symbole werden ausgeschlossen.

### Datenformat

Die Zeitreihe wird kompakt mit einer Symbolzuordnung, einem Anfangszustand und Änderungszeilen übertragen. Die KI erhält damit:

- ADS-Verbindungsstatus,
- read-only-Hinweis,
- Symbolname und Typ,
- aktuelle Werte und Zeitstempel,
- Historieneinträge im gewählten Analysezeitraum.

### Antwort

Die KI-Antwort wird als Freitext angezeigt. Bei einem nicht erreichbaren LM-Studio-Server, einem Timeout oder einer leeren Antwort erscheint eine technische Fehlermeldung in der Oberfläche und im Protokoll.

## Konfiguration

Die Konfiguration liegt lokal in:

```text
config\config.json
```

Beispiel:

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
    "model": "",
    "timeout_seconds": 60.0,
    "temperature": 0.1,
    "max_tokens": 1200,
    "context_length": 4096,
    "top_p": 0.95,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "stream": false,
    "system_prompt": "..."
  },
  "logging": {
    "max_entries": 5000,
    "file": "logs/app.log",
    "timestamp_precision": "milliseconds"
  }
}
```

Die maximale Historiengröße begrenzt den Speicher. Werden alte Einträge entfernt, kann das Diagramm und die KI-Analyse nur noch auf den vorhandenen Zeitraum zugreifen.

## Fehlerbehebung

### ADS-Verbindung fehlgeschlagen

Prüfen Sie:

1. Läuft die TwinCAT-Runtime?
2. Ist Host oder IP korrekt?
3. Ist die AMS Net ID korrekt?
4. Ist Port `851` richtig?
5. Existiert die ADS-Route?
6. Blockiert die Firewall ADS-Kommunikation?
7. Sind Symbole veröffentlicht?

### Keine Symbole geladen

- Verbindung muss erfolgreich verifiziert sein.
- ADS-Symbolupload muss in der Runtime verfügbar sein.
- Runtime und Port müssen zur erwarteten PLC-Instanz gehören.
- Technische Details stehen im Systemprotokoll.

### BOOL-Diagramm bleibt leer

- Mindestens eine unterstützte BOOL-Variable auswählen.
- Aufzeichnung starten.
- Prüfen, ob echte Wertänderungen auftreten.
- Anzeigezeitfenster kontrollieren.
- Historienlimit prüfen.

### LM Studio nicht erreichbar

- Server in LM Studio starten.
- Basis-URL kontrollieren.
- Modell laden.
- Modell-ID in der Anwendung prüfen.
- Lokale Firewall oder Portbelegung prüfen.

### Keine KI-Daten für ein Symbol

Nur Symbole mit aktivierter Auswahl **Aufzeichnen** werden an LM Studio übergeben. Das Diagrammfenster ändert diese Auswahl nicht.

## Tests

Die Kernlogik kann ohne echte SPS und ohne LM Studio getestet werden:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Die Tests dürfen interne Test-Doubles verwenden. Diese stellen keinen Benutzer-Simulationsmodus dar und erzeugen keine gültige ADS-Verbindung in der Anwendung.

Zu prüfen sind insbesondere:

- thread-sichere Zustandsaktualisierung,
- stabile Zeitstempel,
- Historienlimit,
- Zeitfensterfilter,
- Ausschluss nicht aufgezeichneter Variablen,
- Prompt-Erstellung,
- Triggerlogik,
- Diagrammdaten aus der Historie.

## Bekannte Einschränkungen

- Die Historie wird nur im Arbeitsspeicher gehalten.
- Beim Beenden gehen die aufgezeichneten Daten verloren.
- Das BOOL-Zeitdiagramm stellt BOOL-Signale dar, ist aber keine fachliche Bewertung.
- Komplexe TwinCAT-Datentypen werden nicht automatisch vollständig dekodiert.
- STRING-Notifications können abhängig von pyads- und TwinCAT-Zeichenkodierung eingeschränkt sein.
- Eine echte ADS-Route wird nicht automatisch eingerichtet.
- Ohne echte TwinCAT-Runtime werden keine Prozesswerte simuliert.
- Die Anwendung ist nicht für sicherheitsgerichtete oder deterministische Steuerungsaufgaben bestimmt.

## Sicherheitshinweis

ADS_KI_Analyse darf nicht als Ersatz für Sicherheitssteuerungen, Not-Aus-Funktionen, Schutzfunktionen, SPS-Logik oder eine Produktionsfreigabe verwendet werden. Die KI liefert Diagnose- und Beobachtungshinweise auf Basis der übertragenen Daten. Sie entscheidet nicht über die sichere Betriebsführung einer Anlage.

## Lizenz und Projekt

Projekt: ADS_KI_Analyse  
Repository: https://github.com/NKAutomations/ADS_AI_Analyst
