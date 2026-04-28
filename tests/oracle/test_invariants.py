"""Oracle runner for claim ``treescape-tip-count-invariant``.

Property-based: hypothesis generates random trees of varying shape
and size; for each, the rendered scene graph must contain exactly N
tip glyphs and every coordinate must lie within the declared canvas
bounds.

The strategy generates Newick strings directly so we exercise the
full pipeline: parse → layout → scene. Trees range from 1 to 50 tips
with branch lengths in [0, 5].
"""

from __future__ import annotations

import json
import pathlib
import random
import string
import time
from typing import List

import pytest

hypothesis = pytest.importorskip(
    "hypothesis",
    reason="hypothesis not installed (declared in packages/treescape-reference[test])",
)
from hypothesis import HealthCheck, given, settings, strategies as st  # noqa: E402

from treescape_reference.newick import parse as ref_parse
from treescape_reference.render import (
    SceneOptions,
    build_rectangular_scene,
)


REPORT_DIR = pathlib.Path(__file__).parent / "reports"


def _random_newick(rng: random.Random, n_tips: int) -> str:
    """Generate a random Newick string with ``n_tips`` named tips and
    random branch lengths in [0, 5]."""
    tip_names = [
        "t" + str(i)
        for i in range(n_tips)
    ]
    rng.shuffle(tip_names)

    # Build by repeated random pairing until one node remains.
    nodes: List[str] = [
        f"{name}:{rng.uniform(0.0, 5.0):.3f}" for name in tip_names
    ]
    while len(nodes) > 1:
        i = rng.randrange(len(nodes))
        a = nodes.pop(i)
        j = rng.randrange(len(nodes))
        b = nodes.pop(j)
        nodes.append(f"({a},{b}):{rng.uniform(0.0, 5.0):.3f}")
    # Strip the last branch length from the root since root has no parent.
    root = nodes[0]
    if root.startswith("(") and ":" in root:
        # remove the trailing ":xxx" past the matching close paren
        depth = 0
        end_paren = -1
        for i, c in enumerate(root):
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    end_paren = i
                    break
        if end_paren > 0:
            root = root[: end_paren + 1]
    return root + ";"


@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=2000,
)
@given(
    n_tips=st.integers(min_value=1, max_value=50),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_tip_count_and_bounds_invariant(n_tips: int, seed: int) -> None:
    rng = random.Random(seed)
    nwk = _random_newick(rng, n_tips)
    tree = ref_parse(nwk)
    scene = build_rectangular_scene(tree, SceneOptions())
    assert scene.count_tip_labels() == n_tips, (
        f"tip count drifted on n_tips={n_tips} seed={seed}: "
        f"got {scene.count_tip_labels()}"
    )
    assert scene.coords_within_canvas(eps=1e-6), (
        f"coords escape canvas on n_tips={n_tips} seed={seed}"
    )


@pytest.fixture(scope="session", autouse=True)
def _emit_report() -> None:
    yield
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "claim": "treescape-tip-count-invariant",
        "version": "0.1",
        "timestamp_utc": int(time.time()),
        "max_examples": 200,
        "n_tips_range": [1, 50],
    }
    (REPORT_DIR / "tip_count_invariant.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )
