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
