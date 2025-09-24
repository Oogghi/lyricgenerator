import os
from forcealign import ForceAlign

def generate_lrc(audio_file, transcript_file, output_lrc):
    os.makedirs(os.path.dirname(output_lrc), exist_ok=True)

    with open(transcript_file, "r", encoding="utf-8") as f:
        transcript_text = f.read()

    aligner = ForceAlign(audio_file=audio_file, transcript=transcript_text)
    words = aligner.inference()

    with open(output_lrc, "w", encoding="utf-8") as f:
        for word in words:
            start = word.time_start
            minutes = int(start // 60)
            seconds = int(start % 60)
            hundredths = int((start - minutes*60 - seconds) * 100)
            timestamp = f"[{minutes:02d}:{seconds:02d}.{hundredths:02d}]"
            f.write(f"{timestamp}{word.word.lower()}\n")

    print(f"Fichier LRC généré : {output_lrc}")