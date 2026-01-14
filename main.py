"""RDG Playlist Maker - Hauptprogramm mit GUI."""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading

from excel import read_excel, validate_timestamps, Song
from validate import validate_url, format_validation_errors, ValidationResult
from download import download_song, is_downloaded, get_download_path
from audio import build_playlist_audio, export_audio, generate_chapters_text
from video import create_video
from distribute import distribute_songs_fairly, print_distribution_summary


class RDGPlaylistMaker:
    def __init__(self, root):
        self.root = root
        self.root.title("RDG Playlist Maker")
        self.root.geometry("700x600")

        # Standardwerte
        self.default_excel = "request.xlsx"
        self.default_playlists = 3
        self.default_output = "output"
        self.default_assets = "assets"

        self.setup_ui()

    def setup_ui(self):
        """Erstellt die GUI-Elemente."""
        # Main Frame mit Padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        row = 0

        # Excel-Datei
        ttk.Label(main_frame, text="Excel-Datei:").grid(row=row, column=0, sticky="w", pady=5)
        self.excel_var = tk.StringVar(value=self.default_excel)
        excel_entry = ttk.Entry(main_frame, textvariable=self.excel_var, width=50)
        excel_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
        ttk.Button(main_frame, text="...", width=3,
                   command=self.browse_excel).grid(row=row, column=2, pady=5)
        row += 1

        # Anzahl Playlists
        ttk.Label(main_frame, text="Anzahl Playlists:").grid(row=row, column=0, sticky="w", pady=5)
        self.playlists_var = tk.IntVar(value=self.default_playlists)
        playlists_spin = ttk.Spinbox(main_frame, from_=1, to=20, textvariable=self.playlists_var, width=10)
        playlists_spin.grid(row=row, column=1, sticky="w", pady=5, padx=5)
        row += 1

        # Output-Ordner
        ttk.Label(main_frame, text="Output-Ordner:").grid(row=row, column=0, sticky="w", pady=5)
        self.output_var = tk.StringVar(value=self.default_output)
        output_entry = ttk.Entry(main_frame, textvariable=self.output_var, width=50)
        output_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
        ttk.Button(main_frame, text="...", width=3,
                   command=self.browse_output).grid(row=row, column=2, pady=5)
        row += 1

        # Assets-Ordner
        ttk.Label(main_frame, text="Assets-Ordner:").grid(row=row, column=0, sticky="w", pady=5)
        self.assets_var = tk.StringVar(value=self.default_assets)
        assets_entry = ttk.Entry(main_frame, textvariable=self.assets_var, width=50)
        assets_entry.grid(row=row, column=1, sticky="ew", pady=5, padx=5)
        ttk.Button(main_frame, text="...", width=3,
                   command=self.browse_assets).grid(row=row, column=2, pady=5)
        row += 1

        # Separator
        ttk.Separator(main_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        # Fortschrittsbalken
        ttk.Label(main_frame, text="Fortschritt:").grid(row=row, column=0, sticky="w", pady=5)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=row, column=1, columnspan=2, sticky="ew", pady=5, padx=5)
        row += 1

        # Status-Label
        self.status_var = tk.StringVar(value="Bereit")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.grid(row=row, column=0, columnspan=3, sticky="w", pady=5)
        row += 1

        # Log-Bereich
        ttk.Label(main_frame, text="Log:").grid(row=row, column=0, sticky="nw", pady=5)
        self.log_text = scrolledtext.ScrolledText(main_frame, height=15, width=70)
        self.log_text.grid(row=row, column=1, columnspan=2, sticky="nsew", pady=5, padx=5)
        main_frame.rowconfigure(row, weight=1)
        row += 1

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=10)

        self.start_button = ttk.Button(button_frame, text="Playlists erstellen",
                                        command=self.start_processing)
        self.start_button.pack(side="left", padx=5)

        ttk.Button(button_frame, text="Beenden",
                   command=self.root.quit).pack(side="left", padx=5)

    def browse_excel(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Excel-Dateien", "*.xlsx"), ("Alle Dateien", "*.*")]
        )
        if filepath:
            self.excel_var.set(filepath)

    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)

    def browse_assets(self):
        folder = filedialog.askdirectory()
        if folder:
            self.assets_var.set(folder)

    def log(self, message):
        """Fügt eine Nachricht zum Log hinzu."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def set_status(self, status):
        """Setzt den Status-Text."""
        self.status_var.set(status)
        self.root.update_idletasks()

    def set_progress(self, value):
        """Setzt den Fortschrittsbalken."""
        self.progress_var.set(value)
        self.root.update_idletasks()

    def start_processing(self):
        """Startet die Verarbeitung in einem separaten Thread."""
        self.start_button.config(state="disabled")
        self.log_text.delete(1.0, tk.END)
        self.set_progress(0)

        thread = threading.Thread(target=self.process_playlists)
        thread.start()

    def process_playlists(self):
        """Hauptverarbeitungslogik."""
        try:
            excel_path = self.excel_var.get()
            num_playlists = self.playlists_var.get()
            output_dir = self.output_var.get()
            assets_dir = self.assets_var.get()

            # Pfade zu Assets
            three_mp3 = os.path.join(assets_dir, "three.mp3")
            dancebreak_mp3 = os.path.join(assets_dir, "dancebreak.mp3")
            image_path = os.path.join(assets_dir, "RDGStuttgart2.jpg")

            # Prüfe ob Assets existieren
            for asset, name in [(three_mp3, "three.mp3"), (dancebreak_mp3, "dancebreak.mp3"),
                                (image_path, "RDGStuttgart2.jpg")]:
                if not os.path.exists(asset):
                    self.log(f"FEHLER: Asset nicht gefunden: {name}")
                    return

            # 1. Excel einlesen
            self.set_status("Lese Excel-Datei...")
            self.log(f"Lese {excel_path}...")

            songs = read_excel(excel_path)
            self.log(f"{len(songs)} Songs gefunden")

            # Timestamps validieren
            timestamp_errors = validate_timestamps(songs)
            if timestamp_errors:
                self.log("FEHLER: Ungültige Timestamps:")
                for error in timestamp_errors:
                    self.log(f"  {error}")
                return

            # 2. URLs validieren und downloaden
            self.set_status("Validiere URLs und lade Songs herunter...")
            valid_songs = []
            invalid_results = []

            for i, song in enumerate(songs):
                progress = ((i + 1) / len(songs)) * 50  # Erste 50% für Validierung/Download
                self.set_progress(progress)
                self.set_status(f"Validiere: {song.artist} - {song.title}")

                result = validate_url(song)

                if result.is_valid:
                    self.log(f"OK: {song.artist} - {song.title}")

                    # Sofort herunterladen wenn gültig
                    if not is_downloaded(song):
                        self.set_status(f"Lade herunter: {song.artist} - {song.title}")
                        try:
                            download_song(song)
                            self.log(f"  -> Heruntergeladen")
                        except Exception as e:
                            self.log(f"  -> Download-Fehler: {e}")
                            invalid_results.append(ValidationResult(
                                song=song,
                                is_valid=False,
                                error_message=f"Download fehlgeschlagen: {e}"
                            ))
                            continue
                    else:
                        self.log(f"  -> Bereits vorhanden")

                    valid_songs.append(song)
                else:
                    self.log(f"FEHLER: {song.artist} - {song.title}")
                    self.log(f"  -> {result.error_message}")
                    invalid_results.append(result)

            # Wenn Fehler gefunden, stoppen
            if invalid_results:
                self.log("\n" + "=" * 50)
                self.log("STOPP: Fehlerhafte URLs gefunden!")
                self.log("=" * 50)
                self.log(format_validation_errors(invalid_results))
                self.set_status("Fehler gefunden - bitte Excel korrigieren")
                messagebox.showerror(
                    "Fehlerhafte URLs",
                    f"{len(invalid_results)} fehlerhafte URLs gefunden.\n"
                    "Bitte korrigiere die Excel-Datei und starte erneut.\n"
                    "Details im Log."
                )
                return

            # 3. Songs auf Playlists verteilen
            self.set_status("Verteile Songs auf Playlists...")
            self.log(f"\nVerteile {len(valid_songs)} Songs auf {num_playlists} Playlists...")

            playlists = distribute_songs_fairly(valid_songs, num_playlists)

            for i, playlist in enumerate(playlists, 1):
                self.log(f"Playlist {i}: {len(playlist)} Songs")

            # Output-Ordner erstellen
            os.makedirs(output_dir, exist_ok=True)

            # Song-Pfade sammeln
            song_paths = {song: get_download_path(song) for song in valid_songs}

            # 4. Playlists erstellen
            all_chapters = []

            for playlist_num, playlist_songs in enumerate(playlists, 1):
                progress = 50 + ((playlist_num / num_playlists) * 40)  # 50-90% für Audio
                self.set_progress(progress)
                self.set_status(f"Erstelle Playlist {playlist_num}...")
                self.log(f"\nErstelle Playlist {playlist_num}...")

                # Audio zusammenfügen
                audio, chapters = build_playlist_audio(
                    playlist_songs, song_paths, three_mp3, dancebreak_mp3
                )

                # MP3 exportieren
                mp3_path = os.path.join(output_dir, f"playlist_{playlist_num}.mp3")
                self.log(f"  Exportiere MP3: {mp3_path}")
                export_audio(audio, mp3_path)

                # Video erstellen
                mp4_path = os.path.join(output_dir, f"playlist_{playlist_num}.mp4")
                self.log(f"  Erstelle Video: {mp4_path}")
                self.set_status(f"Erstelle Video für Playlist {playlist_num}...")
                create_video(mp3_path, image_path, mp4_path)

                all_chapters.append((playlist_num, chapters))

            # 5. Chapters-Datei erstellen
            self.set_progress(95)
            self.set_status("Erstelle Chapters-Datei...")

            chapters_text = generate_chapters_text(all_chapters)
            chapters_path = os.path.join(output_dir, "chapters.txt")
            with open(chapters_path, 'w', encoding='utf-8') as f:
                f.write(chapters_text)
            self.log(f"\nChapters gespeichert: {chapters_path}")

            # Fertig!
            self.set_progress(100)
            self.set_status("Fertig!")
            self.log("\n" + "=" * 50)
            self.log("FERTIG!")
            self.log(f"Output-Ordner: {output_dir}")
            self.log("=" * 50)

            messagebox.showinfo(
                "Fertig!",
                f"Playlists erfolgreich erstellt!\n\n"
                f"Output-Ordner: {output_dir}\n"
                f"- {num_playlists} MP3-Dateien\n"
                f"- {num_playlists} MP4-Videos\n"
                f"- chapters.txt für YouTube"
            )

        except Exception as e:
            self.log(f"\nFEHLER: {str(e)}")
            self.set_status(f"Fehler: {str(e)}")
            messagebox.showerror("Fehler", str(e))

        finally:
            self.start_button.config(state="normal")


def main():
    root = tk.Tk()
    app = RDGPlaylistMaker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
