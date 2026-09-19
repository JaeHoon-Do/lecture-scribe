# lecture-scribe

Turn a recorded medical-school lecture into slide-by-slide study notes automatically.

Give it the lecture recording (`.mp4`), today's slide deck (`.pdf`), and optionally last year's
annotated notes. It transcribes everything the lecturer said, figures out **which slide was on
screen at every second**, tracks **where the lecturer's mouse pointer lingered**, aligns last
year's notes to this year's slides, and assembles it all into per-slide notes (HTML for desktop
and tablet, an annotated PDF, and a full transcript).

I built this as a second-year medical student because I was spending more time re-watching
recordings than studying. It runs on a single consumer GPU (RTX 3070, 8 GB): a 105-minute lecture
takes about 35 minutes end to end.

> 🇰🇷 Korean documentation: [README.ko.md](README.ko.md). The pipeline is language-agnostic
> (set `whisper.language` in `config.json`), but the note-writing prompts and Claude Code skills
> are written in Korean.

## What it produces

For each lecture deck:

| Output | What's in it |
|---|---|
| **Study-guide HTML** | One block per slide: key points, what the lecturer emphasised, suggested notes in last year's format, ⚠ fact-check flags, numbered pointer marks, and the full verbatim transcript for that slide. |
| **Tablet HTML** | Same content as a single self-contained file with embedded images. It opens directly in the iPad Files app. Landscape layout: slides on the left, notes on the right. |
| **Annotated PDF** | The original slides with notes in the margin and pointer marks drawn on top. |
| **Transcript Markdown** | The full transcript with ①②③ markers showing what the pointer was on when each sentence was said. |
| **Write-up draft** | A skeleton for sharing notes with classmates (which slides were emphasised, added, changed vs. last year). |

Markings on the slides follow the hand-written convention I already used:
**light-blue underline** = the lecturer read/explained this, **purple underline** = emphasised,
green **"skipped"** stamp = slide was passed over without comment.

## How it works

```
mp4 ─ffmpeg─▶ wav ─faster-whisper─▶ raw transcript ─gap check / re-transcribe / low-confidence recheck─▶
pdf ─pypdf──▶ slides.json (term prompt for Whisper)                                                     ├─ assemble ─▶ bundle_<deck>.json ─▶ worksheet
mp4 ─frame differencing─▶ slide segments ─image matching + DP─▶ page per segment ─8 fps re-search─▶ repair   │
mp4 ─background differencing─▶ pointer dwell events ────────────────────────────────────────────────────────┘
last year's pdf ─image DP─▶ lastyear_map.json
worksheet ─Claude (via Claude Code)─▶ notes_<deck>.json ─build─▶ HTML · tablet HTML · PDF · MD · write-up · index
```

The interesting parts, in order:

**1. Transcription that refuses to drop anything** (`transcribe.py`, `gap_check.py`, `fill_gaps.py`, `recheck.py`)
faster-whisper `large-v3` with word timestamps and per-segment confidence. Whisper's VAD is set
permissive to avoid hallucinations, so instead of trusting it, `gap_check.py` measures the RMS
loudness of every silence between segments: quiet gaps are real pauses, loud gaps are things
Whisper missed and get re-transcribed. Low-`avg_logprob` segments are re-checked separately.
`condition_on_previous_text=False` stops repetition hallucinations from propagating through a
long recording. Slide text is extracted first and fed to Whisper as a term prompt so medical
vocabulary is spelled correctly.

**2. Which slide is on screen** (`slide_detect.py`, `match_pages.py`, `repair_segments.py`)
Frames are streamed at 1 fps as 240×135 greyscale through an ffmpeg pipe and adjacent-frame
differences are computed with numpy. Slide changes move most of the screen; cursor movement moves
a few pixels, so the two separate cleanly on magnitude. The PowerPoint toolbar region is masked.
Each detected segment's representative frame is cropped to the slide area (letterbox detection),
normalised, and scored against every rendered PDF page. A **monotone dynamic-programming
alignment** encodes the prior that lectures move forward through the deck. Segments where the
best single match and the DP result disagree are flagged for a human to eyeball. Missed
transitions are re-searched at 8 fps.

**3. Where the lecturer pointed** (`cursor_track.py`)
While a slide is up, the only thing moving on screen is the cursor. Each segment is chunked into
60-second windows; the per-pixel **median of the window is the background**, and whatever differs
from it in a given frame is the cursor (box-sum via integral image to find the blob). Runs where
the cursor stays put become *dwell events* with normalised slide coordinates, so they can be drawn
straight onto the PDF and paired with the words being spoken at that moment (±2.5 s).

**4. Last year's notes → this year's slides** (`lastyear_map.py`)
Last year's PDF has handwriting drawn over it, which lowers image similarity, but the correct page
is still the best match, and the same monotone DP prior fixes the off-by-one shifts a single
extra cover slide would otherwise cause. Low-similarity pages are surfaced as "probably changed
this year".

**5. Assembly and note writing** (`assemble.py`, `dump_bundle.py`, then Claude)
Transcript segments that straddle a slide boundary are split at the word level so nothing is
attributed to the wrong slide. Everything is bundled per page into a worksheet, and the actual
note-writing (summaries, emphasis, fact-checks) is done by Claude through
[Claude Code](https://claude.com/claude-code) skills (`.claude/skills/`), following the rules in
`CLAUDE.md`. Every `underline` Claude emits is resolved back to text coordinates with PyMuPDF and
verified; anything it can't locate is flagged rather than silently dropped.

## Running it

Requirements: Python 3.11+, ffmpeg on `PATH`, an NVIDIA GPU (CPU int8 fallback exists but is slow),
and Claude Code for the note-writing step.

```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
```

Create a folder for the lecture next to the repo, drop in the `.mp4`, today's `.pdf`, and last
year's notes, copy `templates/timeline.txt` into it and fill in the start/end time of each class.
Then either let Claude Code drive the whole thing:

```
claude
/필기 "<lecture folder>"
```

or run the pipeline stages directly:

```
wabel --lecture "<lecture folder>"             # all stages up to the worksheet
wabel --lecture "<lecture folder>" --from match  # resume from a stage
wabel stages                                     # list stages
```

Per-lecture settings live in `lecture.json` (see `templates/lecture.json.example`); shared settings
(Whisper model, render sizes, fonts) in `config.json`.

## Layout

| Path | Purpose |
|---|---|
| `tools/` | The pipeline. One script per stage; `pipeline.py` is the driver. Nothing lecture-specific is hard-coded; each script reads the lecture's `lecture.json`. |
| `templates/` | `timeline.txt` and `lecture.json.example`. |
| `.claude/skills/` | Claude Code skills that orchestrate a lecture end to end and write the notes. |
| `CLAUDE.md` | The procedure and note schema Claude follows. |

Lecture recordings, slides, and generated notes are never committed. They belong to the lecturers.

## License

MIT
