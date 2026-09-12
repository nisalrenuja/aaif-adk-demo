"""Keep the files that are copied across phases from drifting apart.

Every phase folder is self contained on purpose: you can copy `agents/p5_models/`
out of this repo and run it on its own. The price of that property is that seven
files exist as byte identical copies in up to six folders, so a fix to
`degrade_gracefully` has to land in all of them.

The usual answer is to extract the shared code into a common module and import it.
That is the wrong trade here, because the thing being paid for is exactly the
property the import would destroy. So the copies stay and the drift is what gets
killed instead:

    python3 scripts/sync_phases.py             # report any copy that has drifted
    python3 scripts/sync_phases.py --write     # copy the source phase over the rest

`tests/test_phase_sync.py` runs the same check, so drift fails the suite rather
than being found by a reader three phases later.

## The manifest

Each entry names the phase a file *first appears in*. Every later phase that has a
file of that name must match it byte for byte. Earlier phases are deliberately
different: `p2_state/tools.py` is a smaller, simpler version of the file, and that
difference is the lesson of the phase.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS = REPO_ROOT / "agents"

# The phases, in the order they are taught. Order matters: "first appears in"
# means "at this index and every index after it".
PHASES = [
    "p0_seed",
    "p1_delegation",
    "p2_state",
    "p3_workflow",
    "p4_tools",
    "p5_models",
    "p6_safety",
    "p7_a2a",
    "p8_production",
]

# filename -> the phase it first appears in, and is copied forward from.
SHARED_FILES = {
    "mock_data.py": "p1_delegation",
    "tools.py": "p3_workflow",
    "model.py": "p3_workflow",
    "resilience.py": "p3_workflow",
    "one_pass.py": "p3_workflow",
    "_runner.py": "p3_workflow",
    "test_budget_loop.py": "p3_workflow",
    "weather.py": "p4_tools",
}

# Files that are per phase on purpose, listed so this docstring is not the only
# record of the decision. `agent.py` grows with every phase, and each phase's
# `workflow_graph.py` wires that phase's own agents.
DELIBERATELY_DIFFERENT = ("agent.py", "workflow_graph.py", "README.md", "__init__.py")


def _phases_from(first: str) -> list[str]:
    """The phases at or after `first`, in teaching order."""
    return PHASES[PHASES.index(first):]


def compared() -> list[str]:
    """The shared files that actually exist to be checked."""
    return [f for f, first in SHARED_FILES.items() if (AGENTS / first / f).exists()]


def check() -> list[tuple[Path, Path]]:
    """Return every (source, drifted copy) pair. Empty means everything matches."""
    drifted = []
    for filename, first in SHARED_FILES.items():
        source = AGENTS / first / filename
        if not source.exists():
            continue
        for phase in _phases_from(first)[1:]:
            copy = AGENTS / phase / filename
            if not copy.exists():
                # Not every later phase carries every file, and that is fine. A
                # missing copy is a phase that never needed it, not drift.
                continue
            if not filecmp.cmp(source, copy, shallow=False):
                drifted.append((source, copy))
    return drifted


def propagate() -> list[Path]:
    """Overwrite every drifted copy with its source. Returns what was rewritten."""
    written = []
    for source, copy in check():
        shutil.copyfile(source, copy)
        written.append(copy)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write",
        action="store_true",
        help="copy the source phase's version over every copy that has drifted",
    )
    args = parser.parse_args()

    if args.write:
        written = propagate()
        if not written:
            print("Nothing to do: every shared file already matches its source.")
            return 0
        print(f"Rewrote {len(written)} file(s) from their source phase:")
        for path in written:
            print(f"  {path.relative_to(REPO_ROOT)}")
        print("\nReview with `git diff` before committing.")
        return 0

    drifted = check()
    if not drifted:
        print(f"All {len(compared())} shared files match across every phase.")
        return 0

    print(f"{len(drifted)} shared file(s) have drifted from their source phase:\n")
    for source, copy in drifted:
        print(f"  {copy.relative_to(REPO_ROOT)}")
        print(f"    differs from {source.relative_to(REPO_ROOT)}")
    print("\nFix the source phase, then run `python3 scripts/sync_phases.py --write`.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
