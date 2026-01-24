"""RDG Playlist Maker - Hauptprogramm mit CLI."""

import os
import sys
from typing import Optional

from tqdm import tqdm
from excel import read_excel, validate_timestamps, Song
from validate import validate_url, format_validation_errors, ValidationResult
from download import download_song, is_downloaded, get_download_path
from audio import build_playlist_audio, export_audio, generate_chapters_text
from video import create_video, check_ffmpeg
from distribute import distribute_with_explicit_assignments, move_song_to_last
from config import PlaylistConfig
from constants import (
    DEFAULT_EXCEL, DEFAULT_PLAYLISTS, DEFAULT_LEAD_IN, DEFAULT_LEAD_OUT,
    DEFAULT_DISTRIBUTION_MODE, DEFAULT_OUTPUT_DIR, DEFAULT_ASSETS_DIR,
    DEFAULT_BROWSER, DEFAULT_COVER
)


# ==============================================
# Hilfsfunktionen für CLI-Eingaben
# ==============================================

def print_header() -> None:
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


def get_output_folder_with_versioning(base_dir: str = "output") -> str:
    """
    Fragt nach Projekt-Name und erstellt versionierten Ordner.

    Returns:
        Vollständiger Pfad zum Output-Ordner (z.B. "output/2601 Pforzheim Version 3")
    """
    import re

    # Zeige bestehende Ordner
    if os.path.exists(base_dir):
        existing = sorted([d for d in os.listdir(base_dir)
                          if os.path.isdir(os.path.join(base_dir, d))])
        if existing:
            print(f"\nBestehende Ordner in {base_dir}/:")
            for folder in existing:
                print(f"  - {folder}")
            print()

    # Projekt-Name abfragen
    project_name = input("Projekt-Name (z.B. '2601 Pforzheim'): ").strip()
    if not project_name:
        print("FEHLER: Projekt-Name darf nicht leer sein!")
        sys.exit(1)

    # Finde höchste existierende Version
    pattern = re.compile(rf'^{re.escape(project_name)} Version (\d+)$')
    max_version = 0

    if os.path.exists(base_dir):
        for folder in os.listdir(base_dir):
            match = pattern.match(folder)
            if match:
                version = int(match.group(1))
                max_version = max(max_version, version)

    # Nächste Version
    next_version = max_version + 1
    folder_name = f"{project_name} Version {next_version}"
    full_path = os.path.join(base_dir, folder_name)

    print(f"\n-> Erstelle: {full_path}/")
    return full_path


def select_last_songs(playlists: list[list[Song]]) -> list[list[Song]]:
    """
    Ermöglicht dem Benutzer, für jede Playlist den letzten Song auszuwählen.

    Args:
        playlists: Liste von Playlists (jede Playlist ist eine Liste von Songs)

    Returns:
        Modifizierte Playlists mit neu geordneten Songs
    """
    print("\n" + "-" * 50)
    print("Letzten Song für jede Playlist auswählen")
    print("(Enter drücken = keine Änderung)\n")

    result = []
    for playlist_num, playlist in enumerate(playlists, 1):
        print(f"Playlist {playlist_num} ({len(playlist)} Songs):")
        for i, song in enumerate(playlist, 1):
            dancebreak_marker = " [Dancebreak]" if song.is_dancebreak else ""
            print(f"  {i}. {song.artist} - {song.title} ({song.description}, {song.dancer_name}){dancebreak_marker}")

        while True:
            choice = input(f"\nLetzter Song für Playlist {playlist_num} [Enter = {len(playlist)}]: ").strip()

            if not choice:
                # Keine Änderung, aktueller letzter Song bleibt
                result.append(playlist)
                print(f"  -> Keine Änderung")
                break

            try:
                song_index = int(choice)
                if 1 <= song_index <= len(playlist):
                    # Song ans Ende verschieben (index ist 1-basiert, move_song_to_last erwartet 0-basiert)
                    new_playlist = move_song_to_last(playlist, song_index - 1)
                    result.append(new_playlist)
                    selected = playlist[song_index - 1]
                    print(f"  -> {selected.artist} - {selected.title} wird als letzter Song gesetzt")
                    break
                else:
                    print(f"  Bitte eine Zahl zwischen 1 und {len(playlist)} eingeben.")
            except ValueError:
                print("  Bitte eine gültige Zahl eingeben.")

        print()

    return result


# ==============================================
# Phasen-Funktionen
# ==============================================

def phase_gather_inputs() -> PlaylistConfig:
    """
    Phase 1: Sammelt alle CLI-Eingaben vom Benutzer.

    Returns:
        PlaylistConfig mit allen Einstellungen
    """
    print("Drücke Enter für Standardwerte:\n")

    excel_path = get_input_with_default("Excel-Datei", DEFAULT_EXCEL)
    num_playlists = get_int_with_default("Anzahl Playlists", DEFAULT_PLAYLISTS)
    lead_in_seconds = get_int_with_default("Einlaufzeit (Sekunden vor Start)", DEFAULT_LEAD_IN)
    lead_out_seconds = get_int_with_default("Auslaufzeit (Sekunden nach Ende)", DEFAULT_LEAD_OUT)

    # Verteilungsmodus wählen
    print("\nVerteilungsmodus:")
    print("  1 = Fair (Artist-balanciert, gemischt)")
    print("  2 = Sequential (Excel-Reihenfolge beibehalten)")
    print("  3 = Duration (gleiche Gesamtdauer pro Playlist)")
    distribution_mode = get_int_with_default("Modus", DEFAULT_DISTRIBUTION_MODE)

    # Output-Ordner mit Versionierung
    output_base = get_input_with_default("Output-Ordner Basispfad", DEFAULT_OUTPUT_DIR)
    output_dir = get_output_folder_with_versioning(output_base)
    assets_dir = get_input_with_default("Assets-Ordner", DEFAULT_ASSETS_DIR)

    # URL-Validierung überspringen?
    skip_validation_input = get_input_with_default(
        "URL-Validierung überspringen? (J/N)", "N"
    ).strip().upper()
    skip_validation = skip_validation_input == "J"

    if skip_validation:
        print("⚠ URL-Validierung wird übersprungen - nur Download-Check")

    # Browser für Cookie-Import (gegen YouTube Bot-Detection)
    print("\nBrowser für Cookie-Import (gegen YouTube Bot-Detection):")
    print("  safari = Safari (empfohlen)")
    print("  chrome = Google Chrome/Chromium")
    print("  firefox = Mozilla Firefox")
    print("  edge = Microsoft Edge")
    print("  [leer] = Keine Cookies verwenden")
    browser_input = get_input_with_default("Browser", DEFAULT_BROWSER).strip().lower()

    browser: Optional[str] = browser_input if browser_input in ['safari', 'chrome', 'firefox', 'edge', 'opera', 'brave'] else None

    if browser:
        print(f"✓ Verwende Cookies aus {browser.title()}")
    else:
        print("⚠ Keine Browser-Cookies - kann bei YouTube Bot-Detection fehlschlagen")

    return PlaylistConfig(
        excel_path=excel_path,
        num_playlists=num_playlists,
        lead_in_seconds=lead_in_seconds,
        lead_out_seconds=lead_out_seconds,
        distribution_mode=distribution_mode,
        output_dir=output_dir,
        assets_dir=assets_dir,
        browser=browser,
        skip_validation=skip_validation
    )


def phase_validate_prerequisites(config: PlaylistConfig) -> None:
    """
    Phase 2: Prüft alle Voraussetzungen.

    Beendet das Programm bei Fehlern.
    """
    # Prüfe ffmpeg
    if not check_ffmpeg():
        print("FEHLER: ffmpeg ist nicht installiert!")
        print("Bitte installiere es mit: brew install ffmpeg")
        sys.exit(1)

    print("\n" + "-" * 50)
    print("Prüfe Voraussetzungen...")

    # Prüfe ob Dateien existieren
    errors = config.validate()
    if errors:
        for error in errors:
            print(f"FEHLER: {error}")
        sys.exit(1)

    print("Alle Dateien gefunden!")


def phase_parse_excel(config: PlaylistConfig) -> list[Song]:
    """
    Phase 3: Liest und validiert die Excel-Datei.

    Returns:
        Liste von Song-Objekten
    """
    print("\n" + "-" * 50)
    print(f"Lese {config.excel_path}...")

    songs = read_excel(config.excel_path)
    print(f"{len(songs)} Songs gefunden")

    # Timestamps validieren
    timestamp_errors = validate_timestamps(songs)
    if timestamp_errors:
        print("\nFEHLER: Ungültige Timestamps:")
        for error in timestamp_errors:
            print(f"  {error}")
        sys.exit(1)

    return songs


def phase_validate_and_download(
    songs: list[Song],
    config: PlaylistConfig
) -> tuple[list[Song], list[ValidationResult]]:
    """
    Phase 4: Validiert URLs und lädt Songs herunter.

    Returns:
        Tuple von (gültige Songs, Fehler-Ergebnisse)
    """
    print("\n" + "-" * 50)
    print("Validiere URLs und lade Songs herunter...\n")

    valid_songs = []
    invalid_results = []

    for i, song in enumerate(songs, 1):
        print(f"[{i}/{len(songs)}] {song.artist} - {song.title}")

        # ZUERST prüfen ob bereits vorhanden
        if is_downloaded(song):
            print(f"  ✓ Bereits vorhanden")
            valid_songs.append(song)
            continue

        # URL validieren (nur wenn nicht übersprungen)
        if not config.skip_validation:
            result = validate_url(song, browser=config.browser)

            if not result.is_valid:
                print(f"  ✗ {result.error_message}")
                invalid_results.append(result)
                continue
            else:
                print(f"  ✓ URL gültig")

        # Download versuchen
        print(f"  ⬇ Lade herunter...")
        try:
            download_song(song, browser=config.browser)
            print(f"  ✓ Heruntergeladen")
            valid_songs.append(song)
        except Exception as e:
            print(f"  ✗ Download-Fehler: {e}")
            invalid_results.append(ValidationResult(
                song=song,
                is_valid=False,
                error_message=f"Download fehlgeschlagen: {e}"
            ))

    return valid_songs, invalid_results


def phase_handle_errors(
    invalid_results: list[ValidationResult],
    config: PlaylistConfig
) -> None:
    """
    Behandelt Validierungs-/Download-Fehler.

    Beendet das Programm nach Fehlerausgabe.
    """
    print("\n" + "=" * 50)
    print("STOPP: Fehlerhafte URLs gefunden!")
    print("=" * 50)
    error_message = format_validation_errors(invalid_results)
    print(error_message)

    # Fehlerliste als Textdatei exportieren
    os.makedirs(config.output_dir, exist_ok=True)
    errors_path = os.path.join(config.output_dir, "errors.txt")
    with open(errors_path, 'w', encoding='utf-8') as f:
        f.write("RDG Playlist Maker - Fehlerliste\n")
        f.write("=" * 50 + "\n\n")
        f.write(error_message)
    print(f"\nFehlerliste gespeichert: {errors_path}")

    print("\nBitte korrigiere die Excel-Datei und starte erneut.")
    print("Bereits heruntergeladene Songs bleiben gecacht.")
    sys.exit(1)


def phase_distribute_songs(
    valid_songs: list[Song],
    config: PlaylistConfig
) -> list[list[Song]]:
    """
    Phase 5: Verteilt Songs auf Playlists.

    Returns:
        Liste von Playlists (jede Playlist ist eine Liste von Songs)
    """
    print("\n" + "-" * 50)

    mode_names = {1: "fair", 2: "sequentiell", 3: "nach Dauer"}
    mode_name = mode_names.get(config.distribution_mode, "fair")
    print(f"Verteile {len(valid_songs)} Songs {mode_name} auf {config.num_playlists} Playlists...\n")

    playlists, explicit_count = distribute_with_explicit_assignments(
        valid_songs, config.num_playlists, config.distribution_mode,
        config.lead_in_seconds, config.lead_out_seconds
    )

    if explicit_count > 0:
        print(f"  → {explicit_count} Song(s) wurden explizit zugewiesen (via 'Playlist X' im Requester-Feld)\n")

    for i, playlist in enumerate(playlists, 1):
        artists = set(s.artist for s in playlist)
        duration_sec = sum(
            (s.end_seconds - s.start_seconds + config.lead_in_seconds + config.lead_out_seconds)
            for s in playlist
        )
        duration_min = duration_sec / 60
        print(f"Playlist {i}: {len(playlist)} Songs, ~{duration_min:.1f} min, {len(artists)} Artists")

    # Letzten Song für jede Playlist auswählen
    playlists = select_last_songs(playlists)

    return playlists


def phase_build_playlists(
    playlists: list[list[Song]],
    valid_songs: list[Song],
    config: PlaylistConfig
) -> list[tuple[int, list[dict]]]:
    """
    Phase 6: Baut Audio zusammen und exportiert MP3/MP4.

    Returns:
        Liste von (playlist_nummer, chapters_liste) für alle Playlists
    """
    # Output-Ordner erstellen
    os.makedirs(config.output_dir, exist_ok=True)

    # Song-Pfade sammeln (nach Dateiname)
    song_paths = {song.filename: get_download_path(song) for song in valid_songs}

    print("\n" + "-" * 50)
    print("Erstelle Playlists...\n")

    all_chapters = []

    for playlist_num, playlist_songs in enumerate(playlists, 1):
        print(f"Playlist {playlist_num}/{config.num_playlists}:")

        # Audio zusammenfügen mit Fortschrittsanzeige
        with tqdm(total=len(playlist_songs), desc="  Songs verarbeiten", unit="song",
                  bar_format="  {desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:

            def progress_callback(current: int, total: int, message: str) -> None:
                pbar.update(1)

            audio, chapters = build_playlist_audio(
                playlist_songs, song_paths,
                config.three_mp3_path, config.dancebreak_mp3_path,
                lead_in_seconds=config.lead_in_seconds,
                lead_out_seconds=config.lead_out_seconds,
                progress_callback=progress_callback
            )

        # MP3 exportieren
        mp3_path = os.path.join(config.output_dir, f"playlist_{playlist_num}.mp3")
        print(f"  MP3 exportieren...", end=" ", flush=True)
        export_audio(audio, mp3_path)
        print("OK")

        # Video erstellen
        mp4_path = os.path.join(config.output_dir, f"playlist_{playlist_num}.mp4")
        print(f"  Video erstellen...", end=" ", flush=True)
        create_video(mp3_path, config.image_path, mp4_path)
        print("OK")

        print()

        all_chapters.append((playlist_num, chapters))

    return all_chapters


def phase_export_chapters(
    all_chapters: list[tuple[int, list[dict]]],
    config: PlaylistConfig
) -> None:
    """
    Phase 7: Erstellt die Chapters-Datei für YouTube.
    """
    print("\n" + "-" * 50)
    print("Erstelle Chapters-Datei...")

    chapters_text = generate_chapters_text(all_chapters)
    chapters_path = os.path.join(config.output_dir, "chapters.txt")
    with open(chapters_path, 'w', encoding='utf-8') as f:
        f.write(chapters_text)


def print_summary(config: PlaylistConfig) -> None:
    """Gibt die Abschlussmeldung aus."""
    print("\n" + "=" * 50)
    print("FERTIG!")
    print("=" * 50)
    print(f"\nOutput-Ordner: {config.output_dir}")
    print(f"  - {config.num_playlists} MP3-Dateien")
    print(f"  - {config.num_playlists} MP4-Videos")
    print(f"  - chapters.txt für YouTube")
    print()


# ==============================================
# Hauptprogramm
# ==============================================

def main() -> None:
    """Hauptprogramm - orchestriert alle Phasen."""
    print_header()

    # Phase 1: Eingaben sammeln
    config = phase_gather_inputs()

    # Phase 2: Voraussetzungen prüfen
    phase_validate_prerequisites(config)

    # Phase 3: Excel einlesen
    songs = phase_parse_excel(config)

    # Phase 4: URLs validieren und Songs herunterladen
    valid_songs, invalid_results = phase_validate_and_download(songs, config)

    # Fehlerbehandlung
    if invalid_results:
        phase_handle_errors(invalid_results, config)

    # Phase 5: Songs auf Playlists verteilen
    playlists = phase_distribute_songs(valid_songs, config)

    # Phase 6: Audio zusammenfügen und exportieren
    all_chapters = phase_build_playlists(playlists, valid_songs, config)

    # Phase 7: Chapters-Datei erstellen
    phase_export_chapters(all_chapters, config)

    # Zusammenfassung
    print_summary(config)


if __name__ == "__main__":
    main()
