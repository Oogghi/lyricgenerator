#!/usr/bin/env python3
import subprocess
import os
import tempfile
import shlex

# ====== DEFAULT CONFIG ======
BG_COLOR = "00ff00"
DEFAULT_SIMILARITY = 0.70
DEFAULT_BLEND = 0.03
DEFAULT_START = 15.0
DEFAULT_SPEED = 1.25
DEFAULT_CRF = 18
DEFAULT_PRESET = "ultrafast"
DEFAULT_ENCODER = "libx264"

def run_cmd(cmd):
    """Run a command and stream stderr (logging dans /tmp)."""
    logpath = os.path.join(tempfile.gettempdir(), f"ffmpeg_overlay_log_{os.getpid()}.txt")
    with open(logpath, 'w', encoding='utf-8') as flog:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, bufsize=1)
        # stream stderr lines to stdout and log file
        for line in proc.stderr:
            print(line.rstrip())
            flog.write(line)
        proc.wait()
    return proc.returncode, logpath

def get_video_info(path):
    """Retourne (duration, fps, width, height). Raise si ffprobe KO."""
    rc, out = subprocess.getstatusoutput(
        f'ffprobe -v error -select_streams v:0 -show_entries format=duration '
        f'-of default=noprint_wrappers=1:nokey=1 "{path}"'
    )
    if rc != 0:
        raise RuntimeError(f"ffprobe failed for {path}")

    duration = float(out.strip())

    rc2, out2 = subprocess.getstatusoutput(
        f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate '
        f'-of default=noprint_wrappers=1:nokey=1 "{path}"'
    )
    if rc2 != 0:
        width, height, fps = 0, 0, 0
    else:
        lines = out2.strip().split('\n')
        width = int(lines[0])
        height = int(lines[1])
        # r_frame_rate like "30000/1001" or "30/1"
        num, den = map(int, lines[2].split('/'))
        fps = num / den if den != 0 else 0

    return duration, fps, width, height

def _is_audio_copy_safe(fg_path):
    """Teste si l'audio du fg est déjà en AAC (mp4) pour pouvoir le copier ; sinon on réencode."""
    # On inspecte le codec audio via ffprobe
    rc, out = subprocess.getstatusoutput(
        f'ffprobe -v error -select_streams a:0 -show_entries stream=codec_name '
        f'-of default=noprint_wrappers=1:nokey=1 "{fg_path}"'
    )
    if rc != 0 or not out.strip():
        return False
    codec = out.strip().lower()
    return codec in ("aac", "mp3", "opus", "vorbis")  # codecs que l'on peut généralement copier ou garder

def overlay_chroma(bg_path, fg_path, out_path,
                   start_time=DEFAULT_START, speed=DEFAULT_SPEED,
                   similarity=DEFAULT_SIMILARITY, blend=DEFAULT_BLEND,
                   bg_color=BG_COLOR, crf=DEFAULT_CRF, preset=DEFAULT_PRESET,
                   encoder=DEFAULT_ENCODER, short_bg_action='extend_freeze',
                   copy_audio_if_possible=True):
    """
    Overlay fg on bg with chroma key.
    Optimisations pour la vitesse:
      - preset ultrafast (par défaut)
      - threads auto (-threads 0)
      - filter_complex_threads 0 (parallélise les filtres)
      - copie audio si possible pour éviter réencodage audio
    Paramètre `encoder` permet d'indiquer un encodeur matériel (ex: 'h264_nvenc').
    """

    # Get video info
    fg_dur, fg_fps, fg_w, fg_h = get_video_info(fg_path)
    bg_total_dur, bg_fps, main_w, main_h = get_video_info(bg_path)

    # Calculate available portion
    available_source = max(0.0, bg_total_dur - start_time)
    required_source_needed = fg_dur * speed
    need_extend = available_source < required_source_needed

    # Build bg chain (trim/tpad + rallentissement pour correspondre au speed)
    if available_source <= 0.0:
        use_dur = bg_total_dur
        extra_needed = max(0.0, required_source_needed - bg_total_dur)
        bg_chain = f"trim=start=0:duration={use_dur},setpts=PTS-STARTPTS"
        if extra_needed > 0 and short_bg_action == 'extend_freeze':
            bg_chain += f",tpad=stop_mode=clone:stop_duration={extra_needed}"
    else:
        use_dur = min(available_source, required_source_needed)
        bg_chain = f"trim=start={start_time}:duration={use_dur},setpts=PTS-STARTPTS"
        if need_extend and short_bg_action == 'extend_freeze':
            extra_needed = required_source_needed - available_source
            bg_chain += f",tpad=stop_mode=clone:stop_duration={extra_needed}"

    # Après les trims, on adapte la vitesse du background pour produire exactement la durée du foreground.
    # On remet la durée finale sur fg_dur pour être certain.
    bg_chain += f",setpts=PTS/{speed},trim=duration={fg_dur:.6f},setpts=PTS-STARTPTS"

    # Scale filter conservé : on scale le foreground pour qu'il tienne dans la résolution du bg (même logique que toi).
    main_ratio = float(main_w) / float(main_h) if main_h != 0 else 1.0
    ratio_str = f"{main_ratio:.9f}"
    scale_filter = (
        f"scale=if(gt(iw/ih\\,{ratio_str})\\,{main_w}\\,-1):"
        f"if(gt(iw/ih\\,{ratio_str})\\,-1\\,{main_h})"
    )

    # Chroma key filter (on garde chromakey). Format rgba pour overlay propre.
    chroma_filter = f"{scale_filter},chromakey=0x{bg_color}:{similarity}:{blend},format=rgba"

    # Compose le filter_complex
    filter_complex = (
        f"[0:v]{bg_chain}[bg];"
        f"[1:v]{chroma_filter}[fg];"
        f"[bg][fg]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:shortest=1[outv]"
    )

    # Construire la commande ffmpeg optimisée pour la vitesse
    cmd = [
        'ffmpeg', '-y',
        # Maximiser CPU threads et filtrage parallèle
        '-threads', '0',
        '-filter_complex_threads', '0',
        '-i', bg_path,
        '-i', fg_path,
        '-filter_complex', filter_complex,
        '-map', '[outv]',
    ]

    # Audio handling: essayer de copy si possible pour éviter réencodage (plus rapide)
    audio_copied = False
    if copy_audio_if_possible:
        try:
            if _is_audio_copy_safe(fg_path):
                cmd += ['-map', '1:a?', '-c:a', 'copy']
                audio_copied = True
            else:
                # on map audio et on le réencode en AAC (moins cher que certaines conversions)
                cmd += ['-map', '1:a?', '-c:a', 'aac', '-b:a', '192k']
        except Exception:
            # en cas d'erreur d'inspection, on réencode pour garder la robustesse
            cmd += ['-map', '1:a?', '-c:a', 'aac', '-b:a', '192k']
    else:
        # on garde le comportement original (réencode en AAC)
        cmd += ['-map', '1:a?', '-c:a', 'aac', '-b:a', '192k']

    # Video encoder selection: par défaut libx264 + preset ultrafast (très rapide).
    # Si l'utilisateur a passé un encodeur hardware (ex: h264_nvenc), il sera utilisé.
    cmd += ['-c:v', encoder]

    # si libx264, on applique le preset rapide et le crf
    if encoder.lower() in ('libx264', 'libx265', 'x264'):
        cmd += ['-preset', preset, '-crf', str(crf)]
    else:
        # pour accélération matérielle, on met des flags sûrs (éviter flags inconnus qui cassent)
        # On met quand même le crf en option (peut être ignoré selon l'encodeur).
        cmd += ['-crf', str(crf)]
        # Note: si tu veux affiner les presets nvenc/vaapi, passe directement encoder='h264_nvenc'
        # et modifie ici selon ton matériel.

    # accélération du démarrage pour web players
    cmd += ['-movflags', '+faststart']

    # conserver shortest pour arrêter avec la plus courte piste si besoin
    cmd += ['-shortest', out_path]

    # Debug: affiche la commande (utile pour debug/optimisation)
    print("ffmpeg command:", " ".join(shlex.quote(x) for x in cmd))

    return run_cmd(cmd)


# Exemple d'utilisation rapide (à adapter):
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: script.py background.mp4 foreground.mp4 output.mp4")
        sys.exit(1)
    bg, fg, out = sys.argv[1:4]
    # Par défaut rapide : preset ultrafast, libx264.
    # Si tu veux utiliser nvenc (NVIDIA), appelle overlay_chroma(..., encoder='h264_nvenc').
    rc, log = overlay_chroma(bg, fg, out)
    print("ffmpeg rc:", rc, "log:", log)
