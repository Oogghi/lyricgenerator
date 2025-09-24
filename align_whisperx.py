import os
import re
from num2words import num2words
from forcealign import ForceAlign

def preprocess_transcript(transcript_file, processed_file):
    """
    lit le transcript original et transforme les nombres en mots pour ForceAlign
    """
    with open(transcript_file, "r", encoding="utf-8") as f:
        text = f.read()

    # transformer tous les nombres en mots
    def replace_number(match):
        num = int(match.group(0))
        return num2words(num)

    processed_text = re.sub(r"\b\d+\b", replace_number, text)

    os.makedirs(os.path.dirname(processed_file), exist_ok=True)
    with open(processed_file, "w", encoding="utf-8") as f:
        f.write(processed_text)

def generate_lrc(audio_file, transcript_file, output_lrc):
    # créer version preprocess pour ForceAlign
    preprocessed_transcript = transcript_file.replace(".txt", "_fa.txt")
    preprocess_transcript(transcript_file, preprocessed_transcript)

    # forcealign
    aligner = ForceAlign(audio_file=audio_file, transcript=open(preprocessed_transcript, "r", encoding="utf-8").read())
    words = aligner.inference()

    # générer LRC avec le texte original (pas les nombres transformés)
    with open(transcript_file, "r", encoding="utf-8") as f:
        original_words = [w for w in f.read().split() if w.strip()]

    with open(output_lrc, "w", encoding="utf-8") as f:
        for i, word in enumerate(words):
            start = word.time_start
            minutes = int(start // 60)
            seconds = int(start % 60)
            hundredths = int((start - minutes*60 - seconds) * 100)
            timestamp = f"[{minutes:02d}:{seconds:02d}.{hundredths:02d}]"

            # récupérer le mot original, en lower, en enlevant uniquement les points et virgules
            orig_word = original_words[i].lower().replace(",", "").replace(".", "")
            f.write(f"{timestamp}{orig_word}\n")

    print(f"Fichier LRC généré : {output_lrc}")