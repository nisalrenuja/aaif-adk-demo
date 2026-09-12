"""The copied files must stay identical, or the teaching structure rots.

Nine phase folders, and seven files that exist as byte identical copies in up to
six of them. That is deliberate: a phase folder can be copied out of this repo and
run on its own, which is worth more here than not repeating yourself.

The cost is that a fix to `degrade_gracefully` has to land six times, and the
failure mode is silent. Five phases behave one way, one behaves another, and the
reader who finds it assumes the difference is the lesson.

So the copies stay and this test removes the drift. When it fails:

    python3 scripts/sync_phases.py            # what drifted
    python3 scripts/sync_phases.py --write    # copy the source phase over the rest
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sync_phases  # noqa: E402  the path has to be set up first


def test_shared_files_are_identical_across_phases():
    drifted = sync_phases.check()
    assert not drifted, "Run `python3 scripts/sync_phases.py --write`. Drifted:\n" + "\n".join(
        f"  {copy.relative_to(REPO_ROOT)} != {source.relative_to(REPO_ROOT)}"
        for source, copy in drifted
    )


def test_manifest_matches_what_is_on_disk():
    """Every manifest entry names a file that exists in its source phase.

    Stops the manifest from quietly going stale: a renamed file would otherwise
    make the check pass by checking nothing.
    """
    for filename, first in sync_phases.SHARED_FILES.items():
        source = sync_phases.AGENTS / first / filename
        assert source.exists(), f"{filename} is not in {first}"


def test_every_phase_in_the_manifest_exists():
    for phase in sync_phases.PHASES:
        assert (sync_phases.AGENTS / phase).is_dir(), phase


def test_no_shared_file_is_missing_from_a_later_phase():
    """A file that appears, disappears and reappears is almost always a mistake.

    `weather.py` starts in Phase 4 and is in every phase after it. If one were
    missing, the check above would skip it silently rather than fail, so the gap
    is asserted here instead.
    """
    for filename, first in sync_phases.SHARED_FILES.items():
        later = sync_phases._phases_from(first)
        present = [p for p in later if (sync_phases.AGENTS / p / filename).exists()]
        assert present == later, (
            f"{filename} appears in {present} but should be in every phase "
            f"from {first} onward: {later}"
        )
