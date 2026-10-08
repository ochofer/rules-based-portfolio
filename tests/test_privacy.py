"""No committed file and no public output carries a private value: the starting amount, the top-up or the
random line of the private values file. The file sits outside the repository (RULES_VALUES_FILE, or
private/rules_values_v1.0.txt beside the repository); without it the test is skipped."""

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALUES = Path(os.environ.get("RULES_VALUES_FILE", ROOT.parent / "private" / "rules_values_v1.0.txt"))


def _values() -> dict:
    out = {}
    for line in VALUES.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def _amount(text: str) -> re.Pattern:
    """An amount written in any usual form: 1234, 1,234, 1.234, 1 234, with or without decimals of zero."""
    whole = str(int(round(float(text))))
    groups = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    body = r"[,.   ]?".join(groups)
    return re.compile(rf"(?<![\d.,]){body}(?:[.,]0+)?(?![\d.,])")


def _public_files() -> list:
    listed = subprocess.run(
        ["git", "--no-optional-locks", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    return [ROOT / f for f in listed if f and (ROOT / f).is_file()]


@pytest.mark.skipif(not VALUES.exists(), reason="the private values file is not on this machine")
def test_no_private_value_in_any_public_file():
    values = _values()
    patterns = {
        "starting amount": _amount(values["starting_amount_eur"]),
        "top-up": _amount(values["monthly_top_up_eur"]),
    }
    salt = values["salt"]
    hits = []
    for path in _public_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if salt and salt in text:
            hits.append(f"{path.relative_to(ROOT)}: the random line")
        for name, pattern in patterns.items():
            m = pattern.search(text)
            if m:
                line = text.count("\n", 0, m.start()) + 1
                hits.append(f"{path.relative_to(ROOT)}, line {line}: the {name}")
    assert not hits, "private values in public files:\n" + "\n".join(hits)


def test_amount_pattern_reads_every_usual_form():
    p = _amount("1234.00")
    for text in ("1234", "1,234", "1.234", "1 234", "1234.00", "EUR 1,234.00", "(1234)"):
        assert p.search(text), text
    for text in ("12345", "0.1234", "1234.5", "11234", "1234,56"):
        assert not p.search(text), text
