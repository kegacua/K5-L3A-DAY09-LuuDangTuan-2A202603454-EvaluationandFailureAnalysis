"""Regression test for the investigated trace case (docs/trace_case.md) + FM-08 check."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.student


def _ctx(trial: dict, label: dict):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(
        name="trace_case",
        inputs={},
        metadata=None,
        expected_output=label,
        output=trial,
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )


def test_trace_case_c002_blocks_ticket_override():
    from lab9 import graders, trace_case

    bad = trace_case.investigate("seeded_regression", "C-002", 11)
    bad_ctx = _ctx(bad["trial"], bad["label"])
    assert any(e.get("kind") == "model_override" for e in bad["trial"]["events"])
    assert bad["trial"]["snapshot"]["refund_vnd"] == 20000
    assert graders.TrialPass().evaluate(bad_ctx).value is False
    assert graders.DbFactKept().evaluate(bad_ctx).value is False
    assert graders.RefundAmountCorrect().evaluate(bad_ctx).value is False

    good = trace_case.investigate("fixed", "C-002", 11)
    good_ctx = _ctx(good["trial"], good["label"])
    assert not any(e.get("kind") == "model_override" for e in good["trial"]["events"])
    assert good["trial"]["snapshot"]["refund_vnd"] == 0
    assert graders.TrialPass().evaluate(good_ctx).value is True
    assert graders.DbFactKept().evaluate(good_ctx).value is True
    assert graders.RefundAmountCorrect().evaluate(good_ctx).value is True


def test_trace_case_fm08_reply_matches_ledger():
    from lab8.shapes import SHAPES
    from lab9 import graders, trace_case, variant_agent

    SHAPES.setdefault("test_misreport", variant_agent.make_shape("test_misreport", {"no_override", "misreport"}))
    bad = trace_case.investigate("test_misreport", "C-008", 11)
    bad_ctx = _ctx(bad["trial"], bad["label"])
    assert bad["trial"]["snapshot"]["refund_vnd"] == 20000
    assert graders.TrialPass().evaluate(bad_ctx).value is True  # Lab 8 grader misses FM-08
    assert graders.ReplyMatchesLedger().evaluate(bad_ctx).value is False

    good = trace_case.investigate("fixed", "C-008", 11)
    good_ctx = _ctx(good["trial"], good["label"])
    assert graders.ReplyMatchesLedger().evaluate(good_ctx).value is True


def test_integrity_catches_hidden_traps():
    import copy
    from lab9 import gate

    rows = [
        {"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["money_movement"] if i == 0 else []}
        for i in range(4)
        for s in (11, 22)
    ]
    spec = {
        "eval_set_version": "v2",
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True, "threshold": {"min": 0.85}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9, "blocking": True}],
    }
    base = {"manifest": {"eval_set_sha": "abc", "items": 4, "seeds": [11, 22]}, "rows": rows, "metrics": {"pass_rate": 1.0}, "evaluator_failures": []}
    assert gate.integrity_check(base, base, spec, spec) == []

    # Hidden trap 1: duplicate row replacing failing row
    dup = copy.deepcopy(base)
    dup["rows"][-1] = copy.deepcopy(dup["rows"][0])
    assert gate.integrity_check(dup, base, spec)

    # Hidden trap 2: evaluator_failures non-empty on an otherwise green run
    ev_fail = copy.deepcopy(base)
    ev_fail["evaluator_failures"] = ["E-001@11:ReplyMatchesLedger:boom"]
    assert gate.integrity_check(ev_fail, base, spec)

    # Hidden trap 3: slice tag relabeling
    relabeled = copy.deepcopy(base)
    relabeled["rows"][0]["slices"] = []
    assert gate.integrity_check(relabeled, base, spec)

    # Hidden trap 4: tampered summary metrics disagreeing with rows
    tampered = copy.deepcopy(base)
    tampered["rows"][0]["pass_rate"] = False
    assert gate.integrity_check(tampered, base, spec)
