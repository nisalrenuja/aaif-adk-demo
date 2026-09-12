"""The two runtimes must describe the same pipeline.

`agent.py` and `workflow_graph.py` build the same trip planner twice, once on the
classic `SequentialAgent`/`ParallelAgent`/`LoopAgent` and once on `Workflow`. See
docs/RUNTIMES.md for which of them to build on.

Two implementations of one flow drift, and this one had. `_events` was constructed
as a node in four phases and left out of the edge list, so the graph ran without the
events researcher. Nothing failed. The graph was valid, the run completed, and the
only symptom was an empty `{events_summary?}` reaching the assembler, which looks
exactly like a search that found nothing.

That is the thing to know about a second implementation: it does not break, it
quietly does less. These tests make "same pipeline, two runtimes" checkable.

## Why identity and not names

`node(agent, name="flights")` returns the agent itself, renamed, rather than a
wrapper around it. So the graph knows `flights` where `agent.py` knows
`flight_researcher`, and comparing names would compare nothing. These tests walk
the edge list and compare object identity, and read the `_as_node(...)` calls out
of the source to recover which agent became which node.
"""

from __future__ import annotations

import ast
import importlib
import warnings
from pathlib import Path

import pytest

# The classic agents are deprecated in 2.5 and used on purpose, the same reason
# agent.py silences this. The warning is right and it is not news.
warnings.filterwarnings("ignore", message=r".*deprecated in favor of Workflow.*")

AGENTS = Path(__file__).resolve().parent.parent / "agents"

PIPELINE_PHASES = [
    "p3_workflow",
    "p4_tools",
    "p5_models",
    "p6_safety",
    "p7_a2a",
    "p8_production",
]

# `local_expert` is a RemoteA2aAgent that exists only when its service is running,
# and it is deliberately not in the graph. Named here rather than forgotten about.
CLASSIC_ONLY = {"local_expert"}


def _load(phase: str):
    agent = importlib.import_module(f"agents.{phase}.agent")
    graph = importlib.import_module(f"agents.{phase}.workflow_graph")
    return agent, graph


def _wired_ids(graph) -> set[int]:
    """Object ids of everything reachable from the graph's edge list.

    Walks the edges rather than the module's variables, which is the point: a node
    assigned to a variable and never wired is exactly the bug this catches.
    """
    seen = set()

    def walk(item):
        if isinstance(item, (tuple, list)):
            for sub in item:
                walk(sub)
        elif isinstance(item, dict):
            for sub in item.values():
                walk(sub)
        else:
            seen.add(id(item))

    walk(graph.root_agent.edges)
    return seen


def _node_vars(graph) -> dict[str, object]:
    """The module level `_name = _as_node(...)` objects, by variable name."""
    return {
        name: value
        for name, value in vars(graph).items()
        if name.startswith("_") and not name.startswith("__") and hasattr(value, "name")
    }


def _as_node_calls(phase: str) -> dict[str, str]:
    """Read `_flights = _as_node(flight_researcher, "flights")` out of the source.

    Returns variable name -> the agent.py name it wraps, which is the mapping the
    objects themselves no longer carry once `node()` has renamed them.
    """
    tree = ast.parse((AGENTS / phase / "workflow_graph.py").read_text())
    mapping = {}
    for stmt in tree.body:
        if (
            isinstance(stmt, ast.Assign)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id == "_as_node"
            and isinstance(stmt.value.args[0], ast.Name)
            and isinstance(stmt.targets[0], ast.Name)
        ):
            mapping[stmt.targets[0].id] = stmt.value.args[0].id
    return mapping


@pytest.mark.parametrize("phase", PIPELINE_PHASES)
def test_no_node_is_built_and_left_unwired(phase):
    """A node built and never wired does nothing, and says nothing.

    This is the test that would have caught `_events`.
    """
    _, graph = _load(phase)
    wired = _wired_ids(graph)
    unwired = [name for name, obj in _node_vars(graph).items() if id(obj) not in wired]
    assert not unwired, (
        f"{phase}/workflow_graph.py builds {unwired} and never puts them in the "
        "edge list, so the graph runs without them."
    )


@pytest.mark.parametrize("phase", PIPELINE_PHASES)
def test_every_researcher_runs_on_both_runtimes(phase):
    """The fan out has to hold the same agents on both runtimes."""
    agent, graph = _load(phase)
    classic = {a.name for a in agent.research_team.sub_agents} - CLASSIC_ONLY

    wired = _wired_ids(graph)
    node_vars = _node_vars(graph)
    in_graph = {
        agent_name
        for var, agent_name in _as_node_calls(phase).items()
        if var in node_vars and id(node_vars[var]) in wired
    }

    assert classic <= in_graph, (
        f"{phase}: researchers in agent.py that the graph does not run: "
        f"{sorted(classic - in_graph)}"
    )


@pytest.mark.parametrize("phase", PIPELINE_PHASES)
def test_both_runtimes_total_the_trip_with_the_same_code(phase):
    """The classic `check_budget` tool and the graph's `budget_gate` node.

    Both delegate to `evaluate_budget`, so the number on stage cannot depend on
    which runtime produced it. If either grows its own arithmetic, this fails.
    """
    source = (AGENTS / phase / "workflow_graph.py").read_text()
    gate = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "budget_gate"
    )
    body = ast.unparse(gate)
    assert "evaluate_budget(" in body
    # No second opinion about the total.
    assert "price_usd" not in body


@pytest.mark.parametrize("phase", PIPELINE_PHASES)
def test_both_runtimes_bound_their_loop(phase):
    """Unbounded refinement burns the day's quota on one unlucky question."""
    agent, graph = _load(phase)
    assert graph.MAX_PASSES > 0
    assert agent.refinement_loop.max_iterations > 0


@pytest.mark.parametrize("phase", PIPELINE_PHASES)
def test_the_assemblers_one_pass_guard_survives_the_port(phase):
    """`_as_node` copies the agent. The callbacks have to come with it.

    `model_copy(update=...)` replaces the fields it is given and keeps the rest, so
    this holds today. It is asserted because a future port that rebuilt the agent
    instead of copying it would silently drop the guard on one runtime only.
    """
    _, graph = _load(phase)
    node_vars = _node_vars(graph)
    assemble = next(
        obj
        for var, obj in node_vars.items()
        if _as_node_calls(phase).get(var) == "itinerary_assembler"
    )
    assert assemble.before_tool_callback is not None
    assert assemble.before_agent_callback is not None
