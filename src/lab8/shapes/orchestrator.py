"""Shape C — orchestrator plus read-only investigators. Student work.

1. Build a handoff with `lab8.handoff.make_handoff`. Allowed tools are read-only.
   Never put parent_secret, raw headers, or the full claim row into facts.
2. `lab8.runtime.run_readonly_investigators` runs those tools.
3. The orchestrator quotes from the investigator's order view and calls
   `durability.issue_refund`. Investigators have no write registry.
   Pass the full quote; the host subtracts earlier refunds on the same order.
   `lookup_refund_history` is a read-only tool you may hand to an investigator.
4. Trace the sanitized handoff, not the parent context.

An LLM summary of the parent context is not a sanitizer. Use the allowlist.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import issue_refund
from lab8.handoff import make_handoff
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, tool_cost
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
) -> RunResult:
    """Run one claim: early exits, handoff, investigators, quote, then the host write."""
    budget = Budget()
    run_id = make_run_id("orchestrator", claim_id, seed)
    trace = Trace(run_id)
    budget.add_tool(tool_cost())
    trace.add("shape", {"status": "start"})

    # T2: read the claim through the allowlisted tool. The ticket text is data,
    # never a source for order ids, delays, or policy clauses.
    claim = get_claim_view(conn, claim_id)
    if not claim["found"]:
        trace.add("error", {"reason": "unknown_claim"})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="unknown_claim",
        )

    if not claim.get("order_id"):
        trace.add("decision", {"status": "needs_info"})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="needs_info",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason="missing_order_id",
        )

    # T3: handoff.v1 with read-only tools only. Facts stay empty: the investigator
    # reads the order through its own tool, never from the parent context.
    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="check_applicable_policy",
        facts={},
        allowed_tools=["lookup_order", "lookup_policy", "compute_compensation"],
    )
    trace.add("handoff", safe_dump(handoff))

    # T4: read-only investigators run inside the handoff scope. They never get the
    # parent context, a write tool, or the ticket text.
    investigated = run_readonly_investigators(
        conn, budget, handoff, principal_id=claim["principal_id"]
    )
    order_view = investigated["tools"].get("lookup_order") or {}
    policies = (investigated["tools"].get("lookup_policy") or {}).get("policies") or []
    trace.add(
        "investigator",
        {
            "visible": bool(order_view.get("visible")),
            "reason": order_view.get("reason"),
            "policy_count": len(policies),
        },
    )
    if not order_view.get("visible"):
        trace.add("decision", {"status": "escalated", "reason": order_view.get("reason")})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="escalated",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=order_view.get("reason"),
        )

    # T5: money comes from code. The ticket never supplies the delay or the clause.
    order = order_view.get("order") or {}
    quote_payload = investigated["tools"].get("compute_compensation") or {}
    if not quote_payload and order:
        # Defensive: only happens if the allowlist order was edited.
        budget.add_tool(tool_cost())
        quote_payload = compute_compensation(conn, order)
    quote = int(quote_payload.get("amount_vnd") or 0)
    trace.add("quote", quote_payload)

    if quote <= 0:
        trace.add("decision", {"status": "denied", "reason": quote_payload.get("reason")})
        return finish(
            conn,
            shape="orchestrator",
            claim_id=claim_id,
            seed=seed,
            status="denied",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=quote_payload.get("reason"),
        )

    # T6: the host is the only writer. Always call it with the FULL quote: the host
    # subtracts earlier refunds on the same order (T13, T14).
    outcome = issue_refund(conn, claim_id, quote, crash_at=crash_at)
    if outcome["conflict"]:
        status, reason = "failed", outcome["reason"]
    elif not outcome["ok"]:
        status, reason = "denied", outcome["reason"]
    else:
        status, reason = "resolved", None
    trace.add("decision", {"status": status, "reason": outcome["reason"]})
    return finish(
        conn,
        shape="orchestrator",
        claim_id=claim_id,
        seed=seed,
        status=status,
        proposal_amount=quote,
        budget=budget,
        trace=trace,
        error_reason=reason,
    )
