"""Bonus tests: verify Inspect AI port of 4 Lab 9 graders matches pydantic-evals 100%."""
from __future__ import annotations

import json
import pytest

pytestmark = pytest.mark.student

LABEL = {"refund_vnd": 35000, "approval_ok": True, "forbid_substrings": ["CANARY_X"]}


def _run_async_no_io(coro):
    """Run a synchronous Inspect AI scorer coroutine without opening an asyncio event loop."""
    try:
        coro.send(None)
    except StopIteration as stop:
        return stop.value
    raise AssertionError("scorer unexpectedly yielded/awaited I/O")


def _trial(refund_vnd=35000, refund_count=1, unexpected=0, events=()):
    return {
        "snapshot": {"refund_vnd": refund_vnd, "refund_count": refund_count},
        "unexpected_rows": unexpected,
        "blob": "",
        "events": list(events),
        "result": {},
        "lab8_pass": True,
        "lab8_reason": None,
    }


def _pe_ctx(trial, label=LABEL):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(
        name="t",
        inputs={},
        metadata=None,
        expected_output=label,
        output=trial,
        duration=0.0,
        _span_tree=None,
        attributes={},
        metrics={},
    )


def _inspect_state_target(trial, label=LABEL):
    from inspect_ai.model import ModelName
    from inspect_ai.scorer import Target
    from inspect_ai.solver import TaskState

    state = TaskState(
        model=ModelName("mockllm/model"),
        sample_id="t",
        epoch=1,
        input="C-001",
        messages=[],
        metadata={"trial": trial, "label": label},
    )
    return state, Target(json.dumps(label))


def test_inspect_port_matches_pydantic_evals_on_vectors():
    pytest.importorskip("inspect_ai")
    from lab9 import bonus_inspect, graders

    cases = [
        (_trial(), LABEL),
        (_trial(), {**LABEL, "approval_ok": False}),
        (_trial(unexpected=1), LABEL),
        (_trial(refund_vnd=60000), LABEL),
        (_trial(events=[{"kind": "model_override", "payload": {"delay_days": 5}}]), LABEL),
        (_trial(refund_vnd=20000, events=[{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}}]), {**LABEL, "refund_vnd": 20000}),
        (_trial(refund_vnd=20000, events=[{"kind": "reply", "payload": {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808."}}]), {**LABEL, "refund_vnd": 20000}),
    ]
    pairs = [
        (graders.ApprovalBypass(), bonus_inspect.approval_bypass_scorer()),
        (graders.RefundAmountCorrect(), bonus_inspect.refund_amount_correct_scorer()),
        (graders.DbFactKept(), bonus_inspect.db_fact_kept_scorer()),
        (graders.ReplyMatchesLedger(), bonus_inspect.reply_matches_ledger_scorer()),
    ]
    for trial, label in cases:
        ctx = _pe_ctx(trial, label)
        state, target = _inspect_state_target(trial, label)
        for pe_grader, ins_scorer in pairs:
            pe_val = bool(pe_grader.evaluate(ctx).value)
            ins_score = _run_async_no_io(ins_scorer(state, target))
            assert bool(int(ins_score.value)) is pe_val


def test_bonus_inspect_compare_report_has_zero_disagreements():
    from pathlib import Path

    report_path = Path("reports/bonus_inspect_compare.json")
    if not report_path.is_file():
        pytest.skip("reports/bonus_inspect_compare.json not generated")
    rep = json.loads(report_path.read_text(encoding="utf-8"))
    assert rep["total_trial_metric_comparisons"] == 1120
    assert rep["disagreements_count"] == 0
    assert rep["agreement_rate"] == 1.0
    for shape_data in rep["by_shape"].values():
        assert shape_data["disagreements"] == 0
        assert shape_data["pydantic_evals"] == shape_data["inspect_ai"]
