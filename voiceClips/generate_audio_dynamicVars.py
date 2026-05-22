#!/usr/bin/env python3
"""
generate_audio_dynamicVars.py
─────────────────
Batch-generates audio clips via ElevenLabs TTS for the children's sharing study.
Run once locally; upload audio/dynamicVars/ to GitHub or S3 for jsPsych/CHS.

Usage
-----
  export ELEVENLABS_API_KEY=4bf83b9351581b62f97c01a3e158079d0fbe0c3df6c9c0491b6854ffbbd8d135
  python generate_audio_dynamicVars.py              # generate all missing clips
  python generate_audio_dynamicVars.py --dry-run    # print filenames + text only, no API calls
  python generate_audio_dynamicVars.py --force      # regenerate all clips even if file exists
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID = "rHgIYq4QuHGKeR1k8KoM"
MODEL    = "eleven_turbo_v2"

OUT_DIR  = Path("audio/dynamicVars")
MANIFEST = OUT_DIR / "manifest.json"

DRY_RUN  = "--dry-run" in sys.argv
FORCE    = "--force" in sys.argv
DELAY    = 0.5

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Name pools ────────────────────────────────────────────────────────────────

DICTATORS = [
    "charlie", "sam", "alex", "avery", "riley", "blake",
    "jamie", "quinn", "jessy", "micah", "taylor", "cam",
]

RECEIVERS = [
    "jordan", "skyler", "mackenzie", "casey", "shawn", "drew",
]

AMOUNTS   = [1, 5, 9]
RESOURCES = ["candy", "bug"]

# ── Text helpers ──────────────────────────────────────────────────────────────

NUM_WORDS = {1: "one", 5: "five", 9: "nine"}

def cap(name):
    return name.capitalize()

def plural(resource):
    return "candies" if resource == "candy" else "bugs"

def item_label(n, resource):
    if resource == "candy":
        return "candy" if n == 1 else "candies"
    return "bug" if n == 1 else "bugs"

# ── Build clip manifest ───────────────────────────────────────────────────────

clips = {}

# ── SP sentences (dictator name only) ────────────────────────────────────────

for d in DICTATORS:
    for r in RESOURCES:
        p = plural(r)

        # trialStart SP
        key = f"trialstart-sp-{d}-{r}"
        clips[key] = (
            f"Here are {cap(d)} and you! "
            f"{cap(d)}'s backpack has 10 {p} inside and you have none!"
        )

        # distributePrompt SP
        key = f"distprompt-sp-{d}-{r}"
        clips[key] = f"Let's see how many {p} {cap(d)} gives to you!"

    # distributeComplete SP
    for n in AMOUNTS:
        for r in RESOURCES:
            key = f"distcomplete-sp-{d}-gave-you-{n}-{r}"
            clips[key] = f"Look! {cap(d)} gave you {NUM_WORDS[n]} {item_label(n, r)}!..."

    # emotion / valence / arousal SP
    clips[f"emotion-sp-{d}"] = (
        f"How do you feel about what {cap(d)} gave you? "
        f"Remember, you can pick as many feelings as you want!"
    )
    clips[f"valence-sp-{d}"] = f"How happy or unhappy do you feel about what {cap(d)} gave you?"
    clips[f"arousal-sp-{d}"] = f"How sleepy or awake do you feel about what {cap(d)} gave you?"

# ── TP sentences ──────────────────────────────────────────────────────────────

for d in DICTATORS:
    for rv in RECEIVERS:
        for r in RESOURCES:
            p = plural(r)

            # trialStart TP
            key = f"trialstart-tp-{d}-{rv}-{r}"
            clips[key] = (
                f"Here are {cap(d)} and {cap(rv)}! "
                f"{cap(d)}'s backpack has 10 {p} inside and {cap(rv)} has none!"
            )

            # distributePrompt TP
            key = f"distprompt-tp-{d}-{rv}-{r}"
            clips[key] = f"Let's see how many {p} {cap(d)} gives to {cap(rv)}!"

        # distributeComplete TP (both names)
        for n in AMOUNTS:
            for r in RESOURCES:
                key = f"distcomplete-tp-{d}-{rv}-gave-{n}-{r}"
                clips[key] = f"Look! {cap(d)} gave {cap(rv)} {NUM_WORDS[n]} {item_label(n, r)}!..."

# ── TP emotion / valence / arousal — receiver name only ──────────────────────

for rv in RECEIVERS:
    clips[f"emotion-tp-{rv}"] = (
        f"How do you think {cap(rv)} feels about what they got? "
        f"Remember, you can pick as many feelings as you want!"
    )
    clips[f"valence-tp-{rv}"] = f"How happy or unhappy does {cap(rv)} feel about what they got?"
    clips[f"arousal-tp-{rv}"] = f"How sleepy or awake does {cap(rv)} feel about what they got?"

# ── Generate ──────────────────────────────────────────────────────────────────

def generate_clip(key, text):
    out_path = OUT_DIR / f"{key}.mp3"

    if not FORCE and out_path.exists():
        print(f"  skip   {key}.mp3")
        return True

    if DRY_RUN:
        print(f"  [dry]  {key}.mp3")
        print(f"         {text}")
        return True

    if not API_KEY:
        print("ERROR: ELEVENLABS_API_KEY not set. Run: export ELEVENLABS_API_KEY=sk-...")
        sys.exit(1)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    resp = requests.post(
        url,
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": MODEL,
            "voice_settings": {
                "stability": 0.40,
                "similarity_boost": 1.0,
                "style": 0.35,
                "speed": 0.85,
            },
        },
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"  ERROR  {resp.status_code} on {key}: {resp.text[:200]}")
        return False

    out_path.write_bytes(resp.content)
    print(f"  ✓      {key}.mp3")
    time.sleep(DELAY)
    return True

# ── Run ───────────────────────────────────────────────────────────────────────

print(f"\nGenerating {len(clips)} clips → {OUT_DIR}/\n")
if DRY_RUN:
    print("(dry run — no API calls)\n")

errors = []
for key, text in clips.items():
    ok = generate_clip(key, text)
    if not ok:
        errors.append(key)

# ── Write manifest ────────────────────────────────────────────────────────────

if not DRY_RUN:
    manifest_data = {k: f"{k}.mp3" for k in clips}
    MANIFEST.write_text(json.dumps(manifest_data, indent=2))
    print(f"\nManifest → {MANIFEST}")

n_ok = len(clips) - len(errors)
print(f"\nDone. {n_ok}/{len(clips)} clips generated.")
if errors:
    print(f"\nFailed clips ({len(errors)}):")
    for e in errors:
        print(f"  {e}")
