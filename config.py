"""Konfiguration für RDG Playlist Maker."""

import os
from dataclasses import dataclass
from typing import Optional
from constants import (
    DEFAULT_EXCEL, DEFAULT_PLAYLISTS, DEFAULT_LEAD_IN, DEFAULT_LEAD_OUT,
    DEFAULT_DISTRIBUTION_MODE, DEFAULT_OUTPUT_DIR, DEFAULT_ASSETS_DIR,
    DEFAULT_BROWSER, DEFAULT_COVER, DEFAULT_USE_FADE, DEFAULT_EXPORT_INDIVIDUAL,
    DEFAULT_HALFTIME_MODE
)


@dataclass
class PlaylistConfig:
    """Konfiguration für eine Playlist-Erstellung."""

    excel_path: str = DEFAULT_EXCEL
    num_playlists: int = DEFAULT_PLAYLISTS
    lead_in_seconds: int = DEFAULT_LEAD_IN
    lead_out_seconds: int = DEFAULT_LEAD_OUT
    distribution_mode: int = DEFAULT_DISTRIBUTION_MODE
    output_dir: str = DEFAULT_OUTPUT_DIR
    assets_dir: str = DEFAULT_ASSETS_DIR
    browser: Optional[str] = DEFAULT_BROWSER
    cover_image: str = DEFAULT_COVER
    skip_validation: bool = False
    use_fade: bool = DEFAULT_USE_FADE
    export_individual: bool = DEFAULT_EXPORT_INDIVIDUAL
    halftime_mode: bool = DEFAULT_HALFTIME_MODE
    from_file: bool = False

    @property
    def three_mp3_path(self) -> str:
        """Pfad zur three.mp3 Transition."""
        return os.path.join(self.assets_dir, "countdown", "three.mp3")

    @property
    def dancebreak_mp3_path(self) -> str:
        """Pfad zur dancebreak.mp3 Transition."""
        return os.path.join(self.assets_dir, "countdown", "dancebreak.mp3")

    @property
    def image_path(self) -> str:
        """Pfad zum Cover-Bild."""
        return os.path.join(self.assets_dir, "cover", self.cover_image)

    def validate(self) -> list[str]:
        """
        Validiert die Konfiguration.

        Returns:
            Liste von Fehlermeldungen (leer wenn alles OK)
        """
        errors = []

        if self.num_playlists < 1 and not self.halftime_mode:
            errors.append("Anzahl Playlists muss mindestens 1 sein")

        if self.lead_in_seconds < 0:
            errors.append("Einlaufzeit darf nicht negativ sein")

        if self.lead_out_seconds < 0:
            errors.append("Auslaufzeit darf nicht negativ sein")

        if self.distribution_mode not in [1, 2, 3]:
            errors.append("Verteilungsmodus muss 1, 2 oder 3 sein")

        if not os.path.exists(self.excel_path):
            errors.append(f"Excel-Datei nicht gefunden: {self.excel_path}")

        if not os.path.exists(self.three_mp3_path):
            errors.append(f"Transition nicht gefunden: {self.three_mp3_path}")

        if not os.path.exists(self.dancebreak_mp3_path):
            errors.append(f"Transition nicht gefunden: {self.dancebreak_mp3_path}")

        if not os.path.exists(self.image_path):
            errors.append(f"Cover-Bild nicht gefunden: {self.image_path}")

        return errors
