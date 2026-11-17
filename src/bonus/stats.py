"""B4: thong ke cho benchmark. Chi dung thu vien chuan.

python -m bonus.stats --in reports/benchmark.json --baseline workflow \
    --out reports/bonus_ablation.json

Hai viec:
1. bootstrap 95% CI cho pass rate, resample THEO CLAIM (5 seed cua cung mot claim
   khong doc lap, resample theo trial se cho CI qua hep).
2. McNemar exact giua hai shape tren cung cap (claim, seed).

Ket luan trong file ra do code sinh ra, chi noi dieu du lieu cho phep.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_ALPHA = 0.05
DEFAULT_N_BOOT = 10000
DEFAULT_SEED = 20261117


def pass_rate(trials: Sequence[dict[str, Any]]) -> float:
    """Ty le trial pass. Khong co trial thi tra 0.0."""
    if not trials:
        return 0.0
    return sum(1 for t in trials if t["passed"]) / len(trials)


def bootstrap_ci(
    trials: Sequence[dict[str, Any]],
    *,
    n_boot: int = DEFAULT_N_BOOT,
    alpha: float = DEFAULT_ALPHA,
    seed: int = DEFAULT_SEED,
) -> tuple[float, float]:
    """CI percentile cho pass rate, resample theo claim_id.

    Moi lan: boc ngau nhien (co hoan lai) dung bang so claim, gop moi trial cua cac
    claim da boc, tinh pass rate. Lay phan vi alpha/2 va 1-alpha/2.
    Neu moi claim deu pass (hoac deu fail) thi CI suy bien thanh mot diem; day la
    gioi han cua bootstrap, khong phai bang chung rang ty le "chac chan" bang 1.
    """
    by_claim: dict[str, list[bool]] = defaultdict(list)
    for t in trials:
        by_claim[t["claim_id"]].append(bool(t["passed"]))
    claims = sorted(by_claim)
    if not claims:
        return (0.0, 0.0)
    passes = [sum(by_claim[c]) for c in claims]
    sizes = [len(by_claim[c]) for c in claims]
    rng = random.Random(seed)
    n = len(claims)
    rates: list[float] = []
    for _ in range(n_boot):
        total_pass = 0
        total_size = 0
        for _i in range(n):
            j = rng.randrange(n)
            total_pass += passes[j]
            total_size += sizes[j]
        rates.append(total_pass / total_size)
    rates.sort()
    lo_idx = int(math.floor((alpha / 2) * n_boot))
    hi_idx = int(math.ceil((1 - alpha / 2) * n_boot)) - 1
    return (rates[max(lo_idx, 0)], rates[min(hi_idx, n_boot - 1)])


def mcnemar_exact(b: int, c: int) -> float:
    """McNemar exact hai phia. b = A pass B fail, c = A fail B pass.

    Chi cac cap khac nhau (n = b + c) co thong tin. Duoi H0 thi so b ~ Binomial(n, 0.5).
    p = min(1, 2 * P(X <= min(b, c))). n = 0 thi khong co gi de kiem, tra 1.0.
    """
    if b < 0 or c < 0:
        raise ValueError("b va c phai >= 0")
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2 * tail)


def paired_outcomes(
    trials: Iterable[dict[str, Any]], shape_a: str, shape_b: str
) -> dict[str, int]:
    """Ghep cap (claim_id, seed) giua hai shape, dem b, c va cap dong y."""
    a: dict[tuple[str, int], bool] = {}
    b: dict[tuple[str, int], bool] = {}
    for t in trials:
        key = (t["claim_id"], int(t["seed"]))
        if t["shape"] == shape_a:
            a[key] = bool(t["passed"])
        elif t["shape"] == shape_b:
            b[key] = bool(t["passed"])
    common = sorted(set(a) & set(b))
    only_a_pass = sum(1 for k in common if a[k] and not b[k])
    only_b_pass = sum(1 for k in common if b[k] and not a[k])
    both_pass = sum(1 for k in common if a[k] and b[k])
    both_fail = sum(1 for k in common if not a[k] and not b[k])
    return {
        "pairs": len(common),
        "unpaired": len(set(a) ^ set(b)),
        "both_pass": both_pass,
        "both_fail": both_fail,
        "a_pass_b_fail": only_a_pass,
        "a_fail_b_pass": only_b_pass,
    }


def _conclusion(base: str, other: str, p: float, out: dict[str, int]) -> str:
    n_disc = out["a_pass_b_fail"] + out["a_fail_b_pass"]
    if out["pairs"] == 0:
        return f"{base} va {other}: khong co cap (claim, seed) chung, khong kiem dinh duoc."
    if n_disc == 0:
        return (
            f"{base} va {other}: ket qua giong het tren {out['pairs']} cap, "
            "khong co cap khac nhau nen khong co gi de kiem dinh."
        )
    if p < DEFAULT_ALPHA:
        return (
            f"{base} vs {other}: p={p:.4f} < {DEFAULT_ALPHA} tren {n_disc} cap khac nhau. "
            "Khac biet co y nghia thong ke tren bo claim nay; khong suy ra cho claim ngoai bo nay."
        )
    return (
        f"{base} vs {other}: p={p:.4f} >= {DEFAULT_ALPHA} tren {n_disc} cap khac nhau. "
        "Chua du bang chung de noi hai shape khac nhau; day khong chung minh hai shape bang nhau."
    )


def analyze(
    body: dict[str, Any],
    *,
    baseline: str,
    shapes: Sequence[str] | None = None,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Phan tich mot file benchmark da doc. Tra dict de ghi ra JSON."""
    trials = body["trials"]
    present = sorted({t["shape"] for t in trials})
    if baseline not in present:
        raise SystemExit(f"baseline '{baseline}' khong co trong file (co: {', '.join(present)})")
    others = [s for s in (shapes or present) if s != baseline]
    missing = [s for s in others if s not in present]
    if missing:
        raise SystemExit(f"shape khong co trong file: {', '.join(missing)}")

    by_shape: dict[str, Any] = {}
    for s in [baseline, *others]:
        rows = [t for t in trials if t["shape"] == s]
        lo, hi = bootstrap_ci(rows, n_boot=n_boot, seed=seed)
        by_shape[s] = {
            "trials": len(rows),
            "claims": len({t["claim_id"] for t in rows}),
            "passes": sum(1 for t in rows if t["passed"]),
            "pass_rate": pass_rate(rows),
            "ci95": [lo, hi],
            "ci_degenerate": lo == hi,
        }

    comparisons = []
    for s in others:
        out = paired_outcomes(trials, baseline, s)
        p = mcnemar_exact(out["a_pass_b_fail"], out["a_fail_b_pass"])
        comparisons.append(
            {
                "baseline": baseline,
                "other": s,
                **out,
                "p_value": p,
                "test": "mcnemar_exact_two_sided",
                "conclusion": _conclusion(baseline, s, p, out),
            }
        )

    return {
        "source": "bonus.stats",
        "baseline": baseline,
        "method": {
            "ci": f"bootstrap percentile 95%, {n_boot} lan, resample theo claim_id, seed={seed}",
            "paired_test": "McNemar exact hai phia tren cap (claim_id, seed)",
            "alpha": DEFAULT_ALPHA,
        },
        "controlled_variables": body.get("controlled_variables"),
        "by_shape": by_shape,
        "comparisons": comparisons,
        "limits": [
            "Bo claim nho va co dinh; CI va p-value chi noi ve bo claim nay.",
            "Pass rate gan 1.0: bootstrap co the cho CI suy bien (ci_degenerate=true), khong co nghia la ty le that bang 1.",
            "5 seed cua mot claim khong doc lap; McNemar tren cap (claim, seed) co the lac quan hon bang chung that.",
            "Model la MockLLM, khong suy ra cho model that.",
        ],
    }


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bootstrap CI va McNemar tren file benchmark")
    p.add_argument("--in", dest="inp", default="reports/benchmark.json")
    p.add_argument("--baseline", default="workflow")
    p.add_argument("--shapes", default=None, help="danh sach shape so voi baseline, cach nhau bang dau phay")
    p.add_argument("--out", required=True)
    p.add_argument("--n-boot", type=int, default=DEFAULT_N_BOOT)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    args = _parse_args(argv)
    body = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    shapes = [s.strip() for s in args.shapes.split(",") if s.strip()] if args.shapes else None
    result = analyze(body, baseline=args.baseline, shapes=shapes, n_boot=args.n_boot, seed=args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    for s, row in result["by_shape"].items():
        lo, hi = row["ci95"]
        print(f"{s:14s} pass={row['pass_rate']:.4f}  CI95=[{lo:.4f}, {hi:.4f}]  n={row['trials']}")
    for c in result["comparisons"]:
        print(f"{c['baseline']} vs {c['other']}: b={c['a_pass_b_fail']} c={c['a_fail_b_pass']} p={c['p_value']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
