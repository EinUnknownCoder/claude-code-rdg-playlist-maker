"""Video-Erstellung Modul für RDG Playlist Maker."""

import subprocess
import shutil
from constants import VIDEO_AUDIO_BITRATE, VIDEO_MAX_HEIGHT


def check_ffmpeg() -> bool:
    """Prüft ob ffmpeg installiert ist."""
    return shutil.which('ffmpeg') is not None


def _escape_drawtext(text: str) -> str:
    """Bereinigt Text für den ffmpeg drawtext-Filter."""
    text = text.replace('\\', '/')
    text = text.replace('%', '%%')
    text = text.replace(':', ' -')
    text = text.replace("'", '\u02bc')  # U+02BC typografisches Apostroph
    return text


def _build_overlay_filter(chapters: list[dict]) -> str:
    """
    Baut den vollständigen ffmpeg -vf Filter-String für Song-Info-Overlay.

    Args:
        chapters: Liste von Chapter-Dicts mit Schlüsseln:
                  timestamp_ms, artist, title, description, dancer

    Returns:
        ffmpeg -vf Filter-String
    """
    parts = [f'scale=-2:{VIDEO_MAX_HEIGHT}']

    for i, chapter in enumerate(chapters):
        start_t = chapter['timestamp_ms'] / 1000
        if i + 1 < len(chapters):
            end_t = chapters[i + 1]['timestamp_ms'] / 1000
        else:
            end_t = 999999

        enable = f"between(t,{start_t:.3f},{end_t:.3f})"

        # Vorheriger Song
        if i > 0:
            prev = chapters[i - 1]
            prev_text = _escape_drawtext(
                f"VORHER: {prev['artist']} - {prev['title']}"
                f" ({prev['description']}, {prev['dancer']})"
            )
        else:
            prev_text = 'VORHER: ---'

        # Aktueller Song
        curr_title = _escape_drawtext(
            f"> JETZT: {chapter['artist']} - {chapter['title']}"
        )
        curr_info = _escape_drawtext(
            f"{chapter['description']} | {chapter['dancer']}"
        )

        # Nächster Song
        if i + 1 < len(chapters):
            nxt = chapters[i + 1]
            next_text = _escape_drawtext(
                f"DANACH: {nxt['artist']} - {nxt['title']}"
                f" ({nxt['description']}, {nxt['dancer']})"
            )
        else:
            next_text = 'DANACH: ---'

        parts += [
            f"drawbox=x=10:y=ih-155:w=iw-20:h=145:color=black@0.6:t=fill:enable='{enable}'",
            f"drawtext=text='{prev_text}':fontsize=15:fontcolor=gray:x=20:y=h-148:enable='{enable}'",
            f"drawtext=text='{curr_title}':fontsize=21:fontcolor=white:x=20:y=h-124:enable='{enable}'",
            f"drawtext=text='{curr_info}':fontsize=15:fontcolor=white@0.85:x=20:y=h-99:enable='{enable}'",
            f"drawtext=text='{next_text}':fontsize=15:fontcolor=cyan:x=20:y=h-71:enable='{enable}'",
        ]

    return ','.join(parts)


def create_video(
    audio_path: str,
    image_path: str,
    output_path: str,
    chapters: list[dict] | None = None,
    progress_callback=None
) -> None:
    """
    Erstellt ein MP4-Video mit einem Standbild und Audio.

    Verwendet ffmpeg direkt für maximale Kompatibilität.

    Args:
        audio_path: Pfad zur MP3-Datei
        image_path: Pfad zum Standbild (JPG)
        output_path: Pfad für das Output-Video (MP4)
        chapters: Optionale Liste von Chapter-Dicts für Song-Info-Overlay.
                  Jedes Dict enthält: timestamp_ms, artist, title,
                  description, dancer
    """
    if not check_ffmpeg():
        raise RuntimeError("ffmpeg ist nicht installiert. Bitte installiere es mit 'brew install ffmpeg'")

    if chapters:
        vf_filter = _build_overlay_filter(chapters)
    else:
        vf_filter = f'scale=-2:{VIDEO_MAX_HEIGHT}'

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
        '-vf', vf_filter,
        '-c:v', 'libx264',
        '-tune', 'stillimage',
        '-c:a', 'aac',
        '-b:a', VIDEO_AUDIO_BITRATE,
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
