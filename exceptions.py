"""Custom Exceptions für RDG Playlist Maker."""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from excel import Song


class RDGError(Exception):
    """Basis-Exception für RDG Playlist Maker."""
    pass


class ConfigurationError(RDGError):
    """Fehler in der Konfiguration."""
    pass


class ValidationError(RDGError):
    """Fehler bei der URL-Validierung."""

    def __init__(self, song: "Song", message: str, video_title: Optional[str] = None):
        self.song = song
        self.video_title = video_title
        super().__init__(message)


class DownloadError(RDGError):
    """Fehler beim Download."""

    def __init__(self, song: "Song", message: str):
        self.song = song
        super().__init__(message)


class AudioProcessingError(RDGError):
    """Fehler bei der Audio-Verarbeitung."""
    pass


class VideoCreationError(RDGError):
    """Fehler bei der Video-Erstellung."""
    pass


class ExcelParseError(RDGError):
    """Fehler beim Parsen der Excel-Datei."""

    def __init__(self, row_number: int, message: str):
        self.row_number = row_number
        super().__init__(f"Zeile {row_number}: {message}")
