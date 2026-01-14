"""RDG Playlist Maker - Hauptprogramm mit CLI."""

import os
import sys

from excel import read_excel, validate_timestamps, Song
from validate import validate_url, format_validation_errors, ValidationResult
from download import download_song, is_downloaded, get_download_path
from audio import build_playlist_audio, export_audio, generate_chapters_text
from video import create_video, check_ffmpeg
from distribute import distribute_songs_fairly


def print_header():
    """Zeigt den Header an."""
    print("\n" + "=" * 50)
    print("  RDG Playlist Maker")
    print("=" * 50 + "\n")


def get_input_with_default(prompt: str, default: str) -> str:
    """Fragt nach Eingabe mit Standardwert."""
    user_input = input(f"{prompt} [{default}]: ").strip()
    return user_input if user_input else default


def get_int_with_default(prompt: str, default: int) -> int:
    """Fragt nach Integer-Eingabe mit Standardwert."""
    while True:
        user_input = input(f"{prompt} [{default}]: ").strip()
        if not user_input:
            return default
        try:
            return int(user_input)
        except ValueError:
            print("Bitte eine Zahl eingeben.")


def main():
    print_header()

    # Prüfe ffmpeg
    if not check_ffmpeg():
        print("FEHLER: ffmpeg ist nicht installiert!")
        print("Bitte installiere es mit: brew install ffmpeg")
        sys.exit(1)

    # Eingaben mit Standardwerten
    print("Drücke Enter für Standardwerte:\n")

    excel_path = get_input_with_default("Excel-Datei", "request.xlsx")
    num_playlists = get_int_with_default("Anzahl Playlists", 4)
    lead_in_seconds = get_int_with_default("Einlaufzeit (Sekunden vor Start)", 8)
    lead_out_seconds = get_int_with_default("Auslaufzeit (Sekunden nach Ende)", 2)
    output_dir = get_input_with_default("Output-Ordner", "output")
    assets_dir = get_input_with_default("Assets-Ordner", "assets")

    # Pfade zu Assets
    three_mp3 = os.path.join(assets_dir, "three.mp3")
    dancebreak_mp3 = os.path.join(assets_dir, "dancebreak.mp3")
    image_path = os.path.join(assets_dir, "RDGStuttgart2.jpg")

    print("\n" + "-" * 50)
    print("Prüfe Voraussetzungen...")

    # Prüfe ob Dateien existieren
    if not os.path.exists(excel_path):
        print(f"FEHLER: Excel-Datei nicht gefunden: {excel_path}")
        sys.exit(1)

    for asset, name in [(three_mp3, "three.mp3"), (dancebreak_mp3, "dancebreak.mp3"),
                        (image_path, "RDGStuttgart2.jpg")]:
        if not os.path.exists(asset):
            print(f"FEHLER: Asset nicht gefunden: {name}")
            sys.exit(1)

    print("Alle Dateien gefunden!")

    # 1. Excel einlesen
    print("\n" + "-" * 50)
    print(f"Lese {excel_path}...")

    songs = read_excel(excel_path)
    print(f"{len(songs)} Songs gefunden")

    # Timestamps validieren
    timestamp_errors = validate_timestamps(songs)
    if timestamp_errors:
        print("\nFEHLER: Ungültige Timestamps:")
        for error in timestamp_errors:
            print(f"  {error}")
        sys.exit(1)

    # 2. URLs validieren und downloaden
    print("\n" + "-" * 50)
    print("Validiere URLs und lade Songs herunter...\n")

    valid_songs = []
    invalid_results = []

    for i, song in enumerate(songs, 1):
        print(f"[{i}/{len(songs)}] {song.artist} - {song.title}")

        result = validate_url(song)

        if result.is_valid:
            print(f"  ✓ URL gültig")

            # Sofort herunterladen wenn gültig
            if not is_downloaded(song):
                print(f"  ⬇ Lade herunter...")
                try:
                    download_song(song)
                    print(f"  ✓ Heruntergeladen")
                except Exception as e:
                    print(f"  ✗ Download-Fehler: {e}")
                    invalid_results.append(ValidationResult(
                        song=song,
                        is_valid=False,
                        error_message=f"Download fehlgeschlagen: {e}"
                    ))
                    continue
            else:
                print(f"  ✓ Bereits vorhanden")

            valid_songs.append(song)
        else:
            print(f"  ✗ {result.error_message}")
            invalid_results.append(result)

    # Wenn Fehler gefunden, stoppen
    if invalid_results:
        print("\n" + "=" * 50)
        print("STOPP: Fehlerhafte URLs gefunden!")
        print("=" * 50)
        print(format_validation_errors(invalid_results))
        print("\nBitte korrigiere die Excel-Datei und starte erneut.")
        print("Bereits heruntergeladene Songs bleiben gecacht.")
        sys.exit(1)

    # 3. Songs auf Playlists verteilen
    print("\n" + "-" * 50)
    print(f"Verteile {len(valid_songs)} Songs auf {num_playlists} Playlists...\n")

    playlists = distribute_songs_fairly(valid_songs, num_playlists)

    for i, playlist in enumerate(playlists, 1):
        artists = set(s.artist for s in playlist)
        print(f"Playlist {i}: {len(playlist)} Songs von {len(artists)} Artists")

    # Output-Ordner erstellen
    os.makedirs(output_dir, exist_ok=True)

    # Song-Pfade sammeln (nach Dateiname)
    song_paths = {song.filename: get_download_path(song) for song in valid_songs}

    # 4. Playlists erstellen
    print("\n" + "-" * 50)
    print("Erstelle Playlists...\n")

    all_chapters = []

    for playlist_num, playlist_songs in enumerate(playlists, 1):
        print(f"Playlist {playlist_num}:")

        # Audio zusammenfügen
        print(f"  Füge Audio zusammen...")
        audio, chapters = build_playlist_audio(
            playlist_songs, song_paths, three_mp3, dancebreak_mp3,
            lead_in_seconds=lead_in_seconds,
            lead_out_seconds=lead_out_seconds
        )

        # MP3 exportieren
        mp3_path = os.path.join(output_dir, f"playlist_{playlist_num}.mp3")
        print(f"  Exportiere MP3...")
        export_audio(audio, mp3_path)

        # Video erstellen
        mp4_path = os.path.join(output_dir, f"playlist_{playlist_num}.mp4")
        print(f"  Erstelle Video...")
        create_video(mp3_path, image_path, mp4_path)

        print(f"  ✓ Fertig!")

        all_chapters.append((playlist_num, chapters))

    # 5. Chapters-Datei erstellen
    print("\n" + "-" * 50)
    print("Erstelle Chapters-Datei...")

    chapters_text = generate_chapters_text(all_chapters)
    chapters_path = os.path.join(output_dir, "chapters.txt")
    with open(chapters_path, 'w', encoding='utf-8') as f:
        f.write(chapters_text)

    # Fertig!
    print("\n" + "=" * 50)
    print("FERTIG!")
    print("=" * 50)
    print(f"\nOutput-Ordner: {output_dir}")
    print(f"  - {num_playlists} MP3-Dateien")
    print(f"  - {num_playlists} MP4-Videos")
    print(f"  - chapters.txt für YouTube")
    print()


if __name__ == "__main__":
    main()
