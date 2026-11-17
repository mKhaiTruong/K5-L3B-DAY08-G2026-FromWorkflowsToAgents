"""Shape C end-to-end: the traced handoff stays inside the allowlist, and every
return branch writes a contract-v1 trace. Complements the unit tests in
test_handoff_secret.py, which only exercise sanitize()/make_handoff().
"""

import json
from pathlib import Path

from lab8.handoff import ALLOWED_FIELDS, READONLY_TOOLS
from lab8.shapes import SHAPES

ORCH = SHAPES["orchestrator"]


def _trace(result):
    return json.loads(Path(result.trace_path).read_text(encoding="utf-8"))


def test_handoff_in_trace_uses_allowlist_only(public_db):
    result = ORCH("C-001", seed=11, store_path=str(public_db))
    body = _trace(result)
    assert body["run_id"] == result.run_id

    handoffs = [e["payload"] for e in body["events"] if e["kind"] == "handoff"]
    assert len(handoffs) == 1
    pay = handoffs[0]
    assert set(pay) <= ALLOWED_FIELDS
    assert set(pay["allowed_tools"]) <= READONLY_TOOLS
    assert pay["facts"] == {}
    assert pay["contract_version"] == "handoff.v1"

    text = Path(result.trace_path).read_text(encoding="utf-8")
    for bad in ("CANARY_SECRET_", "parent_secret", "raw_headers", "Authorization"):
        assert bad not in text


def test_every_branch_writes_a_contract_trace(public_db):
    expected = {
        "C-004": ["shape", "decision"],
        "C-005": ["shape", "handoff", "investigator", "decision"],
        "C-002": ["shape", "handoff", "investigator", "quote", "decision"],
        "C-001": ["shape", "handoff", "investigator", "quote", "decision"],
    }
    for claim_id, kinds in expected.items():
        result = ORCH(claim_id, seed=11, store_path=str(public_db))
        body = _trace(result)
        assert body["run_id"] == result.run_id, claim_id
        got = [e["kind"] for e in body["events"]]
        assert got == kinds, (claim_id, got)
        assert "CANARY_SECRET_" not in json.dumps(body, ensure_ascii=False), claim_id
