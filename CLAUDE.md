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
- `distribute.py` - Faire Song-Verteilung auf Playlists (Artist-balanciert)

## Datenfluss
1. Excel einlesen → Liste von Song-Objekten
2. Für jeden Song: URL validieren, bei Erfolg sofort downloaden
3. Falls Fehler: STOP, zeige alle Fehler, bereits geladene Songs bleiben gecacht
4. Songs auf X Playlists verteilen (Round-Robin nach Artist)
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
- **Einlaufzeit**: X Sekunden vor dem Start-Timestamp (Standard: 8s)
- **Auslaufzeit**: X Sekunden nach dem End-Timestamp (Standard: 2s)
- **Normalisierung**: Alle Songs auf -14 dBFS
- **Fade-In**: 2 Sekunden am Anfang jedes Songs
- **Fade-Out**: 2 Sekunden am Ende jedes Songs
- **Transitions**: `three.mp3` zwischen allen Songs, `dancebreak.mp3` vor Dancebreak-Songs

## URL-Validierung
Prüfungen:
1. Artist muss im Video-Titel vorkommen
2. Songtitel muss im Video-Titel vorkommen
3. Muss Lyric Video sein (Keywords: "lyric", "lyrics", "가사")

Nicht erlaubt:
- Official MV / Music Video (kann Soundeffekte haben)
- Dance Practice / Choreography (schlechte Audioqualität)

## Wichtige Konventionen
- Assets liegen in `assets/` (three.mp3, dancebreak.mp3, RDGStuttgart2.jpg)
- Downloads werden gecacht in `downloads/` (Dateiname: "Artist - Titel.mp3")
- Output geht nach `output/` (playlist_1.mp3, playlist_1.mp4, ..., chapters.txt)
- CLI-Standardwerte: request.xlsx, 3 Playlists, 8s Einlauf, 2s Auslauf

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

## Typische Erweiterungen
- **Neue Validierungsregeln**: `validate.py` → `validate_url()` anpassen
- **Excel-Spalten ändern**: `excel.py` → `Song` Dataclass und `read_excel()` anpassen
- **Audio-Transitions ändern**: `audio.py` → `build_playlist_audio()` anpassen
- **Fade-Zeiten ändern**: `audio.py` → `cut_song()` Parameter `fade_in_ms`, `fade_out_ms`
- **Normalisierung anpassen**: `audio.py` → `normalize_audio()` Parameter `target_dBFS`
- **CLI-Eingaben hinzufügen**: `main.py` → neue `get_input_with_default()` Aufrufe
- **Chapters-Format ändern**: `audio.py` → `generate_chapters_text()` anpassen

## Bekannte Einschränkungen
- Python 3.9 zeigt Deprecation-Warnungen von yt-dlp (funktioniert aber)
- tkinter GUI funktioniert nicht auf allen macOS-Versionen (daher CLI)
