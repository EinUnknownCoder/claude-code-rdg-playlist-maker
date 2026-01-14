"""Video-Erstellung Modul für RDG Playlist Maker."""

import subprocess
import shutil


def check_ffmpeg() -> bool:
    """Prüft ob ffmpeg installiert ist."""
    return shutil.which('ffmpeg') is not None


def create_video(
    audio_path: str,
    image_path: str,
    output_path: str,
    progress_callback=None
) -> None:
    """
    Erstellt ein MP4-Video mit einem Standbild und Audio.

    Verwendet ffmpeg direkt für maximale Kompatibilität.

    Args:
        audio_path: Pfad zur MP3-Datei
        image_path: Pfad zum Standbild (JPG)
        output_path: Pfad für das Output-Video (MP4)
    """
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg ist nicht installiert. Bitte installiere es mit 'brew install ffmpeg'")

    # ffmpeg-Befehl: Standbild + Audio zu Video
    # -loop 1: Bild wiederholen
    # -i: Input-Dateien
    # -c:v libx264: Video-Codec
    # -tune stillimage: Optimiert für Standbilder
    # -c:a aac: Audio-Codec
    # -b:a 192k: Audio-Bitrate
    # -pix_fmt yuv420p: Pixel-Format für Kompatibilität
    # -shortest: Stoppe wenn kürzester Stream endet (Audio)
    cmd = [
        'ffmpeg',
        '-y',  # Überschreibe ohne Nachfrage
        '-loop', '1',
        '-i', image_path,
        '-i', audio_path,
        '-c:v', 'libx264',
        '-tune', 'stillimage',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        output_path
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg Fehler: {result.stderr}")


def create_all_videos(
    playlist_data: list[tuple[int, str, str]],
    image_path: str,
    progress_callback=None
) -> None:
    """
    Erstellt Videos für alle Playlists.

    Args:
        playlist_data: Liste von (playlist_nummer, mp3_pfad, mp4_pfad)
        image_path: Pfad zum Standbild
    """
    for i, (playlist_num, mp3_path, mp4_path) in enumerate(playlist_data):
        if progress_callback:
            progress_callback(i + 1, len(playlist_data), f"Erstelle Video für Playlist {playlist_num}")

        create_video(mp3_path, image_path, mp4_path)
