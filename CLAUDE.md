# RDG Playlist Maker

## Projektübersicht
Python-CLI zur Erstellung von K-Pop Random Dance Game Playlists. Das Programm liest Song-Requests aus einer Excel-Datei, validiert YouTube-URLs, lädt Songs herunter, schneidet sie auf definierte Timestamps und erstellt mehrere Playlists als MP3 und MP4 (für YouTube-Upload).

## Architektur
- `main.py` - CLI mit interaktiven Prompts + Workflow-Orchestrierung
- `excel.py` - Excel-Parsing mit openpyxl, Song-Dataclass
- `validate.py` - YouTube URL-Validierung (Artist/Titel-Check, Lyric Video Check)
- `download.py` - YouTube-Download mit yt-dlp
- `audio.py` - Audio-Schnitt, Normalisierung, Fade-In/Out, Zusammenfügung mit pydub
- `video.py` - MP4-Erstellung mit ffmpeg (Standbild + Audio)
- `distribute.py` - Song-Verteilung auf Playlists (Fair: Artist-balanciert, Sequential: Excel-Reihenfolge)

## Datenfluss
1. Excel einlesen → Liste von Song-Objekten (URLs werden bereinigt: `&list=` entfernt)
2. Für jeden Song:
   - Prüfe ob bereits heruntergeladen (gecacht)
   - Falls nein: URL validieren (optional überspringbar), dann downloaden
3. Falls Fehler: STOP, zeige alle Fehler + erstelle `errors.txt`, bereits geladene Songs bleiben gecacht
4. Songs auf X Playlists verteilen (Fair: Round-Robin nach Artist, Sequential: Excel-Reihenfolge)
5. Pro Playlist: Audio zusammenfügen mit Transitions und Effekten
6. MP3 und MP4 exportieren
7. chapters.txt generieren (YouTube-Chapter-Format)

## Excel-Format
Erwartete Spalten (Reihenfolge):
1. YouTube-URL (Lyric Video!)
2. Artist
3. Title
4. Description/Songpart (enthält "Dancebreak" → dancebreak.mp3 wird eingefügt)
5. Requester/Dancer Name
6. Start: Minute
7. Start: Second
8. End: Minute
9. End: Second

## Audio-Verarbeitung
- **Download-Qualität**: 128 kbps MP3 (ausreichend für normalisiertes Audio)
- **Dateinamen-Normalisierung**: Lowercase, keine Leerzeichen/Sonderzeichen
  - Regex: `r'[^\w]'` entfernt alle Nicht-Wortzeichen
  - Beispiel: "NewJeans - Hype Boy!" → `newjeans-hypeboy.mp3`
  - Verhindert Duplikate: "Stray Kids" = "Straykids" → `straykids-xxx.mp3`
- **Einlaufzeit**: X Sekunden vor dem Start-Timestamp (Standard: 8s)
- **Auslaufzeit**: X Sekunden nach dem End-Timestamp (Standard: 2s)
- **Normalisierung**: Alle Songs auf -14 dBFS
- **Fade-In**: 2 Sekunden am Anfang jedes Songs
- **Fade-Out**: 2 Sekunden am Ende jedes Songs
- **Transitions**: `three.mp3` zwischen allen Songs, `dancebreak.mp3` vor Dancebreak-Songs

## URL-Validierung
**Automatische Bereinigung**: URLs mit `&list=` Parameter werden bereinigt (verhindert Playlist-Download)

**Prüfungen** (optional überspringbar):
1. Artist muss im Video-Titel vorkommen
2. Songtitel muss im Video-Titel vorkommen
3. Muss Lyric Video sein (Keywords: "lyric", "lyrics", "가사")

**Nicht erlaubt**:
- Official MV / Music Video (kann Soundeffekte haben)
- Dance Practice / Choreography (schlechte Audioqualität)

**Skip-Option**: Mit `skip_validation=True` kann die Validierung übersprungen werden (nur Download-Check)

## Wichtige Konventionen
- Assets liegen in `assets/` (three.mp3, dancebreak.mp3, RDGStuttgart2.jpg)
- Downloads werden gecacht in `downloads/` (Dateiname: `artist-title.mp3`, lowercase, normalisiert)
- Output geht nach `output/` (playlist_1.mp3, playlist_1.mp4, ..., chapters.txt, errors.txt)
- CLI-Standardwerte:
  - Excel: request.xlsx
  - Playlists: 4
  - Einlauf: 8s
  - Auslauf: 2s
  - Verteilungsmodus: 1 (Fair)
  - Skip Validation: N (Nein)

## Chapters-Format
```
=== PLAYLIST 1 ===
00:03 ARTIST - TITEL (Songpart, Requester)
01:23 ARTIST - TITEL (Songpart, Requester)
```
- Artist und Titel in CAPS LOCK
- Songpart und Requester in normaler Schrift in Klammern

## Abhängigkeiten
```
openpyxl>=3.1.0   # Excel lesen
yt-dlp>=2024.1.0  # YouTube Download
pydub>=0.25.0     # Audio-Bearbeitung
```

Systemvoraussetzung: ffmpeg muss installiert sein (`brew install ffmpeg` auf macOS)

## Testen
```bash
source venv/bin/activate
python main.py
```

## Neue Funktionen (2025-01)

### Song-Verteilung
- **`distribute_songs_fairly()`** (distribute.py): Artist-balanciert, gemischt (Standard)
- **`distribute_songs_sequentially()`** (distribute.py): Excel-Reihenfolge beibehalten, gleichmäßig auf N Playlists
  - Berechnet Songs pro Playlist: `len(songs) // num_playlists`
  - Rest-Songs werden auf erste Playlists verteilt

### Workflow-Optimierung
- **Cache-First Approach**: Prüft zuerst ob Song bereits heruntergeladen ist
- Spart Zeit bei wiederholten Ausführungen (keine unnötigen YouTube-Requests)

### URL-Bereinigung
- Entfernt automatisch `&list=` Parameter aus YouTube-URLs
- Verhindert versehentlichen Playlist-Download statt einzelnem Video

### Fehler-Export
- Bei Fehlern wird automatisch `output/errors.txt` erstellt
- Enthält alle Fehlermeldungen für spätere Referenz

## Typische Erweiterungen
- **Neue Validierungsregeln**: `validate.py` → `validate_url()` anpassen
- **Excel-Spalten ändern**: `excel.py` → `Song` Dataclass und `read_excel()` anpassen
- **Audio-Transitions ändern**: `audio.py` → `build_playlist_audio()` anpassen
- **Fade-Zeiten ändern**: `audio.py` → `cut_song()` Parameter `fade_in_ms`, `fade_out_ms`
- **Normalisierung anpassen**: `audio.py` → `normalize_audio()` Parameter `target_dBFS`
- **Download-Qualität ändern**: `download.py` → `ydl_opts['preferredquality']`
- **Dateinamen-Format ändern**: `excel.py` → `Song.filename` Property
- **CLI-Eingaben hinzufügen**: `main.py` → neue `get_input_with_default()` Aufrufe
- **Chapters-Format ändern**: `audio.py` → `generate_chapters_text()` anpassen

## Bekannte Einschränkungen
- Python 3.9 zeigt Deprecation-Warnungen von yt-dlp (funktioniert aber)
- tkinter GUI funktioniert nicht auf allen macOS-Versionen (daher CLI)
