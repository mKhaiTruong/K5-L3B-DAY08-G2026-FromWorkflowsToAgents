"""Extra checks for Shape A (workflow) beyond the public T01–T14 matrix."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import lab8.shapes.workflow as workflow
from lab8.db import connect
from lab8.durability import InjectedCrash
from lab8.schemas import make_run_id
from tests.conftest import BY_ID


def _read_trace(result) -> dict:
    return json.loads(Path(result.trace_path).read_text(encoding="utf-8"))


def _audit_count(store: Path, claim_id: str, event_type: str) -> int:
    conn = connect(store)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_events WHERE claim_id = ? AND event_type = ?",
            (claim_id, event_type),
        ).fetchone()
        return int(row["n"])
    finally:
        conn.close()


def test_unknown_claim_fails_with_trace(public_db):
    result = workflow.run_claim("C-404", seed=11, store_path=str(public_db))

    assert result.status == "failed"
    assert result.error_reason == "unknown_claim"
    assert result.refund_effects == []
    assert _read_trace(result)["run_id"] == result.run_id


@pytest.mark.parametrize(
    ("claim_id", "status"),
    [("C-004", "needs_info"), ("C-005", "escalated")],
)
def test_early_return_writes_trace_and_skips_refund(public_db, monkeypatch, claim_id, status):
    def _must_not_refund(*args, **kwargs):
        raise AssertionError("issue_refund must not be called on an early return")

    monkeypatch.setattr(workflow, "issue_refund", _must_not_refund)
    result = workflow.run_claim(claim_id, seed=11, store_path=str(public_db))

    trace = _read_trace(result)
    assert result.status == status
    assert trace["run_id"] == result.run_id
    assert trace["events"], "trace must record at least the decision"


def test_escalated_trace_has_no_order_pii(public_db):
    result = workflow.run_claim("C-005", seed=11, store_path=str(public_db))

    blob = Path(result.trace_path).read_text(encoding="utf-8")
    for secret in BY_ID["C-005"]["expected"]["forbid_substrings"]:
        assert secret not in blob


def test_zero_quote_denies_without_policy_denied_audit(public_db, monkeypatch):
    def _must_not_refund(*args, **kwargs):
        raise AssertionError("issue_refund must not be called when quote is 0")

    monkeypatch.setattr(workflow, "issue_refund", _must_not_refund)
    result = workflow.run_claim("C-002", seed=55, store_path=str(public_db))

    assert result.status == "denied"
    assert result.proposal_amount == 0
    assert _audit_count(public_db, "C-002", "policy_denied") == 0


def test_full_quote_is_passed_to_issue_refund(public_db, monkeypatch):
    seen: list[int] = []
    real_issue_refund = workflow.issue_refund

    def _spy(conn, claim_id, proposed_vnd, **kwargs):
        seen.append(proposed_vnd)
        return real_issue_refund(conn, claim_id, proposed_vnd, **kwargs)

    monkeypatch.setattr(workflow, "issue_refund", _spy)
    result = workflow.run_claim("C-014", seed=11, store_path=str(public_db))

    assert seen == [150000], "shape must pass the full quote, not quote minus earlier refunds"
    assert result.status == "resolved"
    assert result.proposal_amount == 150000
    assert result.refund_effects[0]["amount_vnd"] == 120000


def test_workflow_makes_no_model_calls(public_db):
    result = workflow.run_claim("C-001", seed=11, store_path=str(public_db))

    assert result.status == "resolved"
    assert result.model_calls == 0
    assert result.tool_calls == 3


def test_crash_propagates_and_flushes_trace(public_db):
    with pytest.raises(InjectedCrash):
        workflow.run_claim(
            "C-012", seed=11, store_path=str(public_db), crash_at="after_effect_before_checkpoint"
        )

    trace_path = Path("traces") / f"{make_run_id('workflow', 'C-012', 11)}.json"
    events = json.loads(trace_path.read_text(encoding="utf-8"))["events"]
    assert any(e.get("kind") == "crash" for e in events)


# --- CP4: approval branches through run_claim (host gate, not the shape) -----


def _add_claim(conn, claim_id, order_id, approval_id, *, principal="P-100"):
    conn.execute(
        "INSERT INTO claims (claim_id, principal_id, order_id, ticket, parent_secret, raw_headers_json, approval_id) "
        "VALUES (?, ?, ?, 'test', 'CANARY_SECRET_PARENT_T', '{}', ?)",
        (claim_id, principal, order_id, approval_id),
    )


def _add_approval(conn, approval_id, claim_id, amount, status="valid", expires="2027-12-31"):
    conn.execute(
        "INSERT INTO approvals (approval_id, claim_id, approved_vnd, status, expires_at) VALUES (?, ?, ?, ?, ?)",
        (approval_id, claim_id, amount, status, expires),
    )


def _seed(store: Path, *, claims=(), approvals=()) -> None:
    conn = connect(store)
    try:
        for approval in approvals:
            _add_approval(conn, *approval)
        for claim in claims:
            _add_claim(conn, *claim)
        conn.commit()
    finally:
        conn.close()


def _assert_host_denied(store: Path, result, reason: str, proposal: int = 35000) -> None:
    """Check quote > 0 but host refused: denied, full quote kept, no ledger, policy_denied audit."""
    assert result.status == "denied"
    assert result.error_reason == reason
    assert result.proposal_amount == proposal
    assert result.refund_effects == []
    assert result.committed_audit_count == 0
    assert _audit_count(store, result.claim_id, "policy_denied") >= 1


def test_expired_approval_is_denied(public_db):
    result = workflow.run_claim("C-007", seed=11, store_path=str(public_db))

    _assert_host_denied(public_db, result, "approval_expired")


def test_revoked_approval_is_denied_even_with_a_spare_valid_one(public_db):
    _seed(
        public_db,
        approvals=[("A-WF-REVOKED", "C-WF-RV", 35000, "revoked"), ("A-WF-SPARE", "C-WF-RV", 35000, "valid")],
        claims=[("C-WF-RV", "O-909", "A-WF-REVOKED")],
    )
    result = workflow.run_claim("C-WF-RV", seed=11, store_path=str(public_db))

    _assert_host_denied(public_db, result, "approval_revoked")


def test_approval_of_another_claim_is_denied(public_db):
    _seed(public_db, claims=[("C-WF-BORROW", "O-808", "A-001")])
    result = workflow.run_claim("C-WF-BORROW", seed=11, store_path=str(public_db))

    _assert_host_denied(public_db, result, "approval_claim_mismatch")


def test_claim_without_approval_is_denied(public_db):
    _seed(public_db, claims=[("C-WF-NOAPP", "O-107", None)])
    result = workflow.run_claim("C-WF-NOAPP", seed=11, store_path=str(public_db))

    _assert_host_denied(public_db, result, "missing_approval")


def test_fully_refunded_order_is_denied(public_db):
    result = workflow.run_claim("C-013", seed=11, store_path=str(public_db))

    _assert_host_denied(public_db, result, "order_already_refunded")


# --- CP4: trace and stdout carry no raw claim/order rows ----------------------


@pytest.mark.parametrize("claim_id", sorted(BY_ID))
def test_trace_and_stdout_have_no_forbidden_substrings(public_db, capsys, claim_id):
    result = workflow.run_claim(claim_id, seed=11, store_path=str(public_db))

    blob = Path(result.trace_path).read_text(encoding="utf-8") + capsys.readouterr().out
    for secret in BY_ID[claim_id]["expected"]["forbid_substrings"] + ["CANARY_SECRET", "Bearer"]:
        assert secret not in blob, f"{secret!r} leaked for {claim_id}"
