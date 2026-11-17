"""Test cho bonus.stats (B4): McNemar exact, bootstrap theo claim, CLI."""

from __future__ import annotations

import json
import math

import pytest

from bonus import stats


def _trial(shape: str, claim: str, seed: int, passed: bool) -> dict:
    return {"shape": shape, "claim_id": claim, "seed": seed, "passed": passed}


def test_mcnemar_exact_known_values():
    assert stats.mcnemar_exact(0, 0) == 1.0
    assert stats.mcnemar_exact(3, 3) == 1.0
    assert stats.mcnemar_exact(1, 0) == 1.0  # 2 * 0.5 = 1, bi chan o 1
    assert math.isclose(stats.mcnemar_exact(5, 0), 2 * 0.5**5)
    # n=12, k=2: 2 * (1 + 12 + 66) / 4096
    assert math.isclose(stats.mcnemar_exact(10, 2), 2 * 79 / 4096)
    assert stats.mcnemar_exact(10, 2) == stats.mcnemar_exact(2, 10)
    with pytest.raises(ValueError):
        stats.mcnemar_exact(-1, 2)


def test_bootstrap_ci_resamples_by_claim_and_is_deterministic():
    # 4 claim x 5 seed; mot claim fail het -> resample theo claim phai cho CI rong
    trials = [_trial("s", f"C-{i}", seed, i != 0) for i in range(4) for seed in range(5)]
    lo, hi = stats.bootstrap_ci(trials, n_boot=2000, seed=1)
    assert 0.0 <= lo <= stats.pass_rate(trials) <= hi <= 1.0
    assert hi - lo > 0.2  # resample theo trial se hep hon nhieu
    assert stats.bootstrap_ci(trials, n_boot=2000, seed=1) == (lo, hi)

    all_pass = [_trial("s", f"C-{i}", seed, True) for i in range(4) for seed in range(5)]
    assert stats.bootstrap_ci(all_pass, n_boot=500, seed=1) == (1.0, 1.0)


def test_paired_outcomes_counts_and_unpaired():
    trials = [
        _trial("a", "C-1", 11, True), _trial("b", "C-1", 11, True),
        _trial("a", "C-1", 22, True), _trial("b", "C-1", 22, False),
        _trial("a", "C-2", 11, False), _trial("b", "C-2", 11, True),
        _trial("a", "C-2", 22, False), _trial("b", "C-2", 22, False),
        _trial("a", "C-3", 11, True),  # b khong co cap nay
    ]
    out = stats.paired_outcomes(trials, "a", "b")
    assert out == {
        "pairs": 4, "unpaired": 1, "both_pass": 1, "both_fail": 1,
        "a_pass_b_fail": 1, "a_fail_b_pass": 1,
    }


def test_cli_writes_report_and_claims_nothing_beyond_data(tmp_path, capsys):
    trials = []
    for claim in ("C-1", "C-2", "C-3"):
        for seed in (11, 22, 33):
            trials.append(_trial("workflow", claim, seed, True))
            trials.append(_trial("swarm", claim, seed, not (claim == "C-2" and seed == 33)))
    src = tmp_path / "bench.json"
    src.write_text(json.dumps({"controlled_variables": {"seeds": [11, 22, 33]}, "trials": trials}), encoding="utf-8")
    out = tmp_path / "out" / "bonus_ablation.json"

    rc = stats.main(["--in", str(src), "--baseline", "workflow", "--out", str(out), "--n-boot", "500"])
    assert rc == 0

    report = json.loads(out.read_text(encoding="utf-8"))
    assert set(report["by_shape"]) == {"workflow", "swarm"}
    assert report["by_shape"]["workflow"]["ci_degenerate"] is True
    cmp_ = report["comparisons"][0]
    assert (cmp_["a_pass_b_fail"], cmp_["a_fail_b_pass"]) == (1, 0)
    assert cmp_["p_value"] == 1.0
    assert "khong chung minh" in cmp_["conclusion"]  # p cao khong duoc ket luan "bang nhau"
    assert report["limits"]
    assert "workflow" in capsys.readouterr().out


def test_cli_unknown_baseline_exits(tmp_path):
    src = tmp_path / "b.json"
    src.write_text(json.dumps({"trials": [_trial("single", "C-1", 11, True)]}), encoding="utf-8")
    with pytest.raises(SystemExit):
        stats.main(["--in", str(src), "--baseline", "workflow", "--out", str(tmp_path / "o.json")])
