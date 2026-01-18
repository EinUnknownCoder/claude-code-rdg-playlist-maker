"""Song-Verteilung Modul für RDG Playlist Maker."""

import random
from collections import defaultdict
from excel import Song


def distribute_songs_fairly(songs: list[Song], num_playlists: int) -> list[list[Song]]:
    """
    Verteilt Songs fair auf mehrere Playlists.

    Algorithmus:
    1. Songs nach Artist gruppieren
    2. Für jeden Artist: Songs zufällig auf die Playlists verteilen (Round-Robin)
    3. Innerhalb jeder Playlist: Songs shufflen

    Ergebnis: Jede Playlist hat möglichst gleichmäßig Songs von verschiedenen Artists.
    """
    if num_playlists <= 0:
        raise ValueError("Anzahl der Playlists muss mindestens 1 sein")

    if not songs:
        return [[] for _ in range(num_playlists)]

    # Songs nach Artist gruppieren
    songs_by_artist = defaultdict(list)
    for song in songs:
        songs_by_artist[song.artist].append(song)

    # Playlists initialisieren
    playlists = [[] for _ in range(num_playlists)]

    # Für jeden Artist: Songs zufällig mischen und dann Round-Robin verteilen
    playlist_index = 0

    for artist, artist_songs in songs_by_artist.items():
        # Songs dieses Artists zufällig mischen
        shuffled_songs = artist_songs.copy()
        random.shuffle(shuffled_songs)

        # Round-Robin über alle Playlists
        for song in shuffled_songs:
            playlists[playlist_index].append(song)
            playlist_index = (playlist_index + 1) % num_playlists

    # Innerhalb jeder Playlist nochmal shufflen für Abwechslung
    for playlist in playlists:
        random.shuffle(playlist)

    return playlists


def distribute_songs_sequentially(songs: list[Song], num_playlists: int) -> list[list[Song]]:
    """
    Verteilt Songs sequentiell (in Excel-Reihenfolge) auf mehrere Playlists.

    Beispiel: Bei 30 Songs und 3 Playlists:
    - Playlist 1: Songs 0-9
    - Playlist 2: Songs 10-19
    - Playlist 3: Songs 20-29
    """
    if num_playlists <= 0:
        raise ValueError("Anzahl der Playlists muss mindestens 1 sein")

    if not songs:
        return [[] for _ in range(num_playlists)]

    # Berechne Songs pro Playlist
    songs_per_playlist = len(songs) // num_playlists
    remainder = len(songs) % num_playlists

    playlists = []
    start_idx = 0

    for i in range(num_playlists):
        # Erste 'remainder' Playlists bekommen einen Song mehr
        playlist_size = songs_per_playlist + (1 if i < remainder else 0)
        end_idx = start_idx + playlist_size

        playlists.append(songs[start_idx:end_idx])
        start_idx = end_idx

    return playlists


def distribute_songs_by_duration(
    songs: list[Song],
    num_playlists: int,
    lead_in_seconds: float = 8,
    lead_out_seconds: float = 2
) -> list[list[Song]]:
    """
    Verteilt Songs so, dass alle Playlists ungefähr gleich lang sind.

    Algorithmus: Greedy - längste Songs zuerst, immer zur kürzesten Playlist.

    Args:
        songs: Liste von Songs
        num_playlists: Anzahl der Playlists
        lead_in_seconds: Sekunden vor dem Start-Timestamp
        lead_out_seconds: Sekunden nach dem End-Timestamp

    Returns:
        Liste von Playlists (jede Playlist ist eine Liste von Songs)
    """
    if num_playlists <= 0:
        raise ValueError("Anzahl der Playlists muss mindestens 1 sein")

    if not songs:
        return [[] for _ in range(num_playlists)]

    def get_song_duration(song: Song) -> float:
        base = song.end_seconds - song.start_seconds
        return base + lead_in_seconds + lead_out_seconds

    # Playlists mit Dauer-Tracking
    playlists = [[] for _ in range(num_playlists)]
    durations = [0.0 for _ in range(num_playlists)]

    # Längste Songs zuerst für bessere Verteilung
    sorted_songs = sorted(songs, key=get_song_duration, reverse=True)

    # Greedy: Immer zur kürzesten Playlist
    for song in sorted_songs:
        min_idx = durations.index(min(durations))
        playlists[min_idx].append(song)
        durations[min_idx] += get_song_duration(song)

    # Shuffle innerhalb jeder Playlist für Abwechslung
    for playlist in playlists:
        random.shuffle(playlist)

    return playlists


def get_distribution_stats(playlists: list[list[Song]]) -> dict:
    """
    Gibt Statistiken über die Verteilung zurück.

    Nützlich zum Prüfen ob die Verteilung fair war.
    """
    stats = {
        'total_songs': sum(len(p) for p in playlists),
        'songs_per_playlist': [len(p) for p in playlists],
        'artists_per_playlist': []
    }

    for playlist in playlists:
        artists = set(song.artist for song in playlist)
        stats['artists_per_playlist'].append(len(artists))

    return stats


def print_distribution_summary(playlists: list[list[Song]]) -> None:
    """Gibt eine Zusammenfassung der Verteilung aus."""
    stats = get_distribution_stats(playlists)

    print(f"Gesamt: {stats['total_songs']} Songs auf {len(playlists)} Playlists")
    print()

    for i, (song_count, artist_count) in enumerate(
        zip(stats['songs_per_playlist'], stats['artists_per_playlist']), 1
    ):
        print(f"Playlist {i}: {song_count} Songs von {artist_count} verschiedenen Artists")


def distribute_with_explicit_assignments(
    songs: list[Song],
    num_playlists: int,
    distribution_mode: int,
    lead_in_seconds: float = 8,
    lead_out_seconds: float = 2
) -> tuple[list[list[Song]], int]:
    """
    Verteilt Songs auf Playlists mit Unterstützung für explizite Zuweisung.

    Songs mit "Playlist X" im dancer_name werden der entsprechenden Playlist zugewiesen.
    Restliche Songs werden nach dem gewählten Verteilungsmodus verteilt.

    Args:
        songs: Liste von Songs
        num_playlists: Anzahl der Playlists
        distribution_mode: 1=Fair, 2=Sequential, 3=Duration
        lead_in_seconds: Sekunden vor dem Start-Timestamp (für Duration-Modus)
        lead_out_seconds: Sekunden nach dem End-Timestamp (für Duration-Modus)

    Returns:
        Tuple aus:
        - Liste von Playlists (jede Playlist ist eine Liste von Songs)
        - Anzahl der explizit zugewiesenen Songs
    """
    if num_playlists <= 0:
        raise ValueError("Anzahl der Playlists muss mindestens 1 sein")

    if not songs:
        return [[] for _ in range(num_playlists)], 0

    # 1. Songs mit expliziter Zuweisung extrahieren
    explicit_songs = defaultdict(list)  # playlist_num -> [songs]
    remaining_songs = []

    for song in songs:
        if song.assigned_playlist and 1 <= song.assigned_playlist <= num_playlists:
            explicit_songs[song.assigned_playlist].append(song)
        else:
            remaining_songs.append(song)

    explicit_count = sum(len(s) for s in explicit_songs.values())

    # 2. Restliche Songs nach gewähltem Modus verteilen
    if distribution_mode == 2:
        playlists = distribute_songs_sequentially(remaining_songs, num_playlists)
    elif distribution_mode == 3:
        playlists = distribute_songs_by_duration(
            remaining_songs, num_playlists, lead_in_seconds, lead_out_seconds
        )
    else:
        playlists = distribute_songs_fairly(remaining_songs, num_playlists)

    # 3. Explizit zugewiesene Songs hinzufügen (am Ende der jeweiligen Playlist)
    for playlist_num, assigned_songs in explicit_songs.items():
        playlists[playlist_num - 1].extend(assigned_songs)

    return playlists, explicit_count


def move_song_to_last(playlist: list[Song], index: int) -> list[Song]:
    """
    Verschiebt einen Song ans Ende der Playlist.

    Args:
        playlist: Liste von Songs
        index: 0-basierter Index des Songs, der ans Ende soll

    Returns:
        Neue Liste mit dem Song am Ende
    """
    if index < 0 or index >= len(playlist):
        raise ValueError(f"Index {index} außerhalb des gültigen Bereichs (0-{len(playlist) - 1})")

    result = playlist.copy()
    song = result.pop(index)
    result.append(song)
    return result
