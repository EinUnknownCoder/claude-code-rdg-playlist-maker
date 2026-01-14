# RDG Playlist Maker

## Projektübersicht
Python-GUI zur Erstellung von K-Pop Random Dance Game Playlists. Das Programm liest Song-Requests aus einer Excel-Datei, validiert YouTube-URLs, lädt Songs herunter, schneidet sie auf definierte Timestamps und erstellt mehrere Playlists als MP3 und MP4 (für YouTube-Upload).

## Architektur
- `main.py` - tkinter GUI + Workflow-Orchestrierung
- `excel.py` - Excel-Parsing mit openpyxl, Song-Dataclass
- `validate.py` - YouTube URL-Validierung (Artist/Titel-Check, Lyric Video Check)
- `download.py` - YouTube-Download mit yt-dlp
- `audio.py` - Audio-Schnitt und -Zusammenfügung mit pydub
- `video.py` - MP4-Erstellung mit moviepy (Standbild + Audio)
- `distribute.py` - Faire Song-Verteilung auf Playlists (Artist-balanciert)

## Datenfluss
1. Excel einlesen → Liste von Song-Objekten
2. URLs validieren + parallel downloaden (gültige sofort laden)
3. Falls Fehler: STOP, zeige alle Fehler, bereits geladene Songs bleiben gecacht
4. Songs auf X Playlists verteilen (Round-Robin nach Artist)
5. Pro Playlist: Audio zusammenfügen (dancebreak.mp3 + three.mp3 + Song)
6. MP3 und MP4 exportieren
7. chapters.txt generieren (YouTube-Chapter-Format)

## Excel-Format
Erwartete Spalten (Reihenfolge):
1. YouTube-URL (Lyric Video!)
2. Artist
3. Titel
4. Songabschnitt/Description (enthält "Dancebreak" → dancebreak.mp3 wird eingefügt)
5. Tänzer-Name
6. Start-Timestamp (MM:SS)
7. End-Timestamp (MM:SS)

## Wichtige Konventionen
- Assets liegen in `assets/` (three.mp3, dancebreak.mp3, RDGStuttgart2.jpg)
- Downloads werden gecacht in `downloads/` (Dateiname: "Artist - Titel.mp3")
- Output geht nach `output/` (playlist_1.mp3, playlist_1.mp4, ..., chapters.txt)
- GUI-Standardwerte: request.xlsx, 3 Playlists, output/, assets/

## URL-Validierung
Erlaubt:
- Videos mit "lyric", "lyrics", "가사" im Titel

Nicht erlaubt:
- Official MV / Music Video (kann Soundeffekte haben)
- Dance Practice / Choreography (schlechte Audioqualität)

## Abhängigkeiten
```
openpyxl>=3.1.0   # Excel lesen
yt-dlp>=2024.1.0  # YouTube Download
pydub>=0.25.0     # Audio-Bearbeitung
moviepy>=1.0.3    # Video-Erstellung
```

Systemvoraussetzung: ffmpeg muss installiert sein (`brew install ffmpeg` auf macOS)

## Testen
```bash
pip install -r requirements.txt
python main.py
```

## Typische Erweiterungen
- Neue Validierungsregeln: `validate.py` → `validate_url()` anpassen
- Excel-Spalten ändern: `excel.py` → `Song` Dataclass und `read_excel()` anpassen
- Audio-Transitions ändern: `audio.py` → `build_playlist_audio()` anpassen
- GUI-Felder hinzufügen: `main.py` → `setup_ui()` und `process_playlists()` anpassen
