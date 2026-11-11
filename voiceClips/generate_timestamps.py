#!/usr/bin/env python3
"""
generate_timestamps.py
──────────────────────
Uses WhisperX to find when specific words are spoken in the audio clips, and writes a
matching .json file next to each mp3. CHS_task.js loads these files to time its
highlights and animations. If a clip's json is missing, its animation silently doesn't run.

Every clip group below is a different kind of json, matching how the task reads it:

  1. etest-opts-*.mp3          (fixedVars)   { "happy": 0.57, "sad": 1.11, ... }
       emotion words, in the order spoken; lights up the emotion buttons.
  2. instr-discrete-emotions   (fixedVars)   { "happy": ..., "okay": ... }
     instr-practice-discrete                 same emotion words; lights up the buttons.
  3. instr-valence-intro       (fixedVars)   { "happy": ..., "glad": ..., ... "bad": ... }
     instr-arousal-intro                     the rainbow words; keys must match the
                                             data-word="" attributes in CHS_task.js
                                             (valenceIntro / arousalIntro).
  4. instr-practice-{candy,bugs}-{should,would}   { "should": 4.8 }  (or "would")
                                             the word that grows on screen.
  4b. instr-welcome-{boy,girl}  (fixedVars)  { "here": 8.1 }
                                             when "here" is said; the replay-button ring and
                                             arrow appear on the welcome screen at that moment.
  5. trialstart-*.mp3          (dynamicVars) { "amount": 2.39 }
                                             when "10" is spoken; the left sticker grid
                                             pulses at that moment.

  6. instr-valence-intro-cues.json   { "frowningBox": {"start": 21.3, "end": 23.1}, ... }
     instr-arousal-intro-cues.json           start/end of whole phrases; drive the red/green/
                                             navy boxes, dimming and arrow on the valence and
                                             arousal intros
                                             (CLIP_CUES below; names must match `defs` in
                                             trial_valenceIntro / trial_arousalIntro in CHS_task.js).

If you change any wording in CHS_task.js, update the word lists in CLIP_TARGETS and the phrases
in CLIP_CUES below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SETUP (once)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  brew install ffmpeg
  pip3 install torch torchvision torchaudio whisperx
(An existing whisperx_env in this folder works too: activate it first.)

No Hugging Face token is required. If you ever need one, set it in the environment
(export HF_TOKEN=...) — never paste it into this file.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USAGE (run from anywhere)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  python3 generate_timestamps.py --dry-run        list the clips it would process (no model)
  python3 generate_timestamps.py                  process clips that have no json yet
  python3 generate_timestamps.py --force          redo every json, even if one exists
  python3 generate_timestamps.py --only intro     only clips whose name contains "intro"

Run it AFTER the audio is final. New audio means new timings.
Clips where a target word can't be found are reported at the end and NO json is
written for them, so a failure is never hidden behind a half-correct file.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import os
import re
import sys
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

HERE        = Path(__file__).resolve().parent
FIXED_DIR   = HERE / "audio" / "fixedVars"
DYNAMIC_DIR = HERE / "audio" / "dynamicVars"

DEVICE = "cpu"   # "cuda" for an Nvidia GPU, "mps" for Apple Silicon (if it works)

# Words the speech model may write differently from how we name them.
ALIASES = {"ok": "okay", "10": "ten"}

# Little words allowed between two listed words ("happy, sad, or okay").
FILLERS = {"or", "and"}

# ── What to look for in each clip ─────────────────────────────────────────────
# A target is (json_key, [spoken words]). Targets in one GROUP are spoken back to back
# as a list (fillers like "or" are fine in between); the script finds that run, so an
# earlier mention elsewhere in the clip ("a very happy avatar") is never picked up.

def _t(*keys):
    return [(k, k.split("-")) for k in keys]

EMOTIONS = ["happy", "sad", "angry", "surprised", "excited", "jealous", "guilty", "okay"]

CLIP_TARGETS = {
    # emotion-word screens
    "instr-discrete-emotions": [_t(*EMOTIONS)],
    "instr-practice-discrete": [_t(*EMOTIONS)],

    # rainbow words — keys must equal the data-word values in CHS_task.js
    "instr-valence-intro": [
        _t("happy", "glad", "cheerful", "pleased", "good", "hopeful"),
        _t("unhappy", "scared", "angry", "bad"),
    ],
    "instr-arousal-intro": [
        _t("calm", "relaxed", "bored", "sleepy"),
        _t("excited", "nervous", "jittery", "active", "wide-awake"),   # "wide awake" = 2 words
        # second pair of lists ("If you are very excited, enthusiastic, ..." / "If you feel calm, ...");
        # keys end in 2/ are the data-word values in arousalIntro; tokens are the spoken words
        [("excited2", ["excited"]), ("enthusiastic", ["enthusiastic"]), ("nervous2", ["nervous"]),
         ("scared", ["scared"]), ("wide-awake2", ["wide", "awake"])],
        [("calm2", ["calm"]), ("relaxed2", ["relaxed"]), ("sleepy2", ["sleepy"])],
    ],

    # welcome screen: the moment "...you can click here!" is said (replay-button ring + arrow)
    "instr-welcome-boy":  [_t("here")],
    "instr-welcome-girl": [_t("here")],

    # the growing word
    "instr-practice-candy-should": [_t("should")],
    "instr-practice-candy-would":  [_t("would")],
    "instr-practice-bugs-should":  [_t("should")],
    "instr-practice-bugs-would":   [_t("would")],
}

TRIALSTART_TARGETS = [[("amount", ["ten"])]]   # fires when "10" is spoken

# Phrase cues: (name, start_phrase, end_phrase[, {"reach": phrase}]).
# A cue turns on at the START of start_phrase and off at the END of end_phrase (the first
# match at or after the start). Cues are found in order: each one is searched for after the
# previous cue's start, so repeated phrases ("on the other side") resolve to the right one.
# Punctuation and case don't matter ("I've" == "ive"). A "|" in the start phrase marks the
# word the cue actually starts on.
# `reach` (arrow only): the moment the arrow must be fully stretched — the START of that phrase.
CLIP_CUES = {
    "instr-valence-intro": [
        ("frowningBox", "on one side",                         "frowning"),   # photo 1, red
        ("smilingBox",  "on the other side",                   "smiling"),    # photo 9, red
        ("middleBox",   "in the middle",                       "frowning"),   # photo 5, red (…not smiling or frowning)
        ("arrow",       "very unhappy",                        "avatar", {"reach": "very happy"}),
        ("dimHappy",    "lets look on the happy side",         "hopeful"),    # dim 1-5, "Happy Side" label
        ("happyBox",    "see how ive circled",                 "hopeful"),    # photo 9, red
        ("dimFrown",    "lets look on the other side",         "bad"),        # dim 5-9, "Frowning Side" label
        ("frownBox",    "do you see how ive circled",          "bad"),        # photo 1, red
        ("neutralBox",  "you can choose the picture in the middle", "middle"),  # photo 5, amber
        ("happyGroup",  "you can choose one of these pictures", "pictures"),  # photos 6-8, green
        ("frownGroup",  "you can choose one of these pictures", "pictures"),  # photos 2-4, navy (2nd time)
    ],
    "instr-arousal-intro": [
        ("calmSide",    "these pictures show",                 "sleepy"),     # dim 5-9, navy box on 1-4, "Calm Side"
        ("awakeSide",   "|you can use the pictures on",        "are very nervous"),  # dim 1-5, green box on 6-9, "Awake Side"
        ("excitedSide", "|if you are very excited",            "in the pictures before"),  # dim 1-5, "Awake Side"
        ("excitedBox",  "would |choose this picture",          "picture"),    # photo 9, red
        ("awakeGroup",  "|you can use these photos",           "in between"), # only 6-8 lit, green
        ("calmSide2",   "|if you feel calm",                   "in the pictures before"),  # dim 5-9, "Calm Side"
        ("calmBox",     "you can |choose this picture",        "picture"),    # photo 1, red
        ("calmGroup",   "|you can use these photos",           "in between"), # only 2-4 lit, navy
        ("neutralBox",  "|if a feeling is neither",            "middle"),     # photo 5, amber
    ],
}

# Emotion-test questions 3, 5, 7: red circle around the character for "this boy" / "this boy feeling"
# (the circle1/circle2 cues in trial_emotiontest in CHS_task.js)
for _n in (3, 5, 7):
    for _g in ("boy", "girl"):
        CLIP_CUES[f"etest-q-{_n}-{_g}"] = [
            ("circle1", f"this {_g}",         f"this {_g}"),
            ("circle2", f"this {_g} feeling", "feeling"),
        ]


def etest_targets(clip_stem):
    """etest-opts-sad-happy-okay-angry-girl -> one group: sad, happy, okay, angry."""
    expected = clip_stem.split("-")[2:-1]
    return [_t(*expected)]


# ── Matching (pure logic — no model needed) ───────────────────────────────────

def norm(word):
    w = re.sub(r"[^a-z0-9]", "", word.lower())
    return ALIASES.get(w, w)


def _match_run(words, targets, start):
    """Try to match `targets` as a back-to-back list beginning at index >= start.
    Returns (times, end_index) or None."""
    for i in range(start, len(words)):
        pos, times = i, {}
        for key, tokens in targets:
            while pos < len(words) and norm(words[pos]["word"]) in FILLERS and pos > i:
                pos += 1
            if [norm(w["word"]) for w in words[pos:pos + len(tokens)]] != tokens:
                break
            times[key] = words[pos]["t"]
            pos += len(tokens)
        else:
            return times, pos
    return None


def find_times(words, groups):
    """words: [{'word': str, 't': seconds}]. Returns ({key: seconds}, used_fallback)."""
    out, used_fallback, cursor = {}, False, 0
    for targets in groups:
        hit = _match_run(words, targets, cursor)
        if hit:
            times, cursor = hit
            out.update(times)
            continue
        # Fallback: take each word in order wherever it appears, and say so.
        used_fallback = True
        pos = cursor
        for key, tokens in targets:
            found = None
            for j in range(pos, len(words)):
                if [norm(w["word"]) for w in words[j:j + len(tokens)]] == tokens:
                    found = j
                    break
            if found is not None:
                out[key] = words[found]["t"]
                pos = found + len(tokens)
    return out, used_fallback


def fill_times(raw_words):
    """WhisperX gives no 'start' for tokens it can't align (usually digits like '10').
    Borrow the previous word's end (or the next word's start) so every word has a time."""
    words = []
    for i, w in enumerate(raw_words):
        if not norm(w["word"]):      # punctuation-only token such as an em-dash
            continue
        t = w.get("start")
        if t is None:
            prev_end = next((raw_words[j].get("end") for j in range(i - 1, -1, -1)
                             if raw_words[j].get("end") is not None), None)
            next_start = next((raw_words[j].get("start") for j in range(i + 1, len(raw_words))
                               if raw_words[j].get("start") is not None), None)
            t = prev_end if prev_end is not None else (next_start if next_start is not None else 0.0)
        e = w.get("end")
        e = float(e) if e is not None else float(t) + 0.25
        words.append({"word": w["word"], "t": round(float(t), 3), "e": round(max(e, float(t)), 3)})
    return words


def find_phrase(words, phrase, start=0):
    """Index of the first place `phrase` (space-separated) is spoken at or after `start`, else None."""
    tokens = [norm(w) for w in phrase.split()]
    for i in range(start, len(words) - len(tokens) + 1):
        if [norm(w["word"]) for w in words[i:i + len(tokens)]] == tokens:
            return i
    return None


def find_cues(words, specs):
    """Returns ({name: {"start", "end"[, "reach"]}}, [names that could not be found])."""
    out, missing, cursor = {}, [], 0
    for spec in specs:
        name, start_phrase, end_phrase = spec[:3]
        extra = spec[3] if len(spec) > 3 else {}
        # A "|" inside the start phrase marks the word the cue starts on: "would |choose this
        # picture" is found by the whole phrase but starts at "choose".
        lead = len(start_phrase.split("|")[0].split()) if "|" in start_phrase else 0
        i = find_phrase(words, start_phrase.replace("|", " "), cursor)
        if i is None:
            missing.append(name)
            continue
        cursor = i + 1
        search_from = i
        cue = {"start": words[i + lead]["t"]}
        if "reach" in extra:
            r = find_phrase(words, extra["reach"], i)
            if r is None:
                missing.append(name)
                continue
            cue["reach"] = words[r]["t"]
            search_from = r
        j = find_phrase(words, end_phrase, search_from)
        if j is None:
            missing.append(name)
            continue
        cue["end"] = words[j + len(end_phrase.split()) - 1]["e"]
        out[name] = cue
    return out, missing


# ── Work list ─────────────────────────────────────────────────────────────────

def cues_path(mp3):
    return mp3.with_name(mp3.stem + "-cues.json")


def build_jobs():
    """[(mp3 path, groups)] for every clip that needs a json."""
    jobs = []
    for name, groups in CLIP_TARGETS.items():
        jobs.append((FIXED_DIR / f"{name}.mp3", groups))
    for stem in CLIP_CUES:
        if stem.startswith("etest-q-"):
            jobs.append((FIXED_DIR / f"{stem}.mp3", []))
    for p in sorted(FIXED_DIR.glob("etest-opts-*.mp3")):
        jobs.append((p, etest_targets(p.stem)))
    for p in sorted(DYNAMIC_DIR.glob("trialstart-*.mp3")):
        jobs.append((p, TRIALSTART_TARGETS))
    return jobs


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    force   = "--force" in sys.argv
    dry     = "--dry-run" in sys.argv
    only    = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None

    jobs = build_jobs()
    if only:
        jobs = [(p, g) for p, g in jobs if only in p.name]

    todo, absent = [], []
    for path, groups in jobs:
        if not path.exists():
            absent.append(path)
        elif (path.with_suffix(".json").exists() and not force
              and (path.stem not in CLIP_CUES or cues_path(path).exists())):
            continue
        else:
            todo.append((path, groups))

    print(f"{len(jobs)} clips checked: {len(todo)} to process, "
          f"{len(jobs) - len(todo) - len(absent)} already have a json, {len(absent)} mp3 missing\n")
    for p in absent:
        print(f"  missing mp3  {p.relative_to(HERE)}")

    if dry:
        for p, _ in todo:
            print(f"  [dry]  {p.relative_to(HERE)}")
        return
    if not todo:
        print("Nothing to do.")
        return

    import whisperx   # imported late so --dry-run and the matching logic work without it

    print("\nLoading WhisperX model...")
    model = whisperx.load_model("base", DEVICE, compute_type="int8", language="en")   # all clips are English: skips per-clip language detection
    align_model, align_meta = whisperx.load_align_model(language_code="en", device=DEVICE)

    import time
    problems = []
    for n, (path, groups) in enumerate(todo, 1):
        t0 = time.time()
        print(f"  [{n}/{len(todo)}] {path.name} ...", flush=True)
        audio  = whisperx.load_audio(str(path))
        result = model.transcribe(audio, batch_size=4)
        result = whisperx.align(result["segments"], align_model, align_meta, audio, DEVICE,
                                return_char_alignments=False)
        raw   = [w for seg in result["segments"] for w in seg.get("words", [])]
        words = fill_times(raw)
        times, used_fallback = find_times(words, groups)

        wanted = [k for g in groups for k, _ in g]
        absent_keys = [k for k in wanted if k not in times]
        if absent_keys:
            heard = " ".join(w["word"] for w in words)
            print(f"  ✗  {path.name}: could not find {absent_keys}\n       heard: {heard}")
            problems.append(path.name)
            continue

        out = {k: times[k] for k in wanted}
        path.with_suffix(".json").write_text(json.dumps(out, indent=2))
        note = "  (words not back-to-back — check)" if used_fallback else ""
        print(f"  ✓  {path.with_suffix('.json').name}  {out}{note}  ({time.time() - t0:.0f}s)")

        if path.stem in CLIP_CUES:
            cues, cue_missing = find_cues(words, CLIP_CUES[path.stem])
            if cue_missing:
                heard = " ".join(w["word"] for w in words)
                print(f"  ✗  {cues_path(path).name}: could not find cues {cue_missing}\n       heard: {heard}")
                problems.append(cues_path(path).name)
            else:
                cues_path(path).write_text(json.dumps(cues, indent=2))
                print(f"  ✓  {cues_path(path).name}  ({len(cues)} cues)")

    print(f"\nDone. {len(todo) - len(problems)}/{len(todo)} json files written.")
    if problems:
        print("Not written (check the audio, or the word list in CLIP_TARGETS):")
        for n in problems:
            print("  ", n)
    print("\nUpload audio/fixedVars/ and audio/dynamicVars/ (with the .json files) to GitHub.")


if __name__ == "__main__":
    main()
