"""URL-Validierung Modul für RDG Playlist Maker."""

import yt_dlp
from dataclasses import dataclass
from typing import Optional
from excel import Song


@dataclass
class ValidationResult:
    """Ergebnis einer URL-Validierung."""
    song: Song
    is_valid: bool
    error_message: Optional[str] = None
    video_title: Optional[str] = None


def get_video_info(url: str, browser: str = None) -> dict:
    """
    Holt Video-Metadaten von YouTube ohne Download.

    Args:
        url: YouTube URL
        browser: Optional Browser für Cookie-Import (z.B. "chrome", "firefox", "safari")
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
    }

    # Browser-Cookies verwenden falls angegeben (gegen YouTube Bot-Detection)
    if browser:
        ydl_opts['cookiesfrombrowser'] = (browser,)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info


def validate_url(song: Song, browser: str = None) -> ValidationResult:
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
        video_title = info.get('title', '').lower()
        video_description = info.get('description', '').lower()

        # Kombiniere Titel und Beschreibung für die Suche
        search_text = f"{video_title} {video_description}"

        # 1. Prüfe ob Artist im Video-Titel vorkommt
        artist_lower = song.artist.lower()
        if artist_lower not in video_title:
            return ValidationResult(
                song=song,
                is_valid=False,
                error_message=f"Artist '{song.artist}' nicht im Video-Titel gefunden",
                video_title=info.get('title')
            )

        # 2. Prüfe ob Titel im Video-Titel vorkommt
        title_lower = song.title.lower()
        if title_lower not in video_title:
            return ValidationResult(
                song=song,
                is_valid=False,
                error_message=f"Songtitel '{song.title}' nicht im Video-Titel gefunden",
                video_title=info.get('title')
            )

        # 3. Prüfe ob es ein Lyric Video ist
        lyric_keywords = ['lyric', 'lyrics', '가사', 'text', 'แรงอีกนิด', 'remix', 'ทัก']
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
                video_title=info.get('title')
            )

        if is_official_mv and not is_lyric_video:
            return ValidationResult(
                song=song,
                is_valid=False,
                error_message="Official Music Video - kann zusätzliche Soundeffekte enthalten",
                video_title=info.get('title')
            )

        if not is_lyric_video:
            return ValidationResult(
                song=song,
                is_valid=False,
                error_message="Kein Lyric Video - bitte Lyric Video URL verwenden",
                video_title=info.get('title')
            )

        # Alles OK
        return ValidationResult(
            song=song,
            is_valid=True,
            video_title=info.get('title')
        )

    except Exception as e:
        return ValidationResult(
            song=song,
            is_valid=False,
            error_message=f"Fehler beim Abrufen der Video-Info: {str(e)}"
        )


def validate_all_urls(songs: list[Song], progress_callback=None) -> tuple[list[ValidationResult], list[ValidationResult]]:
    """
    Validiert alle URLs in der Song-Liste.

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
