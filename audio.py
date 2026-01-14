"""Audio-Verarbeitung Modul für RDG Playlist Maker."""

import os
from pydub import AudioSegment
from excel import Song


def load_audio(filepath: str) -> AudioSegment:
    """Lädt eine Audio-Datei."""
    return AudioSegment.from_file(filepath)


def cut_audio(audio: AudioSegment, start_seconds: float, end_seconds: float) -> AudioSegment:
    """Schneidet Audio auf den angegebenen Zeitbereich."""
    start_ms = int(start_seconds * 1000)
    end_ms = int(end_seconds * 1000)
    return audio[start_ms:end_ms]


def cut_song(song: Song, audio_path: str) -> AudioSegment:
    """Schneidet einen Song auf die in der Excel definierten Timestamps."""
    audio = load_audio(audio_path)
    start = song.get_start_seconds()
    end = song.get_end_seconds()
    return cut_audio(audio, start, end)


def build_playlist_audio(
    songs: list[Song],
    song_paths: dict[Song, str],
    three_mp3_path: str,
    dancebreak_mp3_path: str,
    progress_callback=None
) -> tuple[AudioSegment, list[dict]]:
    """
    Baut die Playlist-Audio zusammen.

    Für jeden Song:
    - Falls Dancebreak: dancebreak.mp3 einfügen
    - three.mp3 einfügen
    - Geschnittenen Song einfügen

    Returns:
        Tuple von (Audio, Chapter-Liste)
        Chapter-Liste enthält dicts mit {timestamp_ms, artist, title}
    """
    playlist = AudioSegment.empty()
    chapters = []

    three_audio = load_audio(three_mp3_path)
    dancebreak_audio = load_audio(dancebreak_mp3_path)

    for i, song in enumerate(songs):
        if progress_callback:
            progress_callback(i + 1, len(songs), f"Verarbeite: {song.artist} - {song.title}")

        audio_path = song_paths.get(song)
        if not audio_path or not os.path.exists(audio_path):
            print(f"Warnung: Audio nicht gefunden für {song.artist} - {song.title}")
            continue

        # Dancebreak einfügen falls nötig
        if song.is_dancebreak:
            playlist += dancebreak_audio

        # three.mp3 einfügen
        playlist += three_audio

        # Timestamp für Chapter speichern (nach three.mp3)
        chapter_timestamp = len(playlist)

        # Song schneiden und einfügen
        cut_song_audio = cut_song(song, audio_path)
        playlist += cut_song_audio

        chapters.append({
            'timestamp_ms': chapter_timestamp,
            'artist': song.artist,
            'title': song.title,
            'dancer': song.dancer_name
        })

    return playlist, chapters


def export_audio(audio: AudioSegment, output_path: str, format: str = "mp3") -> None:
    """Exportiert Audio in eine Datei."""
    audio.export(output_path, format=format)


def format_timestamp(ms: int) -> str:
    """Formatiert Millisekunden als MM:SS für YouTube-Chapters."""
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def generate_chapters_text(all_playlists_chapters: list[tuple[int, list[dict]]]) -> str:
    """
    Generiert den YouTube-Chapters Text für alle Playlists.

    Args:
        all_playlists_chapters: Liste von (playlist_nummer, chapters_liste)
    """
    lines = []

    for playlist_num, chapters in all_playlists_chapters:
        lines.append(f"=== Playlist {playlist_num} ===")

        for chapter in chapters:
            timestamp = format_timestamp(chapter['timestamp_ms'])
            lines.append(f"{timestamp} {chapter['artist']} - {chapter['title']}")

        lines.append("")  # Leerzeile zwischen Playlists

    return "\n".join(lines)
