"""Konstanten für RDG Playlist Maker."""

import logging

# ==============================================
# Logging-Konfiguration
# ==============================================
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"
LOG_LEVEL = logging.INFO  # Kann auf DEBUG gesetzt werden für mehr Details


def setup_logging(verbose: bool = False) -> None:
    """
    Konfiguriert das Logging für das gesamte Projekt.

    Args:
        verbose: True für DEBUG-Level, False für INFO-Level
    """
    level = logging.DEBUG if verbose else LOG_LEVEL
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT
    )


def get_logger(name: str) -> logging.Logger:
    """
    Gibt einen konfigurierten Logger für ein Modul zurück.

    Args:
        name: Modulname (typischerweise __name__)

    Returns:
        Logger-Instanz
    """
    return logging.getLogger(name)

# ==============================================
# CLI Standardwerte
# ==============================================
DEFAULT_EXCEL = "request.xlsx"
DEFAULT_PLAYLISTS = 4
DEFAULT_LEAD_IN = 8  # Sekunden vor Start-Timestamp
DEFAULT_LEAD_OUT = 2  # Sekunden nach End-Timestamp
DEFAULT_DISTRIBUTION_MODE = 3  # 1=Fair, 2=Sequential, 3=Duration
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_ASSETS_DIR = "assets"
DEFAULT_BROWSER = "chromium"
DEFAULT_COVER = "RDGStuttgart.png"  # Cover-Bild für Video-Export

# ==============================================
# Audio-Verarbeitung
# ==============================================
TARGET_DBFS = -14.0  # Ziel-Lautstärke für Normalisierung
FADE_IN_MS = 2000  # Fade-In Dauer in Millisekunden
FADE_OUT_MS = 2000  # Fade-Out Dauer in Millisekunden
DEFAULT_USE_FADE = True  # Fade-In/Out standardmäßig aktiviert
DEFAULT_EXPORT_INDIVIDUAL = False  # Standard: Playlist-Export (nicht Einzelexport)
DEFAULT_HALFTIME_MODE = False  # Halftime-Modus: 1 Song/Playlist, Sequential, kein Fade
SILENCE_THRESH_DB = -40  # Schwellwert für Stille-Erkennung
MIN_SILENCE_LEN_MS = 100  # Minimale Stille-Länge für Erkennung

# ==============================================
# YouTube Download
# ==============================================
DOWNLOAD_QUALITY = "128"  # MP3 Bitrate in kbps
DOWNLOAD_RETRIES = 10  # Anzahl Retry-Versuche
DOWNLOAD_FRAGMENT_RETRIES = 10  # Retry-Versuche für Fragmente
DOWNLOAD_SLEEP_INTERVAL = 1  # Sekunden Pause zwischen Requests
DOWNLOAD_MAX_SLEEP_INTERVAL = 3  # Maximale Pause

# User-Agent für YouTube-Anfragen
DOWNLOAD_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ==============================================
# Video-Export
# ==============================================
VIDEO_AUDIO_BITRATE = "192k"  # AAC Audio-Bitrate für MP4
VIDEO_MAX_HEIGHT = 480  # Maximale Höhe für exportierte Videos in Pixel
