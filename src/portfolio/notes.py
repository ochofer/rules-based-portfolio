"""The monthly notes, notes/YYYY-MM.md: after each cycle day, a dated note of 120 to 200 words written by hand.

python3 -m portfolio note writes a draft to private/notes/ with the heading, the cycle day and one line of
the month's figures, each a figure the page shows. These two lines define cycle day, top-up, target weight and
band, the terms of the repository's list that a note is likeliest to use, and the style check asks for any
other listed term to be defined where the note first uses it. The words are the author's: what the weights did, the
orders placed and what they cost, the drift and the band, any departure, and anything the review of the
rules in October 2027 should know. A finished note is moved to notes/ and committed. read() checks every
note there before the page is built, and a note that fails stops the build.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from . import config

FILE = re.compile(r"^(\d{4})-(\d{2})\.md$")
CYCLE_DAY = "Cycle day (the day each month on which the rules are applied)"
CYCLE_LINE = re.compile(r"^" + re.escape(CYCLE_DAY) + r": (\d{4}-\d{2}-\d{2})\.$")
FIGURES = "Figures: "
DRAFT_MARK = "Write the note here"
WORDS = (120, 200)
# A note looks back. These words look forward, and a note that holds one stops the build.
FORWARD = re.compile(r"\b(will|shall|expects?|expected|expecting|forecasts?|going to|next month|next year|"
                     r"outlook|predicts?|anticipates?)\b", re.I)  # fmt: skip


class NoteError(ValueError):
    """A note that does not follow the form. The message names the file and the fault."""


@dataclass(frozen=True)
class Note:
    month: str  # YYYY-MM
    cycle_day: date
    figures: str
    body: str  # paragraphs separated by blank lines
    path: Path


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.,%/−-]*", text))


def parse(path: Path) -> Note:
    name = Path(path).name
    m = FILE.match(name)
    if not m:
        raise NoteError(f"notes/{name}: the file name is not YYYY-MM.md")
    month = pd.Period(f"{m.group(1)}-{m.group(2)}", "M")
    lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
    title = f"# {month.strftime('%B %Y')}"
    if not lines or lines[0].strip() != title:
        raise NoteError(f"notes/{name}: the first line must be '{title}'")
    rest = [line.rstrip() for line in lines[1:]]
    blocks, current = [], []
    for line in rest + [""]:
        if line.strip():
            current.append(line.strip())
        elif current:
            blocks.append(" ".join(current))
            current = []
    if len(blocks) < 3:
        raise NoteError(f"notes/{name}: it needs the cycle day line, the figures line and the note")
    cycle = CYCLE_LINE.match(blocks[0])
    if not cycle:
        raise NoteError(f"notes/{name}: the second block must read '{CYCLE_DAY}: YYYY-MM-DD.'")
    day = pd.Timestamp(cycle.group(1)).date()
    if pd.Period(day, "M") != month:
        raise NoteError(f"notes/{name}: the cycle day {day} is not in {month}")
    if not blocks[1].startswith(FIGURES):
        raise NoteError(f"notes/{name}: the third block must start with '{FIGURES.strip()}'")
    body = "\n\n".join(blocks[2:])
    if DRAFT_MARK in body:
        raise NoteError(f"notes/{name}: the draft's placeholder is still in the note")
    count = words(body)
    if not WORDS[0] <= count <= WORDS[1]:
        raise NoteError(f"notes/{name}: the note has {count} words, and a note has {WORDS[0]} to {WORDS[1]}")
    forward = FORWARD.search(body)
    if forward:
        raise NoteError(f"notes/{name}: '{forward.group(0)}' looks forward, and a note looks back")
    return Note(str(month), day, blocks[1][len(FIGURES) :], body, Path(path))


def read(folder: Path = None) -> list:
    """Every note in notes/, newest first."""
    folder = Path(folder or config.NOTES_DIR)
    if not folder.exists():
        return []
    notes = [parse(p) for p in sorted(folder.glob("*.md"))]
    return sorted(notes, key=lambda n: n.month, reverse=True)


def draft(month: pd.Period, cycle_day: date, figures: str) -> str:
    return (f"# {month.strftime('%B %Y')}\n\n{CYCLE_DAY}: {cycle_day}.\n\n{FIGURES}{figures}\n\n"
            f"{DRAFT_MARK}, {WORDS[0]} to {WORDS[1]} words: what the weights did, the orders placed and what they "
            "cost, the drift and the band, any departure, and anything the review of the rules in October 2027 "
            "should know. No sentence about what comes next, and no figure the page does not show.\n")  # fmt: skip
