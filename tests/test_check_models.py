"""The loop from "which models are healthy" to "which models the agents run on".

`docs/check_models.py` already knew which ids had quota. What it did with that
knowledge was print four environment variables for a human to retype. `--write`
puts them in `.env.models` and `agents/*/model.py` loads that file on import.

The assignment logic is offline arithmetic, so it is tested directly. The part
worth testing end to end is the handover: a file written by one program has to be
read by another, with the right precedence, or the loop is still open.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "docs"))

import check_models

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- the assignment --------------------------------------------------------


def test_fewer_than_four_usable_models_is_no_assignment():
    """Four distinct ids are needed for a full run. Three is not a partial win."""
    assert check_models._assign([("a", 20, False), ("b", 20, False)]) is None


def test_hungriest_slot_gets_the_healthiest_model():
    """The assembler makes about ten calls, so it gets the most headroom."""
    usable = [
        ("poorly", 2, False),
        ("healthiest", 20, False),
        ("middling", 9, False),
        ("second", 14, False),
    ]
    assignment = check_models._assign(usable)
    assert assignment["TRIP_ASSEMBLER_MODEL"] == "healthiest"
    assert assignment["TRIP_SECOND_MODEL"] == "poorly"


def test_every_slot_is_assigned_exactly_once():
    usable = [(f"m{i}", 20 - i, False) for i in range(4)]
    assignment = check_models._assign(usable)
    assert set(assignment) == set(check_models.SLOT_COST)
    assert len(set(assignment.values())) == 4


# --- the file --------------------------------------------------------------


def test_written_file_parses_back_to_the_assignment(tmp_path):
    usable = [(f"m{i}", 20 - i, False) for i in range(4)]
    assignment = check_models._assign(usable)
    target = tmp_path / ".env.models"
    check_models._write_env(assignment, str(target))

    parsed = dict(
        line.split("=", 1)
        for line in target.read_text().splitlines()
        if line and not line.startswith("#")
    )
    assert parsed == assignment


def test_writing_twice_replaces_rather_than_appends(tmp_path):
    """A stale line further up the file quietly winning is the bug to avoid."""
    target = tmp_path / ".env.models"
    check_models._write_env(dict.fromkeys(check_models.SLOT_COST, "old"), str(target))
    check_models._write_env(dict.fromkeys(check_models.SLOT_COST, "new"), str(target))

    # Only the assignments. The header comment carries an example that mentions
    # a slot name, and that is documentation rather than a second assignment.
    assignments = [
        line for line in target.read_text().splitlines()
        if line and not line.startswith("#")
    ]
    assert all(line.endswith("=new") for line in assignments)
    assert len(assignments) == len(check_models.SLOT_COST)


# --- the handover ----------------------------------------------------------


def _read_ids_with(tmp_path: Path, env: dict[str, str]) -> dict[str, str]:
    """Import `model.py` in a fresh process from `tmp_path` and report its ids.

    A subprocess because the loading happens at import time, and the point of the
    test is what a cold `adk web` run would see.
    """
    script = textwrap.dedent("""
        import json
        from agents.p8_production import model
        print(json.dumps({
            "primary": model.PRIMARY_MODEL_ID,
            "second": model.SECOND_MODEL_ID,
            "third": model.THIRD_MODEL_ID,
            "assembler": model.ASSEMBLER_MODEL_ID,
        }))
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO_ROOT), **env},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    import json

    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.slow
def test_a_written_file_reaches_the_agents(tmp_path):
    """The whole point: write the file, and the agents run on those ids."""
    check_models._write_env(
        {
            "TRIP_ASSEMBLER_MODEL": "written-assembler",
            "TRIP_PRIMARY_MODEL": "written-primary",
            "TRIP_SECOND_MODEL": "written-second",
            "TRIP_THIRD_MODEL": "written-third",
        },
        str(tmp_path / ".env.models"),
    )
    ids = _read_ids_with(tmp_path, {})
    assert ids["assembler"] == "written-assembler"
    assert ids["primary"] == "written-primary"


@pytest.mark.slow
def test_a_real_environment_variable_still_wins(tmp_path):
    """`override=False`. An inline override on the command line must keep working."""
    check_models._write_env(
        dict.fromkeys(check_models.SLOT_COST, "from-file"), str(tmp_path / ".env.models")
    )
    ids = _read_ids_with(tmp_path, {"TRIP_PRIMARY_MODEL": "from-the-command-line"})
    assert ids["primary"] == "from-the-command-line"
    assert ids["second"] == "from-file"


@pytest.mark.slow
def test_no_file_means_the_defaults_in_model_py(tmp_path):
    """The normal case. A missing file is a no op, not an error."""
    ids = _read_ids_with(tmp_path, {})
    assert ids["primary"] == "gemini-3.5-flash-lite"
