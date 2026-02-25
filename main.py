"""RDG Playlist Maker - Hauptprogramm mit CLI."""

import os
import sys
import tomllib
from datetime import datetime
from typing import Optional

CONFIG_FILE = "config.toml"

from tqdm import tqdm
from excel import read_excel, validate_timestamps, Song
from validate import validate_url, format_validation_errors, ValidationResult
from download import download_song, is_downloaded, get_download_path, is_local_file, get_source_path, archive_downloads, is_in_archive, restore_from_archive
from pydub import AudioSegment
from audio import build_playlist_audio, export_audio, generate_chapters_text, cut_song, get_cached_audio, FADE_IN_MS, FADE_OUT_MS
from video import create_video, check_ffmpeg
from distribute import distribute_with_explicit_assignments, move_song_to_last
from config import PlaylistConfig
from constants import (
    DEFAULT_EXCEL, DEFAULT_PLAYLISTS, DEFAULT_LEAD_IN, DEFAULT_LEAD_OUT,
    DEFAULT_DISTRIBUTION_MODE, DEFAULT_OUTPUT_DIR, DEFAULT_ASSETS_DIR,
    DEFAULT_BROWSER, DEFAULT_COVER, DEFAULT_USE_FADE, DEFAULT_EXPORT_INDIVIDUAL,
    DEFAULT_HALFTIME_MODE, DEFAULT_ARCHIVE_DIR
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


def get_available_covers(assets_dir: str = "assets") -> list[str]:
    """Gibt Liste der verfügbaren Cover-Bilder zurück."""
    cover_dir = os.path.join(assets_dir, "cover")
    if not os.path.exists(cover_dir):
        return [DEFAULT_COVER]
    covers = [f for f in os.listdir(cover_dir)
              if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    return sorted(covers)


def parse_cover_selection(input_str: str, available: list[str], default: str) -> str:
    """Parst die Cover-Auswahl (Nummer oder Dateiname)."""
    input_str = input_str.strip()
    # Nummer eingegeben?
    if input_str.isdigit():
        idx = int(input_str) - 1
        if 0 <= idx < len(available):
            return available[idx]
    # Dateiname eingegeben?
    if input_str in available:
        return input_str
    # Default
    return default


def get_output_folder_with_versioning(base_dir: str = "output", project_name: str = None) -> str:
    """
    Fragt nach Projekt-Name und erstellt versionierten Ordner.

    Args:
        base_dir: Basis-Output-Ordner
        project_name: Wenn angegeben, wird interaktive Abfrage übersprungen

    Returns:
        Vollständiger Pfad zum Output-Ordner (z.B. "output/2601 Pforzheim Version 3")
    """
    import re

    if project_name is None:
        # Zeige bestehende Ordner (nur im interaktiven Modus)
        if os.path.exists(base_dir):
            existing = sorted([d for d in os.listdir(base_dir)
                              if os.path.isdir(os.path.join(base_dir, d))])
            if existing:
                print(f"\nBestehende Ordner in {base_dir}/:")
                for folder in existing:
                    print(f"  - {folder}")
                print()

        # Projekt-Name abfragen
        default_project = datetime.now().strftime("%y%m") + " Stuttgart"
        project_name = get_input_with_default("Projekt-Name", default_project)

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
# Config-Datei Loader
# ==============================================

def _load_config_from_file(config_path: str) -> PlaylistConfig:
    """
    Lädt Konfiguration aus einer TOML-Datei.

    Args:
        config_path: Pfad zur TOML-Datei

    Returns:
        PlaylistConfig mit allen Einstellungen, from_file=True
    """
    print(f"Konfigurationsdatei gefunden: {config_path}")
    print("Überspringe interaktive Eingaben.\n")

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    excel_path = raw.get("excel_path", DEFAULT_EXCEL)
    project_name = raw.get("project_name", datetime.now().strftime("%y%m") + " Stuttgart")
    halftime_mode = raw.get("halftime_mode", DEFAULT_HALFTIME_MODE)
    output_base = raw.get("output_dir", DEFAULT_OUTPUT_DIR)
    assets_dir = raw.get("assets_dir", DEFAULT_ASSETS_DIR)
    cover_image = raw.get("cover_image", DEFAULT_COVER)
    skip_validation = raw.get("skip_validation", False)
    use_archive = raw.get("use_archive", False)
    export_individual = raw.get("export_individual", DEFAULT_EXPORT_INDIVIDUAL)
    lead_in_seconds = raw.get("lead_in_seconds", DEFAULT_LEAD_IN)
    lead_out_seconds = raw.get("lead_out_seconds", DEFAULT_LEAD_OUT)
    browser_raw = raw.get("browser", DEFAULT_BROWSER)

    if halftime_mode:
        num_playlists = 0
        distribution_mode = 2
        use_fade = False
    else:
        num_playlists = raw.get("num_playlists", DEFAULT_PLAYLISTS)
        distribution_mode = raw.get("distribution_mode", DEFAULT_DISTRIBUTION_MODE)
        use_fade = raw.get("use_fade", DEFAULT_USE_FADE)

    # Output-Ordner mit Versionierung (nicht-interaktiv)
    output_dir = get_output_folder_with_versioning(output_base, project_name)

    # Browser: leerer String oder unbekannter Wert → None (keine Cookies)
    valid_browsers = ['safari', 'chrome', 'chromium', 'firefox', 'edge', 'opera', 'brave']
    browser: Optional[str] = browser_raw if browser_raw in valid_browsers else None

    # Konfiguration zur Bestätigung ausgeben
    mode_names = {1: "Fair", 2: "Sequential", 3: "Duration"}
    print("Konfiguration:")
    print(f"  Excel:           {excel_path}")
    print(f"  Projekt:         {project_name}")
    if halftime_mode:
        print(f"  Modus:           Halftime (1 Song/Playlist, Sequential, kein Fade)")
    else:
        print(f"  Playlists:       {num_playlists}")
        print(f"  Verteilung:      {distribution_mode} ({mode_names.get(distribution_mode, '?')})")
        print(f"  Fade:            {'Ja' if use_fade else 'Nein'}")
    print(f"  Einlauf:         {lead_in_seconds}s")
    print(f"  Auslauf:         {lead_out_seconds}s")
    print(f"  Cover:           {cover_image}")
    print(f"  Validierung:     {'Übersprungen' if skip_validation else 'Aktiv'}")
    print(f"  Archiv:          {'Aktiv' if use_archive else 'Inaktiv'}")
    print(f"  Export:          {'Einzeln' if export_individual else 'Playlists'}")
    print(f"  Browser:         {browser or 'Keine Cookies'}")
    print()

    return PlaylistConfig(
        excel_path=excel_path,
        num_playlists=num_playlists,
        lead_in_seconds=lead_in_seconds,
        lead_out_seconds=lead_out_seconds,
        distribution_mode=distribution_mode,
        output_dir=output_dir,
        assets_dir=assets_dir,
        browser=browser,
        skip_validation=skip_validation,
        use_archive=use_archive,
        use_fade=use_fade,
        export_individual=export_individual,
        halftime_mode=halftime_mode,
        cover_image=cover_image,
        from_file=True
    )


# ==============================================
# Phasen-Funktionen
# ==============================================

def phase_gather_inputs() -> PlaylistConfig:
    """
    Phase 1: Sammelt alle CLI-Eingaben vom Benutzer.

    Returns:
        PlaylistConfig mit allen Einstellungen
    """
    if os.path.exists(CONFIG_FILE):
        return _load_config_from_file(CONFIG_FILE)

    print("Drücke Enter für Standardwerte:\n")

    excel_path = get_input_with_default("Excel-Datei", DEFAULT_EXCEL)

    # Halftime-Modus abfragen (1 Song pro Playlist, Sequential, kein Fade)
    halftime_input = get_input_with_default(
        "Halftime-Modus? (J/N)", "J" if DEFAULT_HALFTIME_MODE else "N"
    ).strip().upper()
    halftime_mode = halftime_input == "J"

    if halftime_mode:
        print("→ Halftime: 1 Song/Playlist, Sequential, kein Fade")
        num_playlists = 0  # Wird später auf Anzahl Songs gesetzt
        distribution_mode = 2  # Sequential
        use_fade = False
    else:
        num_playlists = get_int_with_default("Anzahl Playlists", DEFAULT_PLAYLISTS)

        # Verteilungsmodus wählen (nur wenn nicht Halftime)
        print("\nVerteilungsmodus:")
        print("  1 = Fair (Artist-balanciert, gemischt)")
        print("  2 = Sequential (Excel-Reihenfolge beibehalten)")
        print("  3 = Duration (gleiche Gesamtdauer pro Playlist)")
        distribution_mode = get_int_with_default("Modus", DEFAULT_DISTRIBUTION_MODE)

    lead_in_seconds = get_int_with_default("Einlaufzeit (Sekunden vor Start)", DEFAULT_LEAD_IN)
    lead_out_seconds = get_int_with_default("Auslaufzeit (Sekunden nach Ende)", DEFAULT_LEAD_OUT)

    # Output-Ordner mit Versionierung
    output_base = get_input_with_default("Output-Ordner Basispfad", DEFAULT_OUTPUT_DIR)
    output_dir = get_output_folder_with_versioning(output_base)
    assets_dir = get_input_with_default("Assets-Ordner", DEFAULT_ASSETS_DIR)

    # Cover-Bild auswählen
    available_covers = get_available_covers(assets_dir)
    print("\nVerfügbare Cover-Bilder:")
    for i, cover in enumerate(available_covers, 1):
        print(f"  {i}. {cover}")

    # Smart Default basierend auf Projektname
    # Extrahiere Projektname aus output_dir (z.B. "output/2601 Stuttgart Version 1" -> "2601 Stuttgart")
    import re
    folder_name = os.path.basename(output_dir)
    project_name = re.sub(r' Version \d+$', '', folder_name).lower()

    if "stuttgart" in project_name or halftime_mode:
        default_cover = "RDGStuttgart.png"
    elif "pforzheim" in project_name:
        default_cover = "PforzheimRPD.jpg"
    elif "goeppingen" in project_name or "göppingen" in project_name:
        default_cover = "ARDGGoeppingen.jpg"
    else:
        default_cover = DEFAULT_COVER

    # Falls Default nicht in verfügbaren Covers, nehme erstes
    if default_cover not in available_covers and available_covers:
        default_cover = available_covers[0]

    cover_input = get_input_with_default(
        f"Cover-Bild (1-{len(available_covers)} oder Dateiname)",
        default_cover
    )
    selected_cover = parse_cover_selection(cover_input, available_covers, default_cover)
    print(f"✓ Cover: {selected_cover}")

    # URL-Validierung überspringen?
    skip_validation_input = get_input_with_default(
        "URL-Validierung überspringen? (J/N)", "N"
    ).strip().upper()
    skip_validation = skip_validation_input == "J"

    if skip_validation:
        print("⚠ URL-Validierung wird übersprungen - nur Download-Check")

    # Archiv als Quelle verwenden?
    use_archive_input = get_input_with_default(
        "Archiv verwenden? (J/N)", "N"
    ).strip().upper()
    use_archive = use_archive_input == "J"

    if use_archive:
        print("→ Fehlende Songs werden aus archive/ kopiert statt von YouTube geladen")

    # Export-Modus (Playlists oder Einzelne Songs)
    export_mode_input = get_input_with_default(
        "Export-Modus: P=Playlists, E=Einzelne Songs", "P" if not DEFAULT_EXPORT_INDIVIDUAL else "E"
    ).strip().upper()
    export_individual = export_mode_input == "E"

    if export_individual:
        print("→ Exportiere jeden Song als separate Datei")

    # Fade-In/Out aktivieren? (nur wenn nicht Halftime)
    if not halftime_mode:
        use_fade_input = get_input_with_default(
            "Fade-In/Out aktivieren? (J/N)", "J" if DEFAULT_USE_FADE else "N"
        ).strip().upper()
        use_fade = use_fade_input == "J"

        if not use_fade:
            print("⚠ Fade-In/Out deaktiviert - Songs starten/enden abrupt")

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
        skip_validation=skip_validation,
        use_archive=use_archive,
        use_fade=use_fade,
        export_individual=export_individual,
        halftime_mode=halftime_mode,
        cover_image=selected_cover
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

        # Lokale Datei? → Nur prüfen ob sie existiert
        if is_local_file(song):
            try:
                source_path = get_source_path(song)
                print(f"  ✓ Lokale Datei: {os.path.basename(source_path)}")
                valid_songs.append(song)
            except FileNotFoundError as e:
                print(f"  ✗ {e}")
                invalid_results.append(ValidationResult(
                    song=song,
                    is_valid=False,
                    error_message=str(e)
                ))
            continue

        # YouTube URL: ZUERST prüfen ob bereits vorhanden
        if is_downloaded(song):
            print(f"  ✓ Bereits vorhanden")
            valid_songs.append(song)
            continue

        # Archiv prüfen (wenn use_archive=True)
        if config.use_archive and is_in_archive(song, config.archive_dir):
            print(f"  ✓ Im Archiv gefunden – wiederherstellen")
            restore_from_archive(song, config.archive_dir)
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

    # Letzten Song für jede Playlist auswählen (nur wenn nicht Halftime und nicht Config-Datei)
    if not config.halftime_mode and not config.from_file:
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

    # Song-Pfade sammeln (lokale Dateien oder Download-Cache)
    song_paths = {}
    for song in valid_songs:
        if is_local_file(song):
            song_paths[song.filename] = get_source_path(song)
        else:
            song_paths[song.filename] = get_download_path(song)

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
                use_fade=config.use_fade,
                progress_callback=progress_callback
            )

        # Dateinamen generieren
        if config.halftime_mode and len(playlist_songs) == 1:
            # Halftime: "01 - Artist - Title (Dancer).mp3"
            song = playlist_songs[0]
            # Sonderzeichen entfernen die in Dateinamen nicht erlaubt sind
            safe_artist = song.artist.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
            safe_title = song.title.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
            safe_dancer = song.dancer_name.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
            base_filename = f"{playlist_num:02d} - {safe_artist} - {safe_title} ({safe_dancer})"
        else:
            # Normal: "Ordnername Playlist X"
            folder_name = os.path.basename(config.output_dir)
            base_filename = f"{folder_name} Playlist {playlist_num}"

        # MP3 exportieren
        mp3_path = os.path.join(config.output_dir, f"{base_filename}.mp3")
        print(f"  MP3 exportieren...", end=" ", flush=True)
        export_audio(audio, mp3_path)
        print("OK")

        # Video erstellen
        mp4_path = os.path.join(config.output_dir, f"{base_filename}.mp4")
        print(f"  Video erstellen...", end=" ", flush=True)
        create_video(mp3_path, config.image_path, mp4_path, chapters=chapters)
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


def phase_export_individual_songs(
    valid_songs: list[Song],
    config: PlaylistConfig
) -> None:
    """
    Phase 6 (Alternative): Exportiert jeden Song einzeln als MP3 und MP4.

    Wird verwendet wenn export_individual=True.
    """
    # Output-Ordner erstellen
    os.makedirs(config.output_dir, exist_ok=True)

    # Song-Pfade sammeln (lokale Dateien oder Download-Cache)
    song_paths = {}
    for song in valid_songs:
        if is_local_file(song):
            song_paths[song.filename] = get_source_path(song)
        else:
            song_paths[song.filename] = get_download_path(song)

    # Countdown-Audio laden
    three_audio = get_cached_audio(config.three_mp3_path, strip_silence=True)
    dancebreak_audio = get_cached_audio(config.dancebreak_mp3_path, strip_silence=False)

    print("\n" + "-" * 50)
    print("Exportiere Songs einzeln (MP3 + MP4)...\n")

    for i, song in enumerate(valid_songs, 1):
        audio_path = song_paths.get(song.filename)
        if not audio_path or not os.path.exists(audio_path):
            print(f"  ⚠ Datei nicht gefunden: {song.filename}")
            continue

        # Song schneiden (keine Einlauf-/Auslaufzeit, optionales Fade)
        cut_audio_segment = cut_song(
            song, audio_path,
            lead_in=0, lead_out=0,
            fade_in_ms=FADE_IN_MS if config.use_fade else 0,
            fade_out_ms=FADE_OUT_MS if config.use_fade else 0
        )

        # Audio zusammenbauen: Dancebreak (optional) + Countdown + Song
        final_audio = AudioSegment.empty()
        if song.is_dancebreak:
            final_audio += dancebreak_audio
        final_audio += three_audio
        final_audio += cut_audio_segment

        # Sicherer Dateiname (Windows-kompatibel)
        safe_artist = song.artist.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
        safe_title = song.title.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
        safe_dancer = song.dancer_name.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
        base_filename = f"{i:02d} - {safe_artist} - {safe_title} ({safe_dancer})"

        # MP3 exportieren
        mp3_path = os.path.join(config.output_dir, f"{base_filename}.mp3")
        export_audio(final_audio, mp3_path)
        print(f"  ✓ {base_filename}.mp3")

        # MP4 Video erstellen
        mp4_path = os.path.join(config.output_dir, f"{base_filename}.mp4")
        single_chapter = [{
            'timestamp_ms': 0,
            'artist': song.artist,
            'title': song.title,
            'description': song.description,
            'dancer': song.dancer_name
        }]
        create_video(mp3_path, config.image_path, mp4_path, chapters=single_chapter)
        print(f"  ✓ {base_filename}.mp4")


def print_summary(config: PlaylistConfig, num_songs: int = None) -> None:
    """Gibt die Abschlussmeldung aus."""
    print("\n" + "=" * 50)
    print("FERTIG!")
    print("=" * 50)
    print(f"\nOutput-Ordner: {config.output_dir}")
    if config.export_individual:
        print(f"  - {num_songs} einzelne MP3-Dateien")
        print(f"  - {num_songs} einzelne MP4-Videos")
    else:
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

    # Halftime-Modus: Anzahl Playlists = Anzahl Songs
    if config.halftime_mode:
        config.num_playlists = len(songs)
        print(f"→ Halftime: {config.num_playlists} Playlists (1 Song pro Playlist)")

    # Phase 4: URLs validieren und Songs herunterladen
    valid_songs, invalid_results = phase_validate_and_download(songs, config)

    # Fehlerbehandlung
    if invalid_results:
        phase_handle_errors(invalid_results, config)

    # Unterschiedlicher Workflow je nach Export-Modus
    if config.export_individual:
        # Einzelexport: Jeden Song einzeln exportieren
        phase_export_individual_songs(valid_songs, config)
    else:
        # Playlist-Export: Songs verteilen und zusammenfügen
        # Phase 5: Songs auf Playlists verteilen
        playlists = phase_distribute_songs(valid_songs, config)

        # Phase 6: Audio zusammenfügen und exportieren
        all_chapters = phase_build_playlists(playlists, valid_songs, config)

        # Phase 7: Chapters-Datei erstellen
        phase_export_chapters(all_chapters, config)

    # Downloads nach archive/ verschieben
    archived = archive_downloads(archive_dir=config.archive_dir)
    if archived > 0:
        print(f"\n{archived} Song(s) nach {config.archive_dir}/ archiviert")

    # Zusammenfassung
    print_summary(config, len(valid_songs) if config.export_individual else None)


if __name__ == "__main__":
    main()
