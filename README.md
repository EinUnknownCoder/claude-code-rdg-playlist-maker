# RDG Playlist Maker

Ein Python-Tool zur Erstellung von K-Pop Random Dance Game Playlists mit automatischem YouTube-Download, Audio-Verarbeitung und Video-Export.

## Features

- YouTube Lyric Video Download mit Validierung (optional überspringbar)
- Automatische URL-Bereinigung (entfernt Playlist-Parameter)
- Audio-Normalisierung (einheitliche Lautstärke)
- Einlauf- und Auslaufzeit für jeden Song
- Fade-In und Fade-Out
- Zwei Verteilungsmodi:
  - **Fair**: Artist-balanciert, gemischt
  - **Sequential**: Excel-Reihenfolge beibehalten
- Normalisierte Dateinamen (lowercase, keine Leerzeichen/Sonderzeichen)
- MP3 und MP4 Export
- YouTube-Chapters für Video-Beschreibung
- Fehler-Export als Textdatei

## Voraussetzungen

- Python 3.9+ (empfohlen: 3.10+)
- ffmpeg

### ffmpeg installieren (macOS)

```bash
brew install ffmpeg
```

## Installation

1. Repository klonen:
```bash
git clone <repo-url>
cd claude-code-rdg-playlist-maker
```

2. Virtuelle Umgebung erstellen und aktivieren:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

## Excel-Datei vorbereiten

Erstelle eine Excel-Datei (z.B. `request.xlsx`) mit folgenden Spalten:

| Spalte | Beschreibung |
|--------|--------------|
| A | YouTube-URL (muss Lyric Video sein!) |
| B | Artist |
| C | Titel |
| D | Description/Songpart (z.B. "Chorus", "Chorus 2, Dancebreak") |
| E | Requester/Dancer Name |
| F | Start: Minute |
| G | Start: Second |
| H | End: Minute |
| I | End: Second |

**Wichtig:**
- Die URL muss zu einem **Lyric Video** führen (nicht Official MV oder Dance Practice)
- Artist und Titel müssen im Video-Titel vorkommen (falls URL-Validierung aktiviert)
- URLs mit `&list=` Parameter werden automatisch bereinigt (lädt nur das einzelne Video)
- Dateinamen werden normalisiert: "NewJeans - Hype Boy!" → `newjeans-hypeboy.mp3`
  - Verhindert Duplikate durch Schreibvarianten (z.B. "Stray Kids" vs "Straykids")
- Wenn "Dancebreak" in der Description steht, wird `dancebreak.mp3` vor dem Song eingefügt

## Assets vorbereiten

Lege folgende Dateien im `assets/` Ordner ab:

- `three.mp3` - Countdown zwischen den Songs
- `dancebreak.mp3` - Wird vor Songs mit "Dancebreak" in der Description abgespielt
- `RDGStuttgart2.jpg` - Standbild für das Video

## Programm starten

```bash
source venv/bin/activate
python main.py
```

Das Programm fragt nach folgenden Eingaben (Enter für Standardwert):

| Eingabe | Standardwert | Beschreibung |
|---------|--------------|--------------|
| Excel-Datei | `request.xlsx` | Pfad zur Excel-Datei |
| Anzahl Playlists | `4` | Auf wie viele Playlists verteilt wird |
| Einlaufzeit | `8` Sekunden | Zeit vor dem Start-Timestamp |
| Auslaufzeit | `2` Sekunden | Zeit nach dem End-Timestamp |
| Verteilungsmodus | `1` (Fair) | `1` = Fair (gemischt), `2` = Sequential (Excel-Reihenfolge) |
| Output-Ordner | `output` | Wo die Dateien gespeichert werden |
| Assets-Ordner | `assets` | Wo die Assets liegen |
| URL-Validierung überspringen | `N` (Nein) | `J` = Überspringen, `N` = Normale Validierung |

## Ablauf

1. **Validierung & Download**:
   - Bereits heruntergeladene Songs werden erkannt (spart Zeit!)
   - Neue Songs werden validiert (falls nicht übersprungen): Artist, Titel, Lyric Video
   - Gültige Songs werden sofort heruntergeladen (128 kbps für schnellere Downloads)

2. **Fehlerbehandlung**: Falls Fehler gefunden werden, stoppt das Programm und zeigt alle Fehler an. Zusätzlich wird `output/errors.txt` erstellt. Bereits heruntergeladene Songs bleiben gecacht.

3. **Playlist-Erstellung**:
   - **Fair Mode**: Songs werden artist-balanciert gemischt (kein Artist dominiert)
   - **Sequential Mode**: Songs bleiben in Excel-Reihenfolge, gleichmäßig auf N Playlists aufgeteilt

4. **Audio-Verarbeitung**:
   - Lautstärke-Normalisierung
   - Einlauf-/Auslaufzeit
   - Fade-In/Out (je 2 Sekunden)
   - `three.mp3` zwischen jedem Song
   - `dancebreak.mp3` vor Songs mit Dancebreak

5. **Export**: MP3, MP4 (mit Standbild) und `chapters.txt`

## Output

```
output/
├── playlist_1.mp3
├── playlist_1.mp4
├── playlist_2.mp3
├── playlist_2.mp4
├── ...
├── chapters.txt
└── errors.txt         (nur bei Fehlern)
```

Die `chapters.txt` enthält YouTube-Chapters für alle Playlists:

```
=== PLAYLIST 1 ===
00:03 ARTIST - TITEL (Songpart, Requester)
01:23 ARTIST - TITEL (Songpart, Requester)
...
```

## Tipps

- **Downloads werden gecacht**: Wenn ein Song bereits in `downloads/` liegt, wird er nicht erneut heruntergeladen (keine erneute URL-Validierung nötig).
- **Bei Fehlern**: Korrigiere die Excel-Datei und starte erneut. Bereits heruntergeladene Songs bleiben erhalten. Fehlerliste siehe `output/errors.txt`.
- **Lyric Video finden**: Suche auf YouTube nach "[Artist] [Song] Lyrics" oder "[Artist] [Song] 가사"
- **URL-Validierung überspringen**: Nützlich wenn du Playlists für andere erstellst und nur prüfen willst, ob Downloads funktionieren.
- **Sequential Mode**: Perfekt wenn du eine spezifische Reihenfolge aus der Excel-Datei beibehalten möchtest.
