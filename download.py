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


def download_song(song: Song, downloads_dir: str = "downloads", progress_callback=None) -> str:
    """
    Lädt einen Song von YouTube herunter.

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
        'no_warnings': True,
    }

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
                       progress_callback=None) -> dict[Song, str]:
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
            path = download_song(song, downloads_dir)
            results[song] = path
        except Exception as e:
            print(f"Fehler beim Download von {song.artist} - {song.title}: {e}")
            results[song] = None

    return results
