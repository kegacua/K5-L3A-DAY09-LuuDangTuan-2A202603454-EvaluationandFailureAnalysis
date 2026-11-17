"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def _ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    """Ensure thresholds and slices only get stricter on the same eval_set_version."""
    problems: list[str] = []
    if spec.get("eval_set_version") != base_spec.get("eval_set_version"):
        return problems
    if base_spec.get("seeds") and not set(base_spec["seeds"]).issubset(set(spec.get("seeds") or [])):
        problems.append("ratchet: spec seeds shrunk compared to base_spec")
    cur_metrics = {m["id"]: m for m in spec.get("metrics") or []}
    for bm in base_spec.get("metrics") or []:
        mid = bm["id"]
        if mid not in cur_metrics:
            problems.append(f"ratchet: metric {mid} removed")
            continue
        cm = cur_metrics[mid]
        if bm.get("blocking") and not cm.get("blocking"):
            problems.append(f"ratchet: metric {mid} became non-blocking")
        bth = bm.get("threshold") or {}
        cth = cm.get("threshold") or {}
        if "max" in bth and ("max" not in cth or cth["max"] > bth["max"]):
            problems.append(f"ratchet: metric {mid} max loosened ({cth.get('max')} > {bth['max']})")
        if "min" in bth and ("min" not in cth or cth["min"] < bth["min"]):
            problems.append(f"ratchet: metric {mid} min loosened ({cth.get('min')} < {bth['min']})")
        if "max_increase" in bth and ("max_increase" not in cth or cth["max_increase"] > bth["max_increase"]):
            problems.append(f"ratchet: metric {mid} max_increase loosened")
        if bth.get("no_significant_drop") and not cth.get("no_significant_drop"):
            problems.append(f"ratchet: metric {mid} dropped no_significant_drop")

    cur_slices = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for bs in base_spec.get("slices") or []:
        key = (bs["name"], bs["metric"])
        if key not in cur_slices:
            problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} removed")
            continue
        cs = cur_slices[key]
        if bs.get("blocking") and not cs.get("blocking"):
            problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} became non-blocking")
        if "min" in bs and ("min" not in cs or cs["min"] < bs["min"]):
            problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} min loosened")
        if "max" in bs and ("max" not in cs or cs["max"] > bs["max"]):
            problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} max loosened")
        if bs.get("no_significant_drop") and not cs.get("no_significant_drop"):
            problems.append(f"ratchet: slice {bs['name']}/{bs['metric']} dropped no_significant_drop")
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    pr_metrics = pr.get("metrics") or {}
    for k, v in pr_metrics.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isfinite(float(v)):
            problems.append(f"non-finite metric {k}={v}")

    for m in spec.get("metrics") or []:
        mid = m["id"]
        if mid in pr_metrics and pr_metrics[mid] is None and m.get("kind") in ("safety", "capability"):
            problems.append(f"metric {mid} is None")

    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures non-empty ({len(pr['evaluator_failures'])})")

    pr_manifest = pr.get("manifest") or {}
    base_manifest = base.get("manifest") or {}
    pr_rows = pr.get("rows") or []
    base_rows = base.get("rows") or []

    expected_n = int(pr_manifest.get("items", 0)) * len(pr_manifest.get("seeds") or [])
    if len(pr_rows) != expected_n:
        problems.append(f"row count {len(pr_rows)} != manifest items*seeds ({expected_n})")
    if len(pr_rows) != len(base_rows):
        problems.append(f"row count {len(pr_rows)} != baseline row count {len(base_rows)}")

    pr_keys = [(r.get("item_id"), r.get("seed")) for r in pr_rows]
    base_keys = [(r.get("item_id"), r.get("seed")) for r in base_rows]
    if len(set(pr_keys)) != len(pr_keys):
        problems.append("duplicate (item_id, seed) rows in PR report")
    if set(pr_keys) != set(base_keys):
        problems.append("(item_id, seed) set differs from baseline")

    if sorted(pr_manifest.get("seeds") or []) != sorted(base_manifest.get("seeds") or []):
        problems.append(f"manifest seeds {pr_manifest.get('seeds')} != baseline {base_manifest.get('seeds')}")

    row_metrics = {
        m["id"] for m in spec.get("metrics") or []
        if m["id"] in GRADERS or (base_rows and m["id"] in base_rows[0])
    }
    for r in pr_rows:
        for mid in row_metrics:
            val = r.get(mid)
            if val is None or (isinstance(val, (int, float)) and not isinstance(val, bool) and not math.isfinite(float(val))):
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has invalid {mid}={val}")
                break

    if pr_rows and not any("invalid" in p or "duplicate" in p for p in problems):
        for m in spec.get("metrics") or []:
            mid = m["id"]
            if mid not in pr_metrics or pr_metrics[mid] is None or mid not in pr_rows[0]:
                continue
            vals = [r[mid] for r in pr_rows]
            if any(v is None for v in vals):
                continue
            if mid in ("secret_leak", "approval_bypass"):
                expected_val = float(sum(bool(v) for v in vals))
            else:
                expected_val = sum(float(v) for v in vals) / len(vals)
            if isinstance(pr_metrics[mid], (int, float)) and math.isfinite(float(pr_metrics[mid])):
                if abs(float(pr_metrics[mid]) - expected_val) > 1e-3:
                    problems.append(f"metric {mid}={pr_metrics[mid]} disagrees with rows ({expected_val:.4f})")

    if pr_rows and "pass_rate" in pr_rows[0] and not any("invalid" in p or "duplicate" in p for p in problems):
        by_item: dict[str, list[bool]] = {}
        for r in pr_rows:
            by_item.setdefault(str(r.get("item_id")), []).append(bool(r.get("pass_rate")))
        if "pass_5" in pr_metrics and pr_metrics["pass_5"] is not None:
            expected_p5 = sum(all(v) for v in by_item.values()) / len(by_item)
            if isinstance(pr_metrics["pass_5"], (int, float)) and math.isfinite(float(pr_metrics["pass_5"])):
                if abs(float(pr_metrics["pass_5"]) - expected_p5) > 1e-3:
                    problems.append(f"metric pass_5={pr_metrics['pass_5']} disagrees with rows ({expected_p5:.4f})")
        for k in spec.get("pass_k", []) or []:
            key = f"pass_hat_{k}"
            if key in pr_metrics and pr_metrics[key] is not None and min(len(v) for v in by_item.values()) >= k:
                expected_phk = sum(stats.pass_hat_k(len(v), sum(v), k) for v in by_item.values()) / len(by_item)
                if isinstance(pr_metrics[key], (int, float)) and math.isfinite(float(pr_metrics[key])):
                    if abs(float(pr_metrics[key]) - expected_phk) > 1e-3:
                        problems.append(f"metric {key}={pr_metrics[key]} disagrees with rows ({expected_phk:.4f})")

    base_slices: dict[str, list[str]] = {}
    for r in base_rows:
        iid = r.get("item_id")
        if iid is not None:
            base_slices.setdefault(iid, sorted(r.get("slices") or []))
    for r in pr_rows:
        iid = r.get("item_id")
        if iid in base_slices and sorted(r.get("slices") or []) != base_slices[iid]:
            problems.append(f"item {iid} slice tags {r.get('slices')} differ from baseline {base_slices[iid]}")
            break

    if base_spec is not None:
        problems.extend(_ratchet_problems(spec, base_spec))

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        sname, mid = s["name"], s["metric"]
        sid = f"slice:{sname}/{mid}"
        a = per_item(pr, mid, slice_name=sname)
        b = per_item(base, mid, slice_name=sname)
        verdict, note = "ok", ""
        if not a:
            val = None
            verdict = "missing"
        else:
            val = round(sum(a.values()) / len(a), 4)
            if "min" in s and val < s["min"]:
                verdict = "fail"
            elif "max" in s and val > s["max"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap(
                        [a[k] for k in keys],
                        [b[k] for k in keys],
                        n_resamples=bs.get("n_resamples", 1000),
                        rng=bs.get("rng", 2027),
                        confidence=bs.get("confidence", 0.95),
                    )
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        th_view = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        lines.append(f"  {sid:<22} {val!s:<8} {json.dumps(th_view):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
