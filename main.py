import sys
import json
import os
import yt_dlp
import re
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QTextEdit,
    QFileDialog, QVBoxLayout, QHBoxLayout, QProgressBar, QSpinBox, QComboBox
)
from PyQt6.QtGui import QFont, QKeySequence
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from pydub import AudioSegment

# Try to import dependencies
HAS_DEPS = True
try:
    from force_align import generate_lrc
    from generate_vid import generate_lyrics_video
    import chroma_video
except ImportError:
    HAS_DEPS = False

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

# Worker (only works if deps exist)
if HAS_DEPS:
    class Worker(QThread):
        progress = pyqtSignal(str)
        finished = pyqtSignal(bool, str)

        def __init__(self, audio_file, text_file, output_dir, fps, bg_video, chroma_start,
                     chroma_speed, chroma_sim, chroma_blend, font_name, encoder, preset):
            super().__init__()
            self.audio_file = audio_file
            self.text_file = text_file
            self.output_dir = output_dir
            self.fps = fps
            self.bg_video = bg_video
            self.chroma_start = chroma_start
            self.chroma_speed = chroma_speed
            self.chroma_sim = chroma_sim
            self.chroma_blend = chroma_blend
            self.font_name = font_name
            self.encoder = encoder
            self.preset = preset

        def run(self):
            try:
                os.makedirs(self.output_dir, exist_ok=True)
                base_name = os.path.splitext(os.path.basename(self.audio_file))[0]

                # 1) LRC
                self.progress.emit("📝 Génération du fichier LRC...")
                lrc_path = os.path.join(self.output_dir, f"{base_name}.lrc")
                generate_lrc(self.audio_file, self.text_file, lrc_path)

                # 2) Lyrics video
                self.progress.emit("🎬 Génération de la vidéo des paroles...")
                lyrics_video_path = os.path.join(self.output_dir, f"{base_name}_lyrics.mp4")
                generate_lyrics_video(
                    mp3_path=self.audio_file,
                    lrc_path=lrc_path,
                    out_path=lyrics_video_path,
                    fps=self.fps,
                    font_gui=self.font_name
                )

                # 3) Optional chroma overlay
                if self.bg_video:
                    self.progress.emit("🖌️ Superposition de la vidéo...")
                    final_path = os.path.join(self.output_dir, f"{base_name}_final.mp4")
                    rc, log = chroma_video.overlay_chroma(
                        bg_path=self.bg_video,
                        fg_path=lyrics_video_path,
                        out_path=final_path,
                        start_time=self.chroma_start,
                        speed=self.chroma_speed,
                        similarity=self.chroma_sim,
                        blend=self.chroma_blend,
                        bg_color="00ff00",
                        encoder=self.encoder,
                        preset=self.preset
                    )
                    if rc == 0:
                        self.finished.emit(True, final_path)
                    else:
                        self.finished.emit(False, log)
                else:
                    self.finished.emit(True, lyrics_video_path)

            except Exception as e:
                self.finished.emit(False, str(e))

class PlainTextEdit(QTextEdit):
    def insertFromMimeData(self, source):
        if source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)

class CustomTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.setFixedHeight(40)
        self.setStyleSheet("background-color: #2c3e50;")

        # Titre
        self.title_label = QLabel("🎶 Générateur de paroles par Oogghi", self)
        self.title_label.setStyleSheet("color: white; background: transparent;")
        self.title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))

        # Boutons
        self.btn_minimize = QPushButton("−")
        self.btn_close = QPushButton("✕")

        for btn, color, hover_color in [
            (self.btn_minimize, "#f39c12", "#e67e22"),
            (self.btn_close, "#e74c3c", "#c0392b"),
        ]:
            btn.setFixedSize(30, 30)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
            """)

        # Connexions
        self.btn_close.clicked.connect(self.parent.close)
        self.btn_minimize.clicked.connect(self.parent.showMinimized)

        # Layout
        h_layout = QHBoxLayout(self)
        h_layout.setContentsMargins(10, 0, 10, 0)
        h_layout.addWidget(self.title_label)
        h_layout.addStretch()
        h_layout.addWidget(self.btn_minimize)
        h_layout.addWidget(self.btn_close)

        self.startPos = None

    def toggle_maximize_restore(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.startPos = event.globalPosition()
            self.clickPos = self.mapToParent(event.position().toPoint())

    def mouseMoveEvent(self, event):
        if self.startPos:
            diff = event.globalPosition() - self.startPos
            self.parent.move(self.parent.pos() + diff.toPoint())
            self.startPos = event.globalPosition()

    def mouseReleaseEvent(self, event):
        self.startPos = None

class KaraokeApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎶 Générateur de paroles par Oogghi")
        self.setFixedSize(780, 720)
        self.setMinimumSize(780, 720)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("background-color: black; color: white;")

        layout = QVBoxLayout()

        self.title_bar = CustomTitleBar(self)

        layout.addWidget(self.title_bar)

        # --- Audio file
        h_audio = QHBoxLayout()
        h_audio.addWidget(QLabel("Fichier audio :"))
        self.audio_input = QLineEdit()
        self.audio_input.setPlaceholderText("Sélectionnez un fichier audio ou collez le lien d'une video youtube...")
        self.audio_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")
        btn_audio = QPushButton("Parcourir")
        btn_audio.clicked.connect(self.select_audio)
        h_audio.addWidget(self.audio_input)
        h_audio.addWidget(btn_audio)
        layout.addLayout(h_audio)

        # --- Start/end time
        h_time = QHBoxLayout()
        h_time.addWidget(QLabel("Début :"))
        self.audio_start_input = QLineEdit()
        self.audio_start_input.setPlaceholderText("MM:SS")
        self.audio_start_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")
        h_time.addWidget(self.audio_start_input)

        h_time.addWidget(QLabel("Fin :"))
        self.audio_end_input = QLineEdit()
        self.audio_end_input.setPlaceholderText("MM:SS ou -1")
        self.audio_end_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")
        h_time.addWidget(self.audio_end_input)
        layout.addLayout(h_time)

        # --- Lyrics text
        layout.addWidget(QLabel("Paroles :"))
        self.text_edit = PlainTextEdit()
        self.text_edit.setPlaceholderText("Écrivez ou collez les paroles ici...")
        self.text_edit.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")
        layout.addWidget(self.text_edit)

        # --- Output dir
        h_output = QHBoxLayout()
        h_output.addWidget(QLabel("Nom du projet :"))
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Entrez le nom du projet...")
        self.output_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")
        h_output.addWidget(self.output_input)
        layout.addLayout(h_output)

        # --- Background video
        h_bg = QHBoxLayout()
        h_bg.addWidget(QLabel("Vidéo de fond :"))
        self.bg_input = QLineEdit()
        self.bg_input.setPlaceholderText("Sélectionnez une vidéo de fond ou collez le lien d'une video youtube (optionnelle)...")
        self.bg_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")
        btn_bg = QPushButton("Parcourir")
        btn_bg.clicked.connect(self.select_bg)
        h_bg.addWidget(self.bg_input)
        h_bg.addWidget(btn_bg)
        layout.addLayout(h_bg)

        # --- Params container (vertical)
        params_layout = QVBoxLayout()

        # --- First row (FPS + Chroma settings)
        h_params1 = QHBoxLayout()

        h_params1.addWidget(QLabel("FPS :"))
        self.fps_input = QSpinBox()
        self.fps_input.setValue(60)
        h_params1.addWidget(self.fps_input)

        h_params1.addWidget(QLabel("Début de la vidéo de fond (s) :"))
        self.chroma_start_input = QLineEdit("15.0")
        self.chroma_start_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")
        h_params1.addWidget(self.chroma_start_input)

        h_params1.addWidget(QLabel("Vitesse :"))
        self.chroma_speed_input = QLineEdit("1.25")
        self.chroma_speed_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")
        h_params1.addWidget(self.chroma_speed_input)

        h_params1.addWidget(QLabel("Similarité :"))
        self.chroma_sim_input = QLineEdit("0.25")
        self.chroma_sim_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")
        h_params1.addWidget(self.chroma_sim_input)

        params_layout.addLayout(h_params1)

        # --- Second row (Similarity + Blend + Font + Encoder)
        h_params2 = QHBoxLayout()

        h_params2.addWidget(QLabel("Fusion :"))
        self.chroma_blend_input = QLineEdit("0.04")
        self.chroma_blend_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")
        h_params2.addWidget(self.chroma_blend_input)

        h_params2.addWidget(QLabel("Police :"))
        self.font_input = QComboBox()
        self.font_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")

        fonts_folder = "fonts"
        if os.path.exists(fonts_folder):
            for font_file in os.listdir(fonts_folder):
                if font_file.endswith(".ttf") or font_file.endswith(".otf"):
                    font_name = font_file.split('.')[0]
                    self.font_input.addItem(font_name)

        h_params2.addWidget(self.font_input)
        self.font_input.setCurrentText("COMICBD")

        h_params2.addWidget(QLabel("Encodeur :"))
        self.encoder_input = QComboBox()
        self.encoder_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")

        self.encoder_input.addItems([
            # CPU
            "libx264",
            "libx265",
            "mpeg4",
            "vp8",
            "vp9",
            "av1",

            # NVIDIA
            "h264_nvenc",
            "hevc_nvenc",

            # AMD
            "h264_amf",
            "hevc_amf",

            # Intel QuickSync
            "h264_qsv",
            "hevc_qsv"
        ])
        self.encoder_input.setCurrentText("libx264")
        h_params2.addWidget(self.encoder_input)

        h_params2.addWidget(QLabel("Preset :"))
        self.preset_input = QComboBox()
        self.preset_input.setStyleSheet("background-color: #222; padding: 6px; border-radius: 4px;")

        self.preset_input.addItems([
            "ultrafast",
            "superfast",
            "veryfast",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow"
        ])
        self.preset_input.setCurrentText("ultrafast")
        h_params2.addWidget(self.preset_input)

        params_layout.addLayout(h_params2)
        layout.addLayout(params_layout)

        # --- Progress
        self.progress_label = QLabel("Prêt")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 5px;
                text-align: center;
                background-color: #111;
            }
            QProgressBar::chunk {
                background-color: #007BFF;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        # --- Generate button
        self.btn_generate = QPushButton("Générer la vidéo karaoké")
        self.btn_generate.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #007BFF;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #3399FF;
            }
            QPushButton:pressed {
                background-color: #0056b3;
            }
        """)
        self.btn_generate.clicked.connect(self.generate)
        layout.addWidget(self.btn_generate)

        self.setLayout(layout)

        self.load_settings()

    def load_settings(self):
        """Charge les réglages depuis settings.json (s'ils existent)"""
        try:
            if not os.path.exists(SETTINGS_PATH):
                return

            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                s = json.load(f)

            # champs textuels
            self.audio_input.setText(s.get("audio_input", ""))
            self.audio_start_input.setText(s.get("audio_start_input", ""))
            self.audio_end_input.setText(s.get("audio_end_input", ""))
            self.text_edit.setPlainText(s.get("text_edit", ""))
            self.output_input.setText(s.get("output_input", ""))
            self.bg_input.setText(s.get("bg_input", ""))

            # numériques / spinbox
            try:
                self.fps_input.setValue(int(s.get("fps", self.fps_input.value())))
            except Exception:
                pass

            # chroma params (gardés en string)
            self.chroma_start_input.setText(s.get("chroma_start", self.chroma_start_input.text()))
            self.chroma_speed_input.setText(s.get("chroma_speed", self.chroma_speed_input.text()))
            self.chroma_sim_input.setText(s.get("chroma_sim", self.chroma_sim_input.text()))
            self.chroma_blend_input.setText(s.get("chroma_blend", self.chroma_blend_input.text()))

            # combo boxes (setCurrentText marche même si l'item n'existe pas)
            self.font_input.setCurrentText(s.get("font_name", self.font_input.currentText()))
            self.encoder_input.setCurrentText(s.get("encoder", self.encoder_input.currentText()))
            self.preset_input.setCurrentText(s.get("preset", self.preset_input.currentText()))

        except Exception as e:
            # ne pas planter l'UI si le fichier est corrompu
            print("Erreur load_settings:", e)

    def save_settings(self):
        """Sauvegarde les réglages actuels dans settings.json (atomique)"""
        try:
            s = {
                "audio_input": self.audio_input.text().strip(),
                "audio_start_input": self.audio_start_input.text().strip(),
                "audio_end_input": self.audio_end_input.text().strip(),
                "text_edit": self.text_edit.toPlainText(),
                "output_input": self.output_input.text().strip(),
                "bg_input": self.bg_input.text().strip(),
                "fps": self.fps_input.value(),
                "chroma_start": self.chroma_start_input.text().strip(),
                "chroma_speed": self.chroma_speed_input.text().strip(),
                "chroma_sim": self.chroma_sim_input.text().strip(),
                "chroma_blend": self.chroma_blend_input.text().strip(),
                "font_name": self.font_input.currentText(),
                "encoder": self.encoder_input.currentText(),
                "preset": self.preset_input.currentText()
            }

            tmp_path = SETTINGS_PATH + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(s, f, ensure_ascii=False, indent=2)

            # opération atomique (remplace le fichier)
            os.replace(tmp_path, SETTINGS_PATH)

        except Exception as e:
            print("Erreur save_settings:", e)

    def closeEvent(self, event):
        """
        Sauvegarde les réglages quand l'utilisateur ferme la fenêtre
        (appelé automatiquement par Qt)
        """
        try:
            self.save_settings()
        except Exception as e:
            print("Erreur lors de la sauvegarde à la fermeture:", e)
        # accepter la fermeture
        event.accept()

    # --- File dialogs
    def select_audio(self):
        file, _ = QFileDialog.getOpenFileName(self, "Sélectionner l'audio", "", "Fichiers audio (*.mp3 *.wav *.flac *.m4a)")
        if file:
            self.audio_input.setText(file)

    def get_output_dir(self) -> str:
        """Compute the real output folder path inside songs/."""
        project_name = sanitize_filename(self.project_input.text())
        if not project_name:
            project_name = "default_project"
        output_dir = os.path.join("songs", project_name)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def select_bg(self):
        file, _ = QFileDialog.getOpenFileName(self, "Sélectionner la vidéo de fond", "", "Fichiers vidéo (*.mp4 *.mov *.avi)")
        if file:
            self.bg_input.setText(file)

    def parse_timecode_to_seconds(tc: str):
        """
        Convertit une chaîne timecode en secondes (float).
        Acceptés :
        - "-1" -> retourne -1 (sens spécial : ne pas tronquer la fin)
        - "MM:SS" ou "M:SS" ou "MM:SS.sss"
        - "H:MM:SS" ou "HH:MM:SS.sss"
        Lève ValueError pour les formats invalides.
        """
        s = tc.strip()
        if s == "" or s == "-1":
            return -1

        parts = s.split(":")
        if len(parts) == 2:
            # MM:SS(.sss)
            m_str, s_str = parts
            try:
                minutes = int(m_str)
                seconds = float(s_str)
            except ValueError:
                raise ValueError(f"Timecode MM:SS invalide : '{tc}'")
            if seconds < 0 or seconds >= 60:
                raise ValueError(f"Les secondes doivent être entre 0 et <60 dans '{tc}'")
            return minutes * 60.0 + seconds

        elif len(parts) == 3:
            # H:MM:SS(.sss)
            h_str, m_str, s_str = parts
            try:
                hours = int(h_str)
                minutes = int(m_str)
                seconds = float(s_str)
            except ValueError:
                raise ValueError(f"Timecode H:MM:SS invalide : '{tc}'")
            if minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
                raise ValueError(f"Minutes/secondes hors plage dans '{tc}'")
            return hours * 3600.0 + minutes * 60.0 + seconds

        else:
            raise ValueError(f"Format de timecode invalide : '{tc}'")
        
    def is_youtube_url(self, url):
        pattern = r"(https?://)?(www\.)?(youtube\.com|youtu\.?be)/.+"
        return re.match(pattern, url) is not None

    def download_youtube_audio(self, url, output_dir):
        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }],
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return os.path.splitext(filename)[0] + ".mp3"
        except Exception as e:
            self.progress_label.setText(f"❌ Erreur téléchargement audio: {e}")
            return None

    def download_youtube_video(self, url, output_dir):
        try:
            ydl_opts = {
                "format": "bestvideo[ext=mp4]+bestaudio/best",
                "merge_output_format": "mp4",
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return filename
        except Exception as e:
            self.progress_label.setText(f"❌ Erreur téléchargement vidéo: {e}")
            return None

    # --- Generate logic
    def generate(self):
        self.btn_generate.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Démarrage...")
        QApplication.processEvents()
        self.progress_bar.setValue(1)

        audio_path = self.audio_input.text().strip()
        if not audio_path:
            self.progress_label.setText("❌ Sélectionnez un fichier audio ou collez un lien YouTube !")
            self.btn_generate.setEnabled(True)
            return

        if not os.path.isfile(audio_path):
            if not self.is_youtube_url(audio_path):
                self.progress_label.setText("❌ Sélectionnez un fichier audio valide ou un lien YouTube !")
                self.btn_generate.setEnabled(True)
                return

        lyrics_text = self.text_edit.toPlainText().strip()
        if not lyrics_text:
            self.progress_label.setText("❌ Écrivez ou collez les paroles d'abord !")
            self.btn_generate.setEnabled(True)
            return

        out_dir = self.get_output_dir().strip()
        if not out_dir:
            self.progress_label.setText("❌ Sélectionnez un dossier de sortie !")
            self.btn_generate.setEnabled(True)
            return

        if not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        if self.is_youtube_url(audio_path):
            self.progress_label.setText("🔽 Connexion pour téléchargement audio...")
            QApplication.processEvents()
            self.progress_bar.setValue(5)

            self.progress_label.setText("🔽 Téléchargement audio...")
            QApplication.processEvents()
            audio_path = self.download_youtube_audio(audio_path, out_dir)
            if not audio_path:
                self.btn_generate.setEnabled(True)
                return
            self.audio_input.setText(audio_path)

            self.progress_label.setText("✅ Audio téléchargé")
            QApplication.processEvents()
            self.progress_bar.setValue(10)

        bg_path = self.bg_input.text().strip()
        if bg_path and self.is_youtube_url(bg_path):
            self.progress_label.setText("🔽 Connexion pour téléchargement vidéo...")
            QApplication.processEvents()
            self.progress_bar.setValue(12)

            self.progress_label.setText("🔽 Téléchargement vidéo...")
            QApplication.processEvents()
            bg_path = self.download_youtube_video(bg_path, out_dir)
            if not bg_path:
                self.btn_generate.setEnabled(True)
                return
            self.bg_input.setText(bg_path)

            self.progress_label.setText("✅ Vidéo téléchargée")
            QApplication.processEvents()
            self.progress_bar.setValue(13)

        temp_txt = os.path.join(out_dir, "transcript.txt")
        with open(temp_txt, "w", encoding="utf-8") as f:
            f.write(lyrics_text)

        try:
            start_tc = self.audio_start_input.text().strip()
            end_tc = self.audio_end_input.text().strip()
            audio_start_s = KaraokeApp.parse_timecode_to_seconds(start_tc)
            self.progress_bar.setValue(15)
            QApplication.processEvents()

            audio_end_s = KaraokeApp.parse_timecode_to_seconds(end_tc)
            self.progress_bar.setValue(20)
        except ValueError as e:
            self.progress_label.setText(f"❌ Erreur de timecode : {e}")
            self.btn_generate.setEnabled(True)
            return

        try:
            self.progress_label.setText("✂️ Lecture audio...")
            QApplication.processEvents()
            audio = AudioSegment.from_file(audio_path)
            self.progress_bar.setValue(30)

            self.progress_label.setText("✂️ Découpe audio...")
            QApplication.processEvents()
            start_ms = int(audio_start_s * 1000)
            end_ms = int(audio_end_s * 1000) if audio_end_s != -1 else None
            trimmed_segment = audio[start_ms:end_ms] if end_ms else audio[start_ms:]
            self.progress_bar.setValue(40)

            ext = os.path.splitext(audio_path)[1].lstrip('.').lower()
            base_name = os.path.splitext(os.path.basename(audio_path))[0]
            trimmed_audio_path = os.path.join(out_dir, f"{base_name}_trimmed.{ext}")

            self.progress_label.setText("✂️ Export audio...")
            QApplication.processEvents()
            trimmed_segment.export(trimmed_audio_path, format=ext)
            self.progress_bar.setValue(50)

            self.progress_label.setText("✅ Audio découpé")
            QApplication.processEvents()
            self.progress_bar.setValue(65)
        except Exception as e:
            self.progress_label.setText(f"❌ Erreur découpe audio : {e}")
            self.btn_generate.setEnabled(True)
            return

        try:
            chroma_start = float(self.chroma_start_input.text().strip())
            chroma_speed = float(self.chroma_speed_input.text().strip())
            chroma_sim = float(self.chroma_sim_input.text().strip())
            chroma_blend = float(self.chroma_blend_input.text().strip())
        except ValueError as e:
            self.progress_label.setText(f"❌ Erreur paramètres chroma : {e}")
            self.btn_generate.setEnabled(True)
            return

        self.progress_bar.setValue(80)

        self.worker = Worker(
            audio_file=trimmed_audio_path,
            text_file=temp_txt,
            output_dir=out_dir,
            fps=self.fps_input.value(),
            bg_video=self.bg_input.text().strip() or None,
            chroma_start=chroma_start,
            chroma_speed=chroma_speed,
            chroma_sim=chroma_sim,
            chroma_blend=chroma_blend,
            font_name=self.font_input.currentText(),
            encoder=self.encoder_input.currentText(),
            preset=self.preset_input.currentText()
        )
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.finish_progress)
        self.worker.start()

    # petites fonctions utilitaires pour mettre à jour l'UI depuis le worker
    def update_progress(self, message: str):
        self.progress_label.setText(message)
        # on augmente légèrement la barre pour donner du feedback ; le worker émet des étapes
        current = self.progress_bar.value()
        self.progress_bar.setValue(min(100, current + 10))

    def finish_progress(self, success: bool, payload: str):
        if success:
            self.progress_label.setText(f"✅ Terminé : {payload}")
            self.progress_bar.setValue(100)
        else:
            self.progress_label.setText(f"❌ Erreur : {payload}")
            self.progress_bar.setValue(0)
        self.btn_generate.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KaraokeApp()
    window.show()

    sys.exit(app.exec())
