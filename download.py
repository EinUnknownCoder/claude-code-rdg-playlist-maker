"""YouTube-Download Modul für RDG Playlist Maker."""

import os
import yt_dlp
from excel import Song


def get_download_path(song: Song, downloads_dir: str = "downloads") -> str:
    """Gibt den Pfad zurück, wo der Song gespeichert wird/ist."""
    return os.path.join(downloads_dir, song.filename)


def is_downloaded(song: Song, downloads_dir: str = "downloads") -> bool:
    """Prüft ob der Song bereits heruntergeladen wurde."""
    return os.path.exists(get_download_path(song, downloads_dir))


def download_song(song: Song, downloads_dir: str = "downloads", progress_callback=None, browser: str = None) -> str:
    """
    Lädt einen Song von YouTube herunter.

    Args:
        song: Song-Objekt mit URL und Metadaten
        downloads_dir: Zielverzeichnis für Downloads
        progress_callback: Optional callback für Progress-Updates
        browser: Optional Browser für Cookie-Import (z.B. "chrome", "firefox", "safari")

    Returns:
        Pfad zur heruntergeladenen MP3-Datei
    """
    os.makedirs(downloads_dir, exist_ok=True)

    output_path = get_download_path(song, downloads_dir)

    # Wenn bereits heruntergeladen, überspringe
    if os.path.exists(output_path):
        return output_path

    # Temporärer Pfad ohne Extension (yt-dlp fügt diese hinzu)
    temp_path = output_path.rsplit('.', 1)[0]

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'outtmpl': temp_path,
        'quiet': True,
        'no_warnings': False,  # Zeige Warnungen für Debugging
        # Retry-Optionen für zuverlässigere Downloads
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        # Sleep interval um Rate Limiting zu vermeiden
        'sleep_interval': 1,
        'max_sleep_interval': 3,
        # User-Agent setzen
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        # Weitere Stabilität
        'nocheckcertificate': True,
        'ignoreerrors': False,
        # Extractor Optionen
        'extract_flat': False,
        'source_address': '0.0.0.0',  # Bind to all interfaces
    }

    # Browser-Cookies verwenden falls angegeben (gegen YouTube Bot-Detection)
    if browser:
        ydl_opts['cookiesfrombrowser'] = (browser,)

    if progress_callback:
        def progress_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    percent = (downloaded / total) * 100
                    progress_callback(percent, f"Downloading: {song.artist} - {song.title}")
            elif d['status'] == 'finished':
                progress_callback(100, f"Converting: {song.artist} - {song.title}")

        ydl_opts['progress_hooks'] = [progress_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([song.youtube_url])

    return output_path


def download_all_songs(songs: list[Song], downloads_dir: str = "downloads",
                       progress_callback=None, browser: str = None) -> dict[Song, str]:
    """
    Lädt alle Songs herunter.

    Returns:
        Dictionary von Song -> Dateipfad
    """
    results = {}

    for i, song in enumerate(songs):
        if progress_callback:
            progress_callback(
                current=i + 1,
                total=len(songs),
                status=f"Downloading: {song.artist} - {song.title}"
            )

        try:
            path = download_song(song, downloads_dir, browser=browser)
            results[song] = path
        except Exception as e:
            print(f"Fehler beim Download von {song.artist} - {song.title}: {e}")
            results[song] = None

    return results
