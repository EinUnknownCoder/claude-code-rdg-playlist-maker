"""Test-Skript für 7 Songs."""

import os
import sys

# Füge das aktuelle Verzeichnis zum Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from excel import read_excel, validate_timestamps
from validate import validate_url
from download import download_song, is_downloaded, get_download_path
from audio import build_playlist_audio, export_audio, generate_chapters_text
from video import create_video, check_ffmpeg
from distribute import distribute_with_explicit_assignments


def main():
    print("\n" + "=" * 50)
    print("  RDG Playlist Maker - TEST (7 Songs)")
    print("=" * 50 + "\n")

    # Konfiguration (Halftime-Modus: 1 Song/Playlist, Sequential, kein Fade)
    excel_path = "request.xlsx"
    num_playlists = 7  # 7 Playlists = 1 Song pro Playlist
    lead_in_seconds = 8
    lead_out_seconds = 2
    distribution_mode = 2  # Sequential = Excel-Reihenfolge beibehalten
    use_fade = False  # Halftime: kein Fade-In/Out
    output_dir = "output/Test Halftime"
    assets_dir = "assets"
    browser = "firefox"
    skip_validation = True  # Überspringe Validierung für schnelleren Test
    cover_image = os.path.join(assets_dir, "cover", "PforzheimRPD.jpg")

    # Prüfe ffmpeg
    print("Prüfe ffmpeg...", end=" ", flush=True)
    if not check_ffmpeg():
        print("FEHLER")
        print("FEHLER: ffmpeg ist nicht installiert!")
        sys.exit(1)
    print("OK")

    # Lese Excel
    print(f"\nLese {excel_path}...")
    all_songs = read_excel(excel_path)
    print(f"{len(all_songs)} Songs in Excel gefunden")

    # Nur die ersten 7 Songs
    songs = all_songs[:7]
    print(f"Verwende nur die ersten {len(songs)} Songs für den Test\n")

    for i, song in enumerate(songs, 1):
        duration = song.end_seconds - song.start_seconds
        print(f"  {i}. {song.artist} - {song.title} ({duration}s)")
    print()

    # Timestamps validieren
    print("Validiere Timestamps...", end=" ", flush=True)
    timestamp_errors = validate_timestamps(songs)
    if timestamp_errors:
        print("FEHLER")
        print("\nFEHLER: Ungültige Timestamps:")
        for error in timestamp_errors:
            print(f"  {error}")
        sys.exit(1)
    print("OK")

    # Validiere und lade herunter
    print("\n" + "-" * 50)
    print("Validiere URLs und lade Songs herunter...\n")

    valid_songs = []
    errors = []

    for i, song in enumerate(songs, 1):
        print(f"[{i}/{len(songs)}] {song.artist} - {song.title}")

        # ZUERST prüfen ob bereits vorhanden
        if is_downloaded(song):
            print(f"  [OK] Bereits vorhanden")
            valid_songs.append(song)
            continue

        # Download versuchen
        print(f"  Lade herunter...")
        try:
            download_song(song, browser=browser)
            print(f"  [OK] Heruntergeladen")
            valid_songs.append(song)
        except Exception as e:
            print(f"  [FEHLER] Download-Fehler: {e}")
            errors.append((song, str(e)))

    if len(valid_songs) == 0:
        print("\nKeine gültigen Songs - Abbruch!")
        sys.exit(1)

    print(f"\n{len(valid_songs)}/{len(songs)} Songs erfolgreich validiert/heruntergeladen")

    if errors:
        print(f"\n{len(errors)} Fehler:")
        for song, error in errors:
            print(f"  - {song.artist} - {song.title}: {error}")

    # Song-Pfade sammeln
    song_paths = {}
    for song in valid_songs:
        song_paths[song.filename] = get_download_path(song)

    # Verteile Songs auf Playlists
    print("\n" + "-" * 50)
    print("Verteile Songs auf Playlists...")

    playlists, _ = distribute_with_explicit_assignments(
        valid_songs,
        num_playlists,
        distribution_mode=distribution_mode,
        lead_in_seconds=lead_in_seconds,
        lead_out_seconds=lead_out_seconds
    )

    for i, playlist in enumerate(playlists, 1):
        total_duration = sum(s.end_seconds - s.start_seconds + lead_in_seconds + lead_out_seconds for s in playlist)
        print(f"\nPlaylist {i} ({len(playlist)} Songs, {total_duration}s = {total_duration/60:.1f} min):")
        for song in playlist:
            duration = song.end_seconds - song.start_seconds
            print(f"  - {song.artist} - {song.title} ({duration}s)")

    # Erstelle Output-Ordner
    os.makedirs(output_dir, exist_ok=True)

    # Pfade für Assets
    three_mp3 = os.path.join(assets_dir, "countdown", "three.mp3")
    dancebreak_mp3 = os.path.join(assets_dir, "countdown", "dancebreak.mp3")

    # Prüfe Assets
    print("\n" + "-" * 50)
    print("Prüfe Assets...")

    if not os.path.exists(three_mp3):
        print(f"  [FEHLER] Nicht gefunden: {three_mp3}")
        sys.exit(1)
    print(f"  [OK] {three_mp3}")

    if not os.path.exists(dancebreak_mp3):
        print(f"  [FEHLER] Nicht gefunden: {dancebreak_mp3}")
        sys.exit(1)
    print(f"  [OK] {dancebreak_mp3}")

    if not os.path.exists(cover_image):
        print(f"  [FEHLER] Nicht gefunden: {cover_image}")
        sys.exit(1)
    print(f"  [OK] {cover_image}")

    # Erstelle Audio für jede Playlist
    print("\n" + "-" * 50)
    print("Erstelle Playlists...\n")

    all_chapters = []

    for i, playlist in enumerate(playlists, 1):
        print(f"Playlist {i}:")

        # Audio zusammenfügen
        print(f"  Audio zusammenfügen...", end=" ", flush=True)
        try:
            audio, chapters = build_playlist_audio(
                playlist,
                song_paths,
                three_mp3,
                dancebreak_mp3,
                lead_in_seconds,
                lead_out_seconds,
                use_fade=use_fade
            )
            print("OK")
        except Exception as e:
            print(f"FEHLER: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        all_chapters.append((i, chapters))

        # Halftime-Dateinamen: "01 - Artist - Title (Dancer)"
        song = playlist[0]
        safe_artist = song.artist.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
        safe_title = song.title.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
        safe_dancer = song.dancer_name.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
        base_filename = f"{i:02d} - {safe_artist} - {safe_title} ({safe_dancer})"

        # MP3 exportieren
        mp3_path = os.path.join(output_dir, f"{base_filename}.mp3")
        print(f"  Exportiere MP3...", end=" ", flush=True)
        try:
            export_audio(audio, mp3_path)
            print("OK")
        except Exception as e:
            print(f"FEHLER: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        # Video erstellen
        mp4_path = os.path.join(output_dir, f"{base_filename}.mp4")
        print(f"  Erstelle Video...", end=" ", flush=True)
        try:
            create_video(mp3_path, cover_image, mp4_path)
            print("OK")
        except Exception as e:
            print(f"FEHLER: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # Chapters exportieren
    print("\nErstelle chapters.txt...", end=" ", flush=True)
    try:
        chapters_text = generate_chapters_text(all_chapters)
        chapters_path = os.path.join(output_dir, "chapters.txt")
        with open(chapters_path, 'w', encoding='utf-8') as f:
            f.write(chapters_text)
        print("OK")
    except Exception as e:
        print(f"FEHLER: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 50)
    print("FERTIG!")
    print("=" * 50)
    print(f"\nOutput: {output_dir}/")
    for f in os.listdir(output_dir):
        filepath = os.path.join(output_dir, f)
        size_kb = os.path.getsize(filepath) / 1024
        if size_kb > 1024:
            size_str = f"{size_kb/1024:.1f} MB"
        else:
            size_str = f"{size_kb:.1f} KB"
        print(f"  - {f} ({size_str})")


if __name__ == "__main__":
    main()
