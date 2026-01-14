"""Excel-Parsing Modul für RDG Playlist Maker."""

from openpyxl import load_workbook
from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class Song:
    """Repräsentiert einen Song-Request aus der Excel-Datei."""
    youtube_url: str
    artist: str
    title: str
    description: str  # Songabschnitt, kann "Dancebreak" enthalten
    dancer_name: str
    start_time: str  # Format: "MM:SS" oder "M:SS"
    end_time: str    # Format: "MM:SS" oder "M:SS"
    row_number: int  # Zeilennummer in der Excel für Fehlermeldungen

    @property
    def is_dancebreak(self) -> bool:
        """Prüft ob dieser Song ein Dancebreak ist."""
        return "dancebreak" in self.description.lower()

    @property
    def filename(self) -> str:
        """Generiert einen sicheren Dateinamen für den Song."""
        safe_artist = re.sub(r'[^\w\s-]', '', self.artist).strip()
        safe_title = re.sub(r'[^\w\s-]', '', self.title).strip()
        return f"{safe_artist} - {safe_title}.mp3"

    def get_start_seconds(self) -> float:
        """Konvertiert Start-Timestamp zu Sekunden."""
        return self._parse_timestamp(self.start_time)

    def get_end_seconds(self) -> float:
        """Konvertiert End-Timestamp zu Sekunden."""
        return self._parse_timestamp(self.end_time)

    def _parse_timestamp(self, timestamp: str) -> float:
        """Parst einen Timestamp (MM:SS oder M:SS) zu Sekunden."""
        parts = timestamp.strip().split(":")
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        elif len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        else:
            raise ValueError(f"Ungültiges Timestamp-Format: {timestamp}")


def read_excel(filepath: str) -> list[Song]:
    """
    Liest die Song-Requests aus einer Excel-Datei.

    Erwartete Spalten (Reihenfolge):
    1. YouTube-URL
    2. Artist
    3. Titel
    4. Songabschnitt/Description
    5. Tänzer-Name
    6. Start-Timestamp
    7. End-Timestamp
    """
    wb = load_workbook(filepath, read_only=True)
    ws = wb.active

    songs = []

    # Überspringe Header-Zeile (Zeile 1)
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # Prüfe ob Zeile leer ist
        if not row or not any(row):
            continue

        # Extrahiere Werte, ersetze None mit leerem String
        values = [str(cell).strip() if cell is not None else "" for cell in row[:7]]

        # Stelle sicher, dass wir genug Spalten haben
        while len(values) < 7:
            values.append("")

        youtube_url, artist, title, description, dancer_name, start_time, end_time = values

        # Überspringe Zeilen ohne URL
        if not youtube_url:
            continue

        song = Song(
            youtube_url=youtube_url,
            artist=artist,
            title=title,
            description=description,
            dancer_name=dancer_name,
            start_time=start_time,
            end_time=end_time,
            row_number=row_num
        )
        songs.append(song)

    wb.close()
    return songs


def validate_timestamps(songs: list[Song]) -> list[str]:
    """
    Validiert die Timestamps aller Songs.
    Gibt eine Liste von Fehlermeldungen zurück.
    """
    errors = []

    for song in songs:
        try:
            start = song.get_start_seconds()
            end = song.get_end_seconds()

            if start >= end:
                errors.append(
                    f"Zeile {song.row_number}: Start-Zeit ({song.start_time}) "
                    f"muss vor End-Zeit ({song.end_time}) liegen - "
                    f"{song.artist} - {song.title}"
                )
        except ValueError as e:
            errors.append(f"Zeile {song.row_number}: {str(e)} - {song.artist} - {song.title}")

    return errors
