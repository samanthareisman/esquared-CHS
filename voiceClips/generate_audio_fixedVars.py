#!/usr/bin/env python3
"""
generate_instructions.py
────────────────────────
Generates audio clips for:
  1. All instruction screens
  2. Fixed between-trial screens (next trial, halfway, end, liking, countdown)
  3. Emotion test screens (question clips + all option-order permutations)

Output folder: audio_instructions/en/
(separate from audio/en/ used by generate_audio.py)

Usage
-----
  export ELEVENLABS_API_KEY=sk-...
  python generate_instructions.py              # generate all missing clips
  python generate_instructions.py --dry-run    # print filenames + text, no API calls
  python generate_instructions.py --force      # regenerate all clips
"""

import os
import sys
import json
import time
import re
import requests
from pathlib import Path
from itertools import permutations

# ── Config ────────────────────────────────────────────────────────────────────

API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID = "rHgIYq4QuHGKeR1k8KoM"
MODEL    = "eleven_turbo_v2"

OUT_DIR  = Path("audio/fixedVars")
MANIFEST = OUT_DIR / "manifest.json"

DRY_RUN  = "--dry-run" in sys.argv
FORCE    = "--force" in sys.argv
DELAY    = 0.5

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Voice settings ────────────────────────────────────────────────────────────

VOICE_SETTINGS = {
    "stability":        0.40,
    "similarity_boost": 1.0,
    "style":            0.35,
    "speed":            0.85,
}

# ── Instruction character names (Logan/Emery, not Alex/Taylor) ───────────────
# Alex and Taylor are in the main task dictator pool.
# Logan and Emery are instruction-only characters.

CHAR1 = "Logan"   # introCharName1 — the Giver demo character
CHAR2 = "Emery"   # introCharName2 — the Receiver demo character

# ── HTML stripping ────────────────────────────────────────────────────────────

def strip_html(text):
    """Remove HTML tags and clean up whitespace for TTS."""
    text = re.sub(r'<br\s*/?>', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ── Build clip manifest ───────────────────────────────────────────────────────

clips = {}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — INSTRUCTIONS
# ─────────────────────────────────────────────────────────────────────────────

# welcomeTxt — gender dependent
clips["instr-welcome-boy"] = "Welcome! In today's activity I'm going to ask you questions about emotions. First, I'm going to tell you some stories about a little boy and ask you how he feels."
clips["instr-welcome-girl"] = "Welcome! In today's activity I'm going to ask you questions about emotions. First, I'm going to tell you some stories about a little girl and ask you how she feels."

# avatarSelect
clips["instr-avatar-select"] = "Okay, before we begin the next activity, I want you to choose an avatar. This avatar is special because it represents you! Pick the avatar that you want to represent you in today's activity."

# meetLogan (same for both genders)
clips["instr-meet-logan"] = f"Nice choice! Okay, today we're going to play a game about feelings! In this game, you will meet characters like {CHAR1}."

# meetBackpack — gender dependent (He/She pronoun)
clips["instr-meet-backpack-boy"] = f"Each character has a backpack. And look, you can see what's inside! See the inside of {CHAR1}'s backpack? He has two pieces of candy inside!"
clips["instr-meet-backpack-girl"] = f"Each character has a backpack. And look, you can see what's inside! See the inside of {CHAR1}'s backpack? She has two pieces of candy inside!"

# backpackCandy
clips["instr-backpack-candy"] = "Sometimes backpacks have good things, like candy!"

# backpackBugs
clips["instr-backpack-bugs"] = "And sometimes they have bad things, like bugs!"

# dictatorIntro
clips["instr-dictator-intro"] = f"In this game, there are always two people, a Giver and a Receiver. The person on the left is always the Giver. They share some of what is in their backpack. See here, {CHAR1} is the Giver! The person on the right is always the Receiver. They always get something from the Giver. See here, {CHAR2} is the Receiver."

# watchShare
clips["instr-watch-share"] = f"In the game, you will watch and see what Givers like {CHAR1} share with Receivers, like {CHAR2}. Let's watch now!"

# finishShare
clips["instr-finish-share"] = f"Look! {CHAR1} shared one candy with {CHAR2}!"

# gameOutro
clips["instr-game-outro"] = "Now, you know how the game works! Before we get started I have two questions."

# practiceCandy
clips["instr-practice-candy"] = "I want you to think about most of the kids in your community. How many of these 10 candies do you think most of the kids in your community would give to someone?"

# practiceBugs
clips["instr-practice-bugs"] = "Next, I want you to think about most of the kids in your community. How many of these 10 bugs do you think most of the kids in your community would give to someone?"

# discreteEmotions
clips["instr-discrete-emotions"] = "Great job practicing! Now I'm going to teach you about one more part. After each share, I will ask you how the Receiver feels. When you're the Receiver, I will ask you how you feel! People have lots of different feelings when someone shares something with them, like happy, sad, angry, surprised, excited, jealous, guilty, or okay. When I ask you about these feelings, you can pick as many as you want!"

# practiceDiscrete
clips["instr-practice-discrete"] = "Let's try now! Tell me how you're feeling today! Are you happy, sad, angry, surprised, excited, jealous, guilty, or okay? You can pick as many feelings as you want and you can take as long as you need. When you're picking, you can tell me the names of the feelings or the numbers!"

# affectIntro
clips["instr-affect-intro"] = "To help us talk about feelings, we are also going to use special pictures. These special pictures help people tell us how they feel. When I ask about feelings, just pick the picture that fits best."

# valenceIntro
clips["instr-valence-intro"] = "Here are some of the pictures! Let's look! You can see on one end, the character is frowning. On the other end, they are smiling. In the middle, they aren't smiling or frowning. You can choose the happy side for feelings like happy, glad, cheerful, pleased, good, or hopeful. You can choose the frowning side for feelings like unhappy, scared, angry, or bad. If a feeling is neither unhappy nor happy, you can choose the picture in the middle."

# valencePractice
clips["instr-valence-practice"] = "Now let's practice! How unhappy or happy are you feeling today? Tell me which number! You can take as long as you need."

# arousalIntro
clips["instr-arousal-intro"] = "You will also see these pictures! See on one end, the character is very still with their eyes closed. On the other end, they are full of energy and wide awake. This is like when you get excited and can't sit still, or like when you have butterflies in your stomach and are very nervous. You can choose the awake side for feelings like excited, enthusiastic, nervous, scared, or wide awake. You can choose the sleepy side for feelings like calm, relaxed, bored, or sleepy. If a feeling is neither sleepy nor awake, you can choose the picture in the middle."

# arousalPractice
clips["instr-arousal-practice"] = "Let's practice! How sleepy or awake are you feeling today? Tell me which number! You can take as long as you need."

# finishIntro
clips["instr-finish-intro"] = "Great job! Now you know how to play the game. Let's start!"

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — FIXED BETWEEN-TRIAL / END SCREENS
# ─────────────────────────────────────────────────────────────────────────────

# nextTrialText
clips["next-trial"] = "Let's see the next one!"

# Halfway screen
clips["halfway-headline"]      = "Look, you're halfway done!"
clips["halfway-encouragement"] = "You're doing a great job!"
clips["halfway-continue"]      = "Okay, now let's finish the last half!"

# Countdown messages (last 4 trials)
clips["countdown-3"] = "Almost there! Three more to go!"
clips["countdown-2"] = "Two more to go!"
clips["countdown-1"] = "One more to go!"
clips["countdown-0"] = "Last one!"

# Liking rating questions
clips["liking-candy"] = "How much do you like candy like this?"
clips["liking-bugs"]  = "How much do you like bugs like this?"

# End screen
clips["end-headline"] = "All done!"
clips["end-subtext"]  = "Thank you for participating."

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — EMOTION TEST
# ─────────────────────────────────────────────────────────────────────────────

# Question clips — boy versions (from script_english.js emotion_tvars)
ETEST_QUESTIONS_BOY = [
    "This boy is looking at his little turtle which has just died... How is this boy feeling?",
    "This boy is getting a birthday present... How is this boy feeling?",
    "This boy is trying to do a drawing, but his brother is stopping him... How is this boy feeling?",
    "This boy is standing at the bus stop... How is this boy feeling?",
    "This boy is having a sleepover with his best friend... How is this boy feeling?",
    "This boy opened a box of toothpaste and there were cotton balls inside... How is this boy feeling?",
    "This boy saw his brother win a special prize in a raffle... How is this boy feeling?",
    "This boy got caught stealing cookies from the cookie jar... How is this boy feeling?",
]

# Girl versions (via genderSwapToGirl logic)
ETEST_QUESTIONS_GIRL = [
    "This girl is looking at her little turtle which has just died... How is this girl feeling?",
    "This girl is getting a birthday present... How is this girl feeling?",
    "This girl is trying to do a drawing, but her sister is stopping her... How is this girl feeling?",
    "This girl is standing at the bus stop... How is this girl feeling?",
    "This girl is having a sleepover with her best friend... How is this girl feeling?",
    "This girl opened a box of toothpaste and there were cotton balls inside... How is this girl feeling?",
    "This girl saw her sister win a special prize in a raffle... How is this girl feeling?",
    "This girl got caught stealing cookies from the cookie jar... How is this girl feeling?",
]

for i, text in enumerate(ETEST_QUESTIONS_BOY):
    clips[f"etest-q-{i+1}-boy"] = text

for i, text in enumerate(ETEST_QUESTIONS_GIRL):
    clips[f"etest-q-{i+1}-girl"] = text

# Option suffix clips — all permutations of each emotion group × boy/girl
# Filename: etest-opts-{e1}-{e2}-{e3}-{e4}-{boy|girl}.mp3
# Text:     "Is he/she {e1}, {e2}, {e3}, or {e4}?"

EMOTION_GROUPS = {
    "group-a": ["happy", "sad", "angry", "okay"],
    "group-b": ["excited", "surprised", "jealous", "guilty"],
}

for group_name, emotions in EMOTION_GROUPS.items():
    for perm in permutations(emotions):
        e1, e2, e3, e4 = perm
        opt_str = f"{e1}-{e2}-{e3}-{e4}"

        clips[f"etest-opts-{opt_str}-boy"]  = f"Is he {e1} — {e2} — {e3} — or {e4}?"
        clips[f"etest-opts-{opt_str}-girl"] = f"Is she {e1} — {e2} — {e3} — or {e4}?"

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

    # Instruction clips run slightly faster than other clips
    voice_settings = {**VOICE_SETTINGS}
    if key.startswith("instr-"):
        voice_settings["speed"] = 0.9

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    resp = requests.post(
        url,
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": MODEL,
            "voice_settings": voice_settings,
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
