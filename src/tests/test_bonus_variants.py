"""Tests for the B4 bonus variants: swarm_pruned and the two workflow ablations.

Each test uses a fresh SQLite store (same world and claims as the public matrix) so
trials cannot inherit idempotency from each other.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from bonus.swarm_pruned import run_claim as swarm_pruned
from bonus.workflow_ablate import wf_no_needs_info, wf_no_zero_guard
from lab8.db import connect, init_store
from lab8.shapes.swarm_reference import run_claim as swarm
from tests.conftest import CLAIMS, WORLD


def _store(tmp_path, name: str) -> Path:
    path = tmp_path / f"{name}.sqlite"
    init_store(path, WORLD, CLAIMS).close()
    return path


def _trace(result) -> dict:
    return json.loads(Path(result.trace_path).read_text(encoding="utf-8"))


def _ledger_rows(store: Path, claim_id: str) -> int:
    conn = sqlite3.connect(store)
    try:
        return int(
            conn.execute("SELECT COUNT(*) FROM refund_ledger WHERE claim_id = ?", (claim_id,)).fetchone()[0]
        )
    finally:
        conn.close()


def _policy_denied_reasons(store: Path, claim_id: str) -> list[str]:
    conn = sqlite3.connect(store)
    try:
        rows = conn.execute(
            "SELECT details_json FROM audit_events WHERE claim_id = ? AND event_type = 'policy_denied'",
            (claim_id,),
        ).fetchall()
    finally:
        conn.close()
    return [row[0] for row in rows]


def test_swarm_pruned_prunes_calls_without_changing_the_decision(tmp_path):
    base = swarm("C-002", seed=55, store_path=str(_store(tmp_path, "swarm")))
    pruned = swarm_pruned("C-002", seed=55, store_path=str(_store(tmp_path, "pruned")))

    # Same decision as the reference swarm, including its seed-55 weakness.
    assert pruned.status == base.status
    assert pruned.proposal_amount == base.proposal_amount
    assert pruned.model_calls <= base.model_calls

    plan = [e for e in _trace(pruned)["events"] if e["kind"] == "pruned"]
    assert len(plan) == 1
    flags = plan[0]["payload"]
    # A pruned call is not counted in the budget: 1 draft + kept peer/parse calls.
    assert pruned.model_calls == 1 + (0 if flags["peer"] else 1) + (0 if flags["parse"] else 1)


def test_swarm_pruned_is_deterministic(tmp_path):
    first = swarm_pruned("C-001", seed=11, store_path=str(_store(tmp_path, "a")))
    second = swarm_pruned("C-001", seed=11, store_path=str(_store(tmp_path, "b")))
    assert first.model_calls == second.model_calls

    def plan(result):
        return [e["payload"] for e in _trace(result)["events"] if e["kind"] == "pruned"]

    assert plan(first) == plan(second)


def test_wf_no_needs_info_escalates_missing_order(tmp_path):
    store = _store(tmp_path, "no_needs_info")
    result = wf_no_needs_info("C-004", seed=11, store_path=str(store))

    assert result.status == "escalated"
    assert result.proposal_amount == 0
    assert _ledger_rows(store, "C-004") == 0


def test_wf_no_zero_guard_keeps_status_but_adds_policy_denied(tmp_path):
    store = _store(tmp_path, "no_zero_guard")
    result = wf_no_zero_guard("C-002", seed=11, store_path=str(store))

    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert _ledger_rows(store, "C-002") == 0
    reasons = _policy_denied_reasons(store, "C-002")
    assert reasons, "the host should reject the zero quote and write a policy_denied audit"
    assert "non_positive_amount" in " ".join(reasons)
