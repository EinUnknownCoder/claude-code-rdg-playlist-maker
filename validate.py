"""URL-Validierung Modul für RDG Playlist Maker."""

import re
import yt_dlp
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, Callable
from excel import Song

# Pre-kompiliertes Regex-Pattern (Performance-Optimierung)
_NORMALIZE_RE = re.compile(r'[^a-z0-9]')


def normalize_for_comparison(text: str) -> str:
    """
    Normalisiert einen Text für den Vergleich.
    Entfernt Leerzeichen, Sonderzeichen und konvertiert zu lowercase.
    z.B. "Stray Kids" -> "straykids", "NewJeans" -> "newjeans"
    """
    # Zu lowercase und nur Buchstaben/Zahlen behalten
    return _NORMALIZE_RE.sub('', text.lower())


@dataclass
class ValidationResult:
    """Ergebnis einer URL-Validierung."""
    song: Song
    is_valid: bool
    error_message: Optional[str] = None
    video_title: Optional[str] = None


def get_video_info(url: str, browser: Optional[str] = None) -> dict:
    """
    Holt Video-Metadaten von YouTube ohne Download.

    Args:
        url: YouTube URL
        browser: Optional Browser für Cookie-Import (z.B. "chrome", "firefox", "safari")
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        # KEINE Format-Option - YouTube blockt Format-Anfragen bei Validierung
        # Wir brauchen nur title und description, kein Format-Check nötig
    }

    # Browser-Cookies verwenden falls angegeben (gegen YouTube Bot-Detection)
    if browser:
        ydl_opts['cookiesfrombrowser'] = (browser,)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except PermissionError as e:
        # Safari Cookies sind auf macOS durch Sandbox geschützt
        if 'Safari' in str(e):
            raise PermissionError(
                "Safari-Cookies können auf macOS nicht gelesen werden (Sandbox-Schutz). "
                "Bitte verwende Chrome oder Firefox stattdessen."
            )
        raise


def validate_url(song: Song, browser: Optional[str] = None) -> ValidationResult:
    """
    Validiert eine YouTube-URL für einen Song.

    Args:
        song: Song-Objekt mit URL und Metadaten
        browser: Optional Browser für Cookie-Import (z.B. "chrome", "firefox", "safari")

    Prüft:
    1. Ob Artist und Titel im Video-Titel vorkommen
    2. Ob es ein Lyric Video ist (nicht Official MV oder Dance Practice)
    """
    try:
        info = get_video_info(song.youtube_url, browser=browser)
        video_title_original = info.get('title', '')
        video_title = video_title_original.lower()
        video_description = info.get('description', '').lower()

        # Normalisierte Version für Vergleich (ohne Leerzeichen/Sonderzeichen)
        video_title_normalized = normalize_for_comparison(video_title_original)

        # Kombiniere Titel und Beschreibung für die Suche
        search_text = f"{video_title} {video_description}"

        # 1. Prüfe ob Artist im Video-Titel vorkommt (normalisiert)
        artist_normalized = normalize_for_comparison(song.artist)
        if artist_normalized not in video_title_normalized:
            return ValidationResult(
                song=song,
                is_valid=False,
                error_message=f"Artist '{song.artist}' nicht im Video-Titel gefunden",
                video_title=video_title_original
            )

        # 2. Prüfe ob Titel im Video-Titel vorkommt (normalisiert)
        title_normalized = normalize_for_comparison(song.title)
        if title_normalized not in video_title_normalized:
            return ValidationResult(
                song=song,
                is_valid=False,
                error_message=f"Songtitel '{song.title}' nicht im Video-Titel gefunden",
                video_title=video_title_original
            )

        # 3. Prüfe ob es ein Lyric Video ist
        lyric_keywords = ['lyric', 'lyrics', '가사', 'text']
        is_lyric_video = any(kw in video_title for kw in lyric_keywords)

        # 4. Prüfe ob es KEIN Official MV ist
        mv_keywords = ['official mv', 'music video', 'official video', 'm/v', 'official m/v']
        is_official_mv = any(kw in video_title for kw in mv_keywords)

        # 5. Prüfe ob es KEIN Dance Practice ist
        practice_keywords = ['dance practice', 'choreography', 'practice video', 'dance video']
        is_dance_practice = any(kw in video_title for kw in practice_keywords)

        if is_dance_practice:
            return ValidationResult(
                song=song,
                is_valid=False,
                error_message="Dance Practice Video - schlechte Audioqualität",
                video_title=video_title_original
            )

        if is_official_mv and not is_lyric_video:
            return ValidationResult(
                song=song,
                is_valid=False,
                error_message="Official Music Video - kann zusätzliche Soundeffekte enthalten",
                video_title=video_title_original
            )

        if not is_lyric_video:
            return ValidationResult(
                song=song,
                is_valid=False,
                error_message="Kein Lyric Video - bitte Lyric Video URL verwenden",
                video_title=video_title_original
            )

        # Alles OK
        return ValidationResult(
            song=song,
            is_valid=True,
            video_title=video_title_original
        )

    except Exception as e:
        return ValidationResult(
            song=song,
            is_valid=False,
            error_message=f"Fehler beim Abrufen der Video-Info: {str(e)}"
        )


def validate_all_urls(songs: list[Song], progress_callback: Optional[Callable] = None) -> tuple[list[ValidationResult], list[ValidationResult]]:
    """
    Validiert alle URLs in der Song-Liste (sequentiell).

    Returns:
        Tuple von (gültige_songs, ungültige_songs)
    """
    valid = []
    invalid = []

    for i, song in enumerate(songs):
        result = validate_url(song)

        if result.is_valid:
            valid.append(result)
        else:
            invalid.append(result)

        if progress_callback:
            progress_callback(i + 1, len(songs), result)

    return valid, invalid


def validate_urls_parallel(
    songs: list[Song],
    browser: Optional[str] = None,
    max_workers: int = 4,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> tuple[list[Song], list[ValidationResult]]:
    """
    Validiert URLs parallel mit ThreadPoolExecutor.

    Diese Funktion ist ~10x schneller als sequentielle Validierung bei vielen Songs,
    da YouTube API-Aufrufe I/O-bound sind.

    Args:
        songs: Liste von Songs zu validieren
        browser: Optional Browser für Cookie-Import (z.B. "safari", "chrome")
        max_workers: Maximale Anzahl paralleler Threads (Standard: 4, verhindert Rate-Limiting)
        progress_callback: Optional Callback(current, total, message) für Fortschrittsanzeige

    Returns:
        Tuple von (gültige_songs, fehlerhafte_results)
    """
    valid_songs: list[Song] = []
    invalid_results: list[ValidationResult] = []
    completed = 0

    def validate_single(song: Song) -> tuple[Song, ValidationResult]:
        """Validiert einen einzelnen Song (Thread-Worker)."""
        result = validate_url(song, browser=browser)
        return song, result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Alle Validierungen parallel starten
        futures = {executor.submit(validate_single, song): song for song in songs}

        # Ergebnisse sammeln sobald sie fertig sind
        for future in as_completed(futures):
            completed += 1
            song, result = future.result()

            if progress_callback:
                status = "✓" if result.is_valid else f"✗ {result.error_message}"
                progress_callback(completed, len(songs), f"{song.artist} - {song.title}: {status}")

            if result.is_valid:
                valid_songs.append(song)
            else:
                invalid_results.append(result)

    # Sortiere Ergebnisse nach Original-Reihenfolge (row_number)
    valid_songs.sort(key=lambda s: s.row_number)
    invalid_results.sort(key=lambda r: r.song.row_number)

    return valid_songs, invalid_results


def format_validation_errors(invalid_results: list[ValidationResult]) -> str:
    """Formatiert Validierungsfehler für die Anzeige."""
    lines = ["Folgende URLs sind fehlerhaft:\n"]

    for result in invalid_results:
        lines.append(f"Zeile {result.song.row_number}: {result.song.artist} - {result.song.title}")
        lines.append(f"  URL: {result.song.youtube_url}")
        lines.append(f"  Video: {result.video_title or 'N/A'}")
        lines.append(f"  Fehler: {result.error_message}")
        lines.append("")

    return "\n".join(lines)
