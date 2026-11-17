"""Bonus variants: workflow with one component removed (B4 ablation).

Both variants copy `lab8.shapes.workflow` and drop exactly one step:

- `wf_no_needs_info`: no early return for a missing `order_id`.
- `wf_no_zero_guard`: no early return when the quote is 0.

Everything else (host write, full quote, trace on every return path) is unchanged,
so any metric difference comes from the removed step alone.
"""

from __future__ import annotations

import sqlite3
from functools import partial

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, lookup_order, tool_cost
from lab8.trace import Trace


def wf_no_needs_info(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    return _entry(claim_id, seed=seed, store_path=store_path, crash_at=crash_at, mode="wf_no_needs_info")


def wf_no_zero_guard(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    return _entry(claim_id, seed=seed, store_path=store_path, crash_at=crash_at, mode="wf_no_zero_guard")


def _entry(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None,
    mode: str,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at, mode=mode)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
    mode: str,
) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(mode, claim_id, seed))
    done = partial(finish, conn, shape=mode, claim_id=claim_id, seed=seed, budget=budget, trace=trace)

    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim["found"]:
        trace.add("decision", {"status": "failed", "reason": "unknown_claim"})
        return done(status="failed", proposal_amount=0, error_reason="unknown_claim")
    trace.add("claim", {"claim_id": claim_id, "has_order_id": bool(claim["order_id"])})

    # Ablation: the needs_info guard is removed, so a missing order_id falls through
    # to lookup_order(None) and becomes `escalated` instead.
    if mode != "wf_no_needs_info" and not claim["order_id"]:
        trace.add("decision", {"status": "needs_info", "reason": "missing_order_id"})
        return done(status="needs_info", proposal_amount=0, error_reason="missing_order_id")

    budget.add_tool(tool_cost())
    order_view = lookup_order(conn, claim["order_id"], claim["principal_id"])
    trace.add("lookup_order", {"visible": order_view["visible"], "reason": order_view["reason"]})
    if not order_view["visible"]:
        trace.add("decision", {"status": "escalated", "reason": order_view["reason"]})
        return done(status="escalated", proposal_amount=0, error_reason=order_view["reason"])

    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order_view["order"])
    proposal = int(quote["amount_vnd"])
    trace.add("quote", safe_dump(quote))

    # Ablation: the quote<=0 guard is removed, so a zero quote still calls the host.
    # The host rejects it (`non_positive_amount`) and writes a policy_denied audit.
    if mode != "wf_no_zero_guard" and proposal <= 0:
        trace.add("decision", {"status": "denied", "reason": quote["reason"]})
        return done(status="denied", proposal_amount=0, error_reason=quote["reason"])

    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    trace.add("issue_refund", {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})
    if not outcome["ok"]:
        status = "failed" if outcome["conflict"] else "denied"
        trace.add("decision", {"status": status, "reason": outcome["reason"]})
        return done(status=status, proposal_amount=proposal, error_reason=outcome["reason"])

    trace.add("decision", {"status": "resolved", "reason": outcome["reason"]})
    return done(status="resolved", proposal_amount=proposal, error_reason=None)
