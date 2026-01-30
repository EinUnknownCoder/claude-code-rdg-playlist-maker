"""Audio-Verarbeitung Modul für RDG Playlist Maker."""

import os
from pydub import AudioSegment
from pydub.silence import detect_silence
from excel import Song
from constants import (
    TARGET_DBFS, FADE_IN_MS, FADE_OUT_MS,
    SILENCE_THRESH_DB, MIN_SILENCE_LEN_MS
)

# Modul-Level Cache für Transition-Audios (Performance-Optimierung)
_audio_cache: dict[str, AudioSegment] = {}


def load_audio(filepath: str) -> AudioSegment:
    """Lädt eine Audio-Datei."""
    return AudioSegment.from_file(filepath)


def get_cached_audio(filepath: str, strip_silence: bool = False) -> AudioSegment:
    """
    Lädt Audio aus Cache oder lädt und cached es.

    Args:
        filepath: Pfad zur Audio-Datei
        strip_silence: Ob trailing silence entfernt werden soll

    Returns:
        AudioSegment (aus Cache wenn vorhanden)
    """
    cache_key = f"{filepath}:{strip_silence}"
    if cache_key not in _audio_cache:
        audio = load_audio(filepath)
        if strip_silence:
            audio = strip_trailing_silence(audio)
        _audio_cache[cache_key] = audio
    return _audio_cache[cache_key]


def strip_trailing_silence(audio: AudioSegment, silence_thresh: int = SILENCE_THRESH_DB, min_silence_len: int = MIN_SILENCE_LEN_MS) -> AudioSegment:
    """
    Entfernt Stille am Ende eines Audio-Segments.

    Args:
        audio: Audio-Segment
        silence_thresh: Schwellwert in dB für Stille-Erkennung
        min_silence_len: Minimale Stille-Länge in ms
    """
    silences = detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
    if silences and silences[-1][1] == len(audio):
        # Letzte Stille geht bis zum Ende - abschneiden
        return audio[:silences[-1][0]]
    return audio


def cut_audio(audio: AudioSegment, start_seconds: float, end_seconds: float) -> AudioSegment:
    """Schneidet Audio auf den angegebenen Zeitbereich."""
    start_ms = int(start_seconds * 1000)
    end_ms = int(end_seconds * 1000)
    return audio[start_ms:end_ms]


def normalize_audio(audio: AudioSegment, target_dBFS: float = TARGET_DBFS) -> AudioSegment:
    """
    Normalisiert die Lautstärke eines Audio-Segments.

    Args:
        audio: Audio-Segment
        target_dBFS: Ziel-Lautstärke in dBFS (Standard: -14 dBFS)
    """
    change_in_dBFS = target_dBFS - audio.dBFS
    return audio.apply_gain(change_in_dBFS)


def cut_song(song: Song, audio_path: str, lead_in: float = 0, lead_out: float = 0,
             fade_in_ms: int = FADE_IN_MS, fade_out_ms: int = FADE_OUT_MS) -> AudioSegment:
    """
    Schneidet einen Song auf die in der Excel definierten Timestamps.

    Args:
        song: Song-Objekt mit Timestamps
        audio_path: Pfad zur Audio-Datei
        lead_in: Sekunden vor dem Start-Timestamp (Einlaufzeit)
        lead_out: Sekunden nach dem End-Timestamp (Auslaufzeit)
        fade_in_ms: Fade-In Dauer in Millisekunden
        fade_out_ms: Fade-Out Dauer in Millisekunden
    """
    audio = load_audio(audio_path)

    # Start und Ende mit Einlauf-/Auslaufzeit berechnen
    start = max(0, song.get_start_seconds() - lead_in)
    end = min(len(audio) / 1000, song.get_end_seconds() + lead_out)

    # Audio schneiden
    cut = cut_audio(audio, start, end)

    # Lautstärke normalisieren
    cut = normalize_audio(cut)

    # Fade-In und Fade-Out anwenden (nur wenn aktiviert und Song lang genug)
    if fade_in_ms > 0 and len(cut) > fade_in_ms:
        cut = cut.fade_in(fade_in_ms)
    if fade_out_ms > 0 and len(cut) > fade_out_ms:
        cut = cut.fade_out(fade_out_ms)

    return cut


def build_playlist_audio(
    songs: list[Song],
    song_paths: dict[str, str],
    three_mp3_path: str,
    dancebreak_mp3_path: str,
    lead_in_seconds: float = 8,
    lead_out_seconds: float = 2,
    use_fade: bool = True,
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

    # Transitions aus Cache laden (werden nur einmal geladen, dann wiederverwendet)
    three_audio = get_cached_audio(three_mp3_path, strip_silence=True)
    dancebreak_audio = get_cached_audio(dancebreak_mp3_path, strip_silence=False)

    for i, song in enumerate(songs):
        if progress_callback:
            progress_callback(i + 1, len(songs), f"Verarbeite: {song.artist} - {song.title}")

        audio_path = song_paths.get(song.filename)
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

        # Song schneiden und einfügen (mit Einlauf-/Auslaufzeit und optionalem Fade)
        cut_song_audio = cut_song(
            song, audio_path,
            lead_in=lead_in_seconds,
            lead_out=lead_out_seconds,
            fade_in_ms=FADE_IN_MS if use_fade else 0,
            fade_out_ms=FADE_OUT_MS if use_fade else 0
        )
        playlist += cut_song_audio

        chapters.append({
            'timestamp_ms': chapter_timestamp,
            'artist': song.artist,
            'title': song.title,
            'description': song.description,
            'dancer': song.dancer_name
        })

    return playlist, chapters


def export_audio(audio: AudioSegment, output_path: str, format: str = "mp3") -> None:
    """Exportiert Audio in eine Datei."""
    audio.export(output_path, format=format)


def export_individual_songs(
    songs: list[Song],
    song_paths: dict[str, str],
    output_dir: str,
    lead_in_seconds: float = 0,
    lead_out_seconds: float = 0,
    use_fade: bool = False,
    progress_callback=None
) -> None:
    """
    Exportiert jeden Song einzeln als nummerierte MP3-Datei.

    Args:
        songs: Liste der Song-Objekte
        song_paths: Dict mit filename -> audio_path Mapping
        output_dir: Ausgabeverzeichnis
        lead_in_seconds: Sekunden vor dem Start-Timestamp
        lead_out_seconds: Sekunden nach dem End-Timestamp
        use_fade: Ob Fade-In/Out angewendet werden soll
        progress_callback: Optional callback(current, total, message)
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    for i, song in enumerate(songs, 1):
        if progress_callback:
            progress_callback(i, len(songs), f"{song.artist} - {song.title}")

        audio_path = song_paths.get(song.filename)
        if not audio_path or not os.path.exists(audio_path):
            print(f"  ⚠ Datei nicht gefunden: {song.filename}")
            continue

        # Song schneiden (mit optionalem Fade)
        cut_audio = cut_song(
            song, audio_path,
            lead_in=lead_in_seconds,
            lead_out=lead_out_seconds,
            fade_in_ms=FADE_IN_MS if use_fade else 0,
            fade_out_ms=FADE_OUT_MS if use_fade else 0
        )

        # Nummerierter Dateiname: "01 - Artist - Title.mp3"
        # Entferne alle Windows-ungültigen Zeichen: / \ : ? * " < > |
        safe_artist = song.artist.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
        safe_title = song.title.replace("/", "-").replace("\\", "-").replace(":", "-").replace("?", "").replace("*", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")
        output_filename = f"{i:02d} - {safe_artist} - {safe_title}.mp3"
        output_path = os.path.join(output_dir, output_filename)

        export_audio(cut_audio, output_path)
        print(f"  ✓ {output_filename}")


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
    import re

    lines = []
    all_artists = set()

    for playlist_num, chapters in all_playlists_chapters:
        lines.append(f"=== PLAYLIST {playlist_num} ===")

        for i, chapter in enumerate(chapters):
            # Erstes Chapter auf 00:00 für YouTube-Kompatibilität
            if i == 0:
                timestamp = "00:00"
            else:
                timestamp = format_timestamp(chapter['timestamp_ms'])
            artist = chapter['artist'].upper()
            title = chapter['title'].upper()
            description = chapter.get('description', '')
            dancer = chapter.get('dancer', '')
            lines.append(f"{timestamp} {artist} - {title} ({description}, {dancer})")

            # Artist für Hashtags sammeln
            all_artists.add(chapter['artist'])

        lines.append("")  # Leerzeile zwischen Playlists

    # Hashtags generieren (erst normalisieren, dann Duplikate entfernen)
    lines.append("=== HASHTAGS ===")
    hashtag_set = set()
    for artist in all_artists:
        # Entferne Sonderzeichen und Leerzeichen, CAPS LOCK
        safe_artist = re.sub(r'[^\w]', '', artist).upper()
        hashtag_set.add(f"#{safe_artist}")
    # Alphabetisch sortieren
    hashtags = sorted(hashtag_set)
    lines.append(" ".join(hashtags))
    lines.append("")

    return "\n".join(lines)
