#!/usr/bin/env python3
"""
generate_timestamps.py
──────────────────────
Uses WhisperX to extract word-level timestamps from all etest-opts-*.mp3 clips
and saves a matching .json file alongside each one.

Output format per clip:
  etest-opts-sad-happy-okay-angry-girl.json
  → { "sad": 0.41, "happy": 1.12, "okay": 1.83, "angry": 2.54 }

Claude Code uses these JSON files to highlight the correct emotion button
as the audio plays (polling audio.currentTime on each animation frame).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SETUP INSTRUCTIONS (do this once before running the script)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Install ffmpeg (required by WhisperX):
   Mac:     brew install ffmpeg
   Windows: download from https://ffmpeg.org/download.html

2. Install PyTorch (WhisperX depends on it):
   Mac (Apple Silicon):
     pip3 install torch torchvision torchaudio

   Mac (Intel) or Windows:
     pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

3. Install WhisperX:
     pip3 install whisperx

4. Get a Hugging Face token (free):
   - Go to https://huggingface.co and create a free account
   - Go to https://huggingface.co/settings/tokens
   - Click "New token", give it any name, click "Generate"
   - Copy the token (starts with hf_)
   - Paste it below where it says HF_TOKEN = "hf_..."

   WhisperX uses Hugging Face models for forced alignment.
   You also need to accept the terms for the alignment model:
   - Go to https://huggingface.co/pyannote/speaker-diarization
   - Click "Agree and access repository"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  python3 generate_timestamps.py

Run from the same folder as your audio/fixedVars/ directory.
JSON files are written next to each mp3.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import re
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

HF_TOKEN  = "hf_..."          # paste your Hugging Face token here
AUDIO_DIR = Path("audio/fixedVars")
DEVICE    = "cpu"              # change to "cuda" if you have an Nvidia GPU
                               # change to "mps" if you have Apple Silicon and want faster processing

# Emotion words we want timestamps for (all possible options across both groups)
EMOTION_WORDS = {
    "happy", "sad", "angry", "okay",
    "excited", "surprised", "jealous", "guilty"
}

# ── Load WhisperX ─────────────────────────────────────────────────────────────

import whisperx

print("Loading WhisperX model...")
model = whisperx.load_model("base", DEVICE, compute_type="int8")

print("Loading alignment model...")
align_model, align_metadata = whisperx.load_align_model(
    language_code="en",
    device=DEVICE
)

# ── Process clips ─────────────────────────────────────────────────────────────

clips = sorted(AUDIO_DIR.glob("etest-opts-*.mp3"))
print(f"\nFound {len(clips)} etest-opts clips to process\n")

for clip_path in clips:
    json_path = clip_path.with_suffix(".json")

    if json_path.exists():
        print(f"  skip   {clip_path.name} (json exists)")
        continue

    print(f"  ┄┄     {clip_path.name}")

    # 1. Transcribe with Whisper
    audio  = whisperx.load_audio(str(clip_path))
    result = model.transcribe(audio, batch_size=4)

    # 2. Forced alignment — gets word-level timestamps
    result = whisperx.align(
        result["segments"],
        align_model,
        align_metadata,
        audio,
        DEVICE,
        return_char_alignments=False
    )

    # 3. Extract timestamps for emotion words only
    timestamps = {}
    for segment in result["segments"]:
        for word_info in segment.get("words", []):
            word_clean = re.sub(r"[^a-z]", "", word_info["word"].lower())
            if word_clean in EMOTION_WORDS and word_clean not in timestamps:
                timestamps[word_clean] = round(word_info["start"], 3)

    # 4. Parse expected emotions from filename
    #    e.g. etest-opts-sad-happy-okay-angry-girl.mp3
    #    → expected = ["sad", "happy", "okay", "angry"]
    parts    = clip_path.stem.split("-")   # ['etest', 'opts', 'sad', 'happy', 'okay', 'angry', 'girl']
    expected = parts[2:-1]                 # ['sad', 'happy', 'okay', 'angry']

    # Warn if any expected emotion wasn't found
    missing = [e for e in expected if e not in timestamps]
    if missing:
        print(f"  ⚠ WARNING: could not find timestamps for {missing} in {clip_path.name}")

    # 5. Write JSON — only the emotions in this clip, in filename order
    output = {e: timestamps[e] for e in expected if e in timestamps}
    json_path.write_text(json.dumps(output, indent=2))
    print(f"  ✓      {json_path.name}  →  {output}")

print(f"\nDone. JSON files written to {AUDIO_DIR}/")
print("\nUpload the updated audio/fixedVars/ folder (including .json files) to GitHub.")
