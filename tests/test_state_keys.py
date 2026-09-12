"""Every reference to session state must name a key that exists.

Session state is a dict with string keys, and a missing key is not an error. It is
an empty read. Write `{chosen_flights?}` into an instruction and the presenter
renders a trip with no flight, cheerfully, with nothing in any log to say why.

`tools.py` guards its own references with constants. The references that are not in
`tools.py` are the ones that bite:

- `agent.py` reaches into state as **text**, inside instruction strings,
  `Hotel shortlist: {hotel_options?}`. No constant can reach in there.
- `workflow_graph.py` subscripts state directly, `ctx.state["budget_passes"]`.
- `resilience.py` appends to `state["degraded_agents"]`.

`TripState` in `tools.py` writes the vocabulary down once. This test is what makes
it load bearing rather than documentation, by checking both kinds of reference
against it across every phase.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.p8_production.tools import STATE_KEYS

AGENTS = Path(__file__).resolve().parent.parent / "agents"

# Phases that run the full pipeline. Earlier phases have their own smaller state
# vocabulary and are not covered by TripState.
PIPELINE_PHASES = [
    "p3_workflow",
    "p4_tools",
    "p5_models",
    "p6_safety",
    "p7_a2a",
    "p8_production",
]


def _instruction_strings(path: Path) -> list[tuple[str, str]]:
    """Every `instruction=` and `description=` literal in a module, with its agent.

    Implicitly concatenated string literals fold into one `ast.Constant`, so the
    multi line instructions in `agent.py` arrive here as single strings.
    """
    found = []
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = next(
            (
                kw.value.value
                for kw in node.keywords
                if kw.arg == "name" and isinstance(kw.value, ast.Constant)
            ),
            "<unnamed>",
        )
        for kw in node.keywords:
            if (
                kw.arg in ("instruction", "description")
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                found.append((name, kw.value.value))
    return found


def _placeholders(text: str) -> set[str]:
    """The `{key}` and `{key?}` names ADK will try to resolve against state."""
    import re

    return {m.group(1) for m in re.finditer(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\??\}", text)}


def _state_literals(path: Path) -> set[str]:
    """Keys used as string literals against a `.state`, by subscript or `.get`.

    Catches `ctx.state["budget_passes"]` and `state.get("degraded_agents", [])`.
    Keys reached through a constant are already covered by the constant.
    """
    found = set()
    tree = ast.parse(path.read_text())

    def is_state(node: ast.AST) -> bool:
        return isinstance(node, ast.Attribute) and node.attr == "state"

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and is_state(node.value)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            found.add(node.slice.value)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("get", "setdefault")
            and is_state(node.func.value)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.add(node.args[0].value)
    return found


@pytest.mark.parametrize("phase", PIPELINE_PHASES)
def test_instruction_placeholders_are_real_state_keys(phase):
    """A typo in an instruction placeholder is an empty read, not an error."""
    unknown = {}
    for agent_name, text in _instruction_strings(AGENTS / phase / "agent.py"):
        for key in _placeholders(text) - STATE_KEYS:
            unknown.setdefault(agent_name, set()).add(key)

    assert not unknown, (
        f"{phase}/agent.py references state keys that are not in TripState: "
        f"{ {a: sorted(k) for a, k in unknown.items()} }. Either fix the "
        "placeholder or add the key to TripState in tools.py."
    )


@pytest.mark.parametrize("phase", PIPELINE_PHASES)
def test_state_literals_are_real_state_keys(phase):
    """The same check for code that subscripts state instead of templating it."""
    for filename in ("workflow_graph.py", "resilience.py", "tools.py", "one_pass.py"):
        path = AGENTS / phase / filename
        if not path.exists():
            continue
        # `temp:` keys are ADK's invocation scoped scratch space, not trip state.
        used = {k for k in _state_literals(path) if not k.startswith("temp:")}
        assert used <= STATE_KEYS, (
            f"{phase}/{filename} uses state keys not in TripState: "
            f"{sorted(used - STATE_KEYS)}"
        )


def test_the_key_constants_agree_with_the_typed_dict():
    """`PREFS = "preferences"` and the TypedDict field must not disagree."""
    from agents.p8_production import tools

    constants = {
        name: value
        for name, value in vars(tools).items()
        if name.isupper() and isinstance(value, str) and not name.startswith("_")
    }
    for name, value in constants.items():
        assert value in STATE_KEYS, f"tools.{name} = {value!r} is not a TripState key"


def test_typed_dict_is_not_empty():
    """A refactor that emptied TripState would make every check above vacuous."""
    assert len(STATE_KEYS) > 10
