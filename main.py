import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QTextEdit,
    QFileDialog, QVBoxLayout, QHBoxLayout, QProgressBar, QSpinBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from align_whisperx import generate_lrc
from generate_vid import generate_lyrics_video
import chroma_video
from pydub import AudioSegment


def parse_timecode_to_seconds(tc: str):
    """
    Parse a timecode string to seconds (float).
    Accepts:
      - "-1" -> returns -1 (special meaning: do not cut end)
      - "MM:SS" or "M:SS" or "MM:SS.sss"
      - "H:MM:SS" or "HH:MM:SS.sss"
    Raises ValueError for invalid formats.
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
            raise ValueError(f"Invalid MM:SS timecode: '{tc}'")
        if seconds < 0 or seconds >= 60:
            # allow seconds >= 60? Usually not. enforce 0-59.999...
            raise ValueError(f"Seconds should be between 0 and <60 in '{tc}'")
        return minutes * 60.0 + seconds
    elif len(parts) == 3:
        # H:MM:SS(.sss)
        h_str, m_str, s_str = parts
        try:
            hours = int(h_str)
            minutes = int(m_str)
            seconds = float(s_str)
        except ValueError:
            raise ValueError(f"Invalid H:MM:SS timecode: '{tc}'")
        if minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
            raise ValueError(f"Minutes/seconds out of range in '{tc}'")
        return hours * 3600.0 + minutes * 60.0 + seconds
    else:
        raise ValueError(f"Invalid timecode format: '{tc}'")


class Worker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, audio_file, text_file, output_dir, bg_video, fps, start_time, speed, bg_color, similarity, blend):
        super().__init__()
        self.audio_file = audio_file
        self.text_file = text_file
        self.output_dir = output_dir
        self.bg_video = bg_video
        self.fps = fps
        self.start_time = start_time   # for chroma overlay start
        self.speed = speed
        self.bg_color = bg_color
        self.similarity = similarity
        self.blend = blend

    def run(self):
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(self.audio_file))[0]

            # 1) LRC
            self.progress.emit("📝 Generating LRC...")
            lrc_path = os.path.join(self.output_dir, f"{base_name}.lrc")
            generate_lrc(self.audio_file, self.text_file, lrc_path)

            # 2) Lyrics video
            self.progress.emit("🎬 Generating lyrics video...")
            lyrics_video_path = os.path.join(self.output_dir, f"{base_name}_lyrics.mp4")
            generate_lyrics_video(
                mp3_path=self.audio_file,
                lrc_path=lrc_path,
                out_path=lyrics_video_path,
                fps=self.fps
            )

            # 3) Optional chroma overlay
            if self.bg_video:
                self.progress.emit("🖌️ Overlaying chroma video...")
                final_path = os.path.join(self.output_dir, f"{base_name}_final.mp4")
                rc, log = chroma_video.overlay_chroma(
                    bg_path=self.bg_video,
                    fg_path=lyrics_video_path,
                    out_path=final_path,
                    start_time=self.start_time,
                    speed=self.speed,
                    similarity=self.similarity,
                    blend=self.blend,
                    bg_color=self.bg_color
                )
                if rc == 0:
                    self.finished.emit(True, final_path)
                else:
                    self.finished.emit(False, log)
            else:
                self.finished.emit(True, lyrics_video_path)

        except Exception as e:
            self.finished.emit(False, str(e))


class KaraokeApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎤 Karaoke Video Generator")
        self.setFixedSize(600, 520)
        self.setStyleSheet("background-color: #1e1e2f; color: #f0f0f0;")

        font_button = QFont("Arial", 10, QFont.Weight.Bold)

        layout = QVBoxLayout()

        # Audio file
        self.audio_input = QLineEdit()
        self.audio_input.setPlaceholderText("Select audio file...")
        self.audio_input.setStyleSheet("background-color: #2e2e44; padding: 5px;")
        btn_audio = QPushButton("Browse")
        btn_audio.setFont(font_button)
        btn_audio.clicked.connect(self.select_audio)
        h_audio = QHBoxLayout()
        h_audio.addWidget(self.audio_input)
        h_audio.addWidget(btn_audio)
        layout.addLayout(h_audio)

        # NEW: Audio start / end timecodes as MM:SS (or H:MM:SS). End = -1 means don't cut the end.
        h_audio_times = QHBoxLayout()
        self.audio_start_input = QLineEdit()
        self.audio_start_input.setPlaceholderText("Start (MM:SS or H:MM:SS) — e.g. 0:12 or 2:15.350")
        self.audio_start_input.setText("0:00")
        self.audio_start_input.setStyleSheet("background-color: #2e2e44; padding: 5px;")

        self.audio_end_input = QLineEdit()
        self.audio_end_input.setPlaceholderText("End (MM:SS or -1 to keep full) — e.g. 3:30 or -1")
        self.audio_end_input.setText("-1")
        self.audio_end_input.setStyleSheet("background-color: #2e2e44; padding: 5px;")

        h_audio_times.addWidget(self.audio_start_input)
        h_audio_times.addWidget(self.audio_end_input)
        layout.addLayout(h_audio_times)

        # Lyrics text box instead of file
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Write or paste lyrics/transcript here...")
        self.text_edit.setStyleSheet("background-color: #2e2e44; padding: 5px;")
        layout.addWidget(self.text_edit)

        # Output directory
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Select output directory...")
        self.output_input.setStyleSheet("background-color: #2e2e44; padding: 5px;")
        btn_output = QPushButton("Browse")
        btn_output.setFont(font_button)
        btn_output.clicked.connect(self.select_output)
        h_output = QHBoxLayout()
        h_output.addWidget(self.output_input)
        h_output.addWidget(btn_output)
        layout.addLayout(h_output)

        # Optional background video
        self.bg_input = QLineEdit()
        self.bg_input.setPlaceholderText("Optional background video...")
        self.bg_input.setStyleSheet("background-color: #2e2e44; padding: 5px;")
        btn_bg = QPushButton("Browse")
        btn_bg.setFont(font_button)
        btn_bg.clicked.connect(self.select_bg)
        h_bg = QHBoxLayout()
        h_bg.addWidget(self.bg_input)
        h_bg.addWidget(btn_bg)
        layout.addLayout(h_bg)

        # Optional parameters (note: the 'Start' here is used for chroma overlay start)
        h_params = QHBoxLayout()
        self.fps_input = QSpinBox()
        self.fps_input.setValue(60)
        self.fps_input.setPrefix("FPS: ")
        self.start_input = QLineEdit()  # keep as text to avoid confusion with mm:ss fields
        self.start_input.setText("15.0")
        self.start_input.setToolTip("Chroma overlay start (seconds) — unchanged behavior")
        self.start_input.setStyleSheet("background-color: #2e2e44; padding: 5px;")
        self.speed_input = QLineEdit()
        self.speed_input.setText("1.25")
        self.speed_input.setToolTip("Chroma overlay speed (float)")
        self.sim_input = QLineEdit()
        self.sim_input.setText("0.25")
        self.sim_input.setToolTip("Chroma similarity (float)")
        self.blend_input = QLineEdit()
        self.blend_input.setText("0.04")
        self.blend_input.setToolTip("Chroma blend (float)")

        # pack small labels with fields for clarity:
        h_params.addWidget(self.fps_input)
        h_params.addWidget(self.start_input)
        h_params.addWidget(self.speed_input)
        h_params.addWidget(self.sim_input)
        h_params.addWidget(self.blend_input)
        layout.addLayout(h_params)

        # Progress bar
        self.progress_label = QLabel("Ready")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #00ff99;
            }
        """)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        # Generate button
        self.btn_generate = QPushButton("Generate Karaoke Video")
        self.btn_generate.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.btn_generate.setStyleSheet("background-color: #00cc99; color: black; padding: 10px;")
        self.btn_generate.clicked.connect(self.generate)
        layout.addWidget(self.btn_generate)

        self.setLayout(layout)

    # File dialogs
    def select_audio(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Audio", "", "Audio Files (*.mp3 *.wav *.flac *.m4a)")
        if file:
            self.audio_input.setText(file)

    def select_output(self):
        dir_ = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_:
            self.output_input.setText(dir_)

    def select_bg(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Background Video", "", "Video Files (*.mp4 *.mov *.avi)")
        if file:
            self.bg_input.setText(file)

    def generate(self):
        self.btn_generate.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting...")

        # Validate lyrics
        lyrics_text = self.text_edit.toPlainText().strip()
        if not lyrics_text:
            self.progress_label.setText("❌ Please write or paste lyrics first!")
            self.btn_generate.setEnabled(True)
            return

        # Validate output dir
        out_dir = self.output_input.text().strip()
        if not out_dir:
            self.progress_label.setText("❌ Please select an output directory!")
            self.btn_generate.setEnabled(True)
            return

        # Validate audio file
        audio_path = self.audio_input.text().strip()
        if not audio_path or not os.path.isfile(audio_path):
            self.progress_label.setText("❌ Please select a valid audio file!")
            self.btn_generate.setEnabled(True)
            return

        # Save transcript from QTextEdit to a temp file
        temp_txt = os.path.join(out_dir, "transcript.txt")
        with open(temp_txt, "w", encoding="utf-8") as f:
            f.write(lyrics_text)

        # Parse audio start/end timecodes in MM:SS (or H:MM:SS) form. End = -1 means keep full length
        start_tc = self.audio_start_input.text().strip()
        end_tc = self.audio_end_input.text().strip()

        try:
            audio_start_s = parse_timecode_to_seconds(start_tc)
            audio_end_s = parse_timecode_to_seconds(end_tc)
        except ValueError as e:
            self.progress_label.setText(f"❌ Timecode error: {e}")
            self.btn_generate.setEnabled(True)
            return

        if audio_start_s < 0 and audio_start_s != -1:
            self.progress_label.setText("❌ Start time must be >= 0.")
            self.btn_generate.setEnabled(True)
            return
        # Note: parse_timecode returns -1 for "-1"; we allow start -1? Not logical; enforce >=0
        if audio_start_s == -1:
            self.progress_label.setText("❌ Start time cannot be -1. Use 0:00 or a valid timecode.")
            self.btn_generate.setEnabled(True)
            return

        if audio_end_s != -1 and audio_end_s <= audio_start_s:
            self.progress_label.setText("❌ End time must be -1 or greater than start time.")
            self.btn_generate.setEnabled(True)
            return

        # Trim audio (if needed) and create trimmed file in output dir
        try:
            self.progress_label.setText("✂️ Trimming audio...")
            self.progress_bar.setValue(5)
            audio = AudioSegment.from_file(audio_path)
            duration_ms = len(audio)
            start_ms = int(audio_start_s * 1000)
            if start_ms >= duration_ms:
                self.progress_label.setText("❌ Start time is after audio duration.")
                self.btn_generate.setEnabled(True)
                return

            if audio_end_s == -1:
                end_ms = None
            else:
                end_ms = int(audio_end_s * 1000)
                if end_ms > duration_ms:
                    end_ms = duration_ms

            if end_ms is None:
                trimmed_segment = audio[start_ms:]
            else:
                trimmed_segment = audio[start_ms:end_ms]

            base_name = os.path.splitext(os.path.basename(audio_path))[0]
            ext = os.path.splitext(audio_path)[1].lstrip('.').lower() or "mp3"
            trimmed_audio_path = os.path.join(out_dir, f"{base_name}_trimmed.{ext}")

            # export trimmed file
            trimmed_segment.export(trimmed_audio_path, format=ext)
            self.progress_bar.setValue(15)
            self.progress_label.setText("✅ Audio trimmed")
        except Exception as e:
            self.progress_label.setText(f"❌ Audio trim error: {e}")
            self.btn_generate.setEnabled(True)
            return

        # Start worker with the trimmed audio path
        # Parse numeric chroma overlay params from text fields
        try:
            chroma_start = float(self.start_input.text())
        except Exception:
            chroma_start = 15.0
        try:
            chroma_speed = float(self.speed_input.text())
        except Exception:
            chroma_speed = 1.25
        try:
            chroma_sim = float(self.sim_input.text())
        except Exception:
            chroma_sim = 0.25
        try:
            chroma_blend = float(self.blend_input.text())
        except Exception:
            chroma_blend = 0.04

        self.worker = Worker(
            audio_file=trimmed_audio_path,
            text_file=temp_txt,
            output_dir=out_dir,
            bg_video=self.bg_input.text() if self.bg_input.text() else None,
            fps=self.fps_input.value(),
            start_time=chroma_start,   # chroma overlay start (unchanged behavior)
            speed=chroma_speed,
            bg_color="00ff00",
            similarity=chroma_sim,
            blend=chroma_blend
        )
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.finish_progress)
        self.worker.start()

    def update_progress(self, msg):
        self.progress_label.setText(msg)
        self.progress_bar.setValue(min(self.progress_bar.value() + 25, 100))

    def finish_progress(self, success, info):
        if success:
            self.progress_label.setText(f"✅ Finished: {info}")
            self.progress_bar.setValue(100)
        else:
            self.progress_label.setText(f"❌ Error: {info}")
        self.btn_generate.setEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KaraokeApp()
    window.show()
    sys.exit(app.exec())