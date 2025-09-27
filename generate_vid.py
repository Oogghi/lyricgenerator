import os
import re
import subprocess
import librosa
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import av
import sys
import random
import time
random.seed(time.time())

# ========== CONFIG ==========
VIDEO_SIZE = (1080, 1080)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, "fonts")
FONT_NAME = "COMICBD.ttf"
FONT_PATH = os.path.join(FONTS_DIR, FONT_NAME)
FONT_SIZE = 105
TEXT_COLOR = (0, 0, 0)
BG_COLOR = (0, 255, 0)
MARGIN = 0
LINE_SPACING = 80
DEFAULT_FPS = 60


# ========== UTILS ==========
def time_to_seconds(t):
    minutes, seconds = map(float, t.split(":"))
    return minutes * 60 + seconds


def parse_lrc_words(lrc_path):
    with open(lrc_path, encoding="utf-8") as f:
        lines = f.readlines()

    words = []
    for line in lines:
        match = re.match(r"\[(\d+:\d+\.\d+)](.*)", line)
        if match:
            timestamp, word = match.groups()
            word = word.strip()
            if word:
                time = time_to_seconds(timestamp)
                words.append((time, word))
    return words


def justify_text(words, font, max_width, draw):
    lines = []
    current_line = []
    current_width = 0
    space_width = font.getsize(" ")[0]

    for word in words:
        bbox = draw.textbbox((0, 0), word, font=font)
        word_width = bbox[2] - bbox[0]

        total_width = current_width + (space_width if current_line else 0) + word_width
        if total_width > max_width:
            lines.append(current_line)
            current_line = [word]
            current_width = word_width
        else:
            current_line.append(word)
            current_width = total_width

    if current_line:
        lines.append(current_line)
    return lines


def paginate_lines(text_lines):
    """Split lyrics lines into pages of 2–4 lines (not repeating previous count)."""
    pages = {}
    page_index = 0
    start = 0
    prev_count = None

    while start < len(text_lines):
        choices = [1, 2, 3]
        if prev_count in choices:
            choices.remove(prev_count)
        count = random.choice(choices)

        end = min(start + count, len(text_lines))
        pages[page_index] = (start, end)

        prev_count = count
        start = end
        page_index += 1

    return pages


def layout_text(words, font):
    img = Image.new("RGB", VIDEO_SIZE)
    draw = ImageDraw.Draw(img)
    word_positions = []

    text_lines = justify_text([w for _, w in words], font, VIDEO_SIZE[0] - 2 * MARGIN, draw)
    word_index = 0

    for line in text_lines:
        total_word_width = sum(
            draw.textbbox((0, 0), w, font=font)[2] - draw.textbbox((0, 0), w, font=font)[0]
            for w in line
        )
        space_count = len(line) - 1
        space_width = (VIDEO_SIZE[0] - 2 * MARGIN - total_word_width) // space_count if space_count > 0 else 0
        x = MARGIN
        for w in line:
            word_time, word_text = words[word_index]
            word_width = draw.textbbox((0, 0), w, font=font)[2] - draw.textbbox((0, 0), w, font=font)[0]
            word_positions.append((word_time, word_text, x, 0))
            x += word_width + space_width
            word_index += 1

    # Paginate lines with random 2–4 lines
    pages = paginate_lines(text_lines)

    return word_positions, text_lines, pages


def draw_text_frame(word_positions, text_lines, pages, current_time, font):
    SHADOW_COLOR = (255, 255, 255)
    SHADOW_OFFSET = 5

    img = Image.new("RGB", VIDEO_SIZE, BG_COLOR)
    draw = ImageDraw.Draw(img)

    visible_word_indices = [i for i, (t, _, _, _) in enumerate(word_positions) if t <= current_time]
    if not visible_word_indices:
        return np.array(img)

    last_visible_word_idx = visible_word_indices[-1]
    word_to_line = [i for i, line in enumerate(text_lines) for _ in line]
    max_line = word_to_line[last_visible_word_idx]

    # Find current page
    page = None
    for p, (start, end) in pages.items():
        if start <= max_line < end:
            page = p
            break

    if page is None:
        return np.array(img)

    start_line, end_line = pages[page]
    visible_lines = text_lines[start_line:end_line]

    ascent, descent = font.getmetrics()
    line_height = ascent + descent + LINE_SPACING
    total_height = line_height * len(visible_lines) - LINE_SPACING
    y_start = (VIDEO_SIZE[1] - total_height) // 2

    for i in visible_word_indices:
        line_idx = word_to_line[i]
        if start_line <= line_idx < end_line:
            _, word, x, _ = word_positions[i]
            y = y_start + (line_idx - start_line) * line_height
            draw.text((x + SHADOW_OFFSET, y), word, font=font, fill=SHADOW_COLOR)
            draw.text((x, y), word, font=font, fill=TEXT_COLOR)

    return np.array(img)


# ========== MAIN FUNCTION ==========
def generate_lyrics_video(mp3_path, lrc_path, out_path, fps=DEFAULT_FPS, font_gui=FONT_NAME):
    y, sr = librosa.load(mp3_path, sr=None)
    duration = librosa.get_duration(y=y, sr=sr)

    font_name = (font_gui or "").strip()
    if not font_name.endswith(".ttf"):
        font_name += ".ttf"
    font_path = os.path.join(FONTS_DIR, font_name)

    container = av.open(out_path + ".noaudio.mp4", mode="w")
    stream = container.add_stream("libx264", rate=fps)
    stream.width, stream.height = VIDEO_SIZE
    stream.pix_fmt = "yuv420p"

    try:
        font = ImageFont.truetype(font_path, FONT_SIZE)
    except:
        font = ImageFont.load_default()

    words = parse_lrc_words(lrc_path)
    word_positions, text_lines, pages = layout_text(words, font)
    num_frames = int(duration * fps)

    for i in range(num_frames):
        current_time = i / fps
        frame_np = draw_text_frame(word_positions, text_lines, pages, current_time, font)
        frame = av.VideoFrame.from_ndarray(frame_np, format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)

    # Flush encoder
    for packet in stream.encode():
        container.mux(packet)
    container.close()

    # Merge audio with video
    cmd = [
        "ffmpeg", "-y",
        "-i", out_path + ".noaudio.mp4",
        "-i", mp3_path,
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        out_path
    ]
    subprocess.run(cmd, check=True)


# ========== EXAMPLE USAGE ==========
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_vid.py <lrc_path> <mp3_path> [out_path]")
        sys.exit(1)

    lrc_path = sys.argv[1]
    mp3_path = sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else mp3_path.replace(".mp3", "_output.mp4")

    generate_lyrics_video(
        lrc_path=lrc_path,
        mp3_path=mp3_path,
        out_path=out_path

    )
