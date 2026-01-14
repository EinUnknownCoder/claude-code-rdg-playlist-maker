"""Video-Erstellung Modul für RDG Playlist Maker."""

from moviepy.editor import ImageClip, AudioFileClip


def create_video(
    audio_path: str,
    image_path: str,
    output_path: str,
    progress_callback=None
) -> None:
    """
    Erstellt ein MP4-Video mit einem Standbild und Audio.

    Args:
        audio_path: Pfad zur MP3-Datei
        image_path: Pfad zum Standbild (JPG)
        output_path: Pfad für das Output-Video (MP4)
    """
    # Audio laden
    audio = AudioFileClip(audio_path)

    # Bild laden und auf Audio-Länge setzen
    image = ImageClip(image_path)
    image = image.set_duration(audio.duration)
    image = image.set_audio(audio)

    # Video exportieren
    image.write_videofile(
        output_path,
        fps=1,  # Niedriger FPS da statisches Bild
        codec='libx264',
        audio_codec='aac',
        logger=None if not progress_callback else 'bar'
    )

    # Ressourcen freigeben
    audio.close()
    image.close()


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
