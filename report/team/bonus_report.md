# Bonus report: B4

- Topic + nguồn (tên, năm, slide): B4 · Baseline công bằng, ablation và thống kê. EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* (slide 44, 59); AgentArch, AACL 2026 (slide 43).
- CLAIM của nguồn (1 câu): "efficiency gain" của multi-agent có thể đến từ cách thiết kế benchmark; có lúc random pruning vẫn giữ được hiệu năng, nên phải so với single-agent và baseline đơn giản, với runtime, model và tool giữ cố định.
- BOUNDARY (model / dataset / setup): nguồn đo trên LLM thật và benchmark MAS tổng quát; ở đây là MockLLM tất định theo seed, 14 claim public của LogiX-VN × 5 seed (11, 22, 33, 44, 55), giá mô phỏng (`tool_call_vnd = 10`), latency `unavailable`, mỗi trial một SQLite mới. Ablation chỉ trên shape nhóm chọn (workflow), không có model call nên ablation bỏ **bước kiểm tra** thay vì bỏ model call.
- HYPOTHESIS trên LogiX: (1) workflow rules-only không thua swarm có ý nghĩa thống kê trên bộ public; (2) swarm bị prune ngẫu nhiên các lần gọi peer/parse vẫn giữ pass rate, tức là các lần gọi đó không mua thêm độ đúng; (3) bỏ bước kiểm tra trong workflow (nhánh `needs_info`, nhánh quote = 0) làm metric tụt, dù host vẫn giữ an toàn tiền.
- Biến cố định / biến thay đổi: cố định 14 claim public × seed 11,22,33,44,55, MockLLM, bảng giá mô phỏng, SQLite mới mỗi trial; thay đổi shape (workflow, swarm, swarm_pruned, wf_no_needs_info, wf_no_zero_guard).
- Lệnh tái lập (copy-paste được), chạy trong `src/`:
  - `python -m lab8.benchmark --shapes workflow,swarm,swarm_pruned,wf_no_needs_info,wf_no_zero_guard --extra-shape swarm_pruned=bonus.swarm_pruned:run_claim --extra-shape wf_no_needs_info=bonus.workflow_ablate:wf_no_needs_info --extra-shape wf_no_zero_guard=bonus.workflow_ablate:wf_no_zero_guard --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/bonus_benchmark.json`
  - `python -m bonus.stats --in reports/bonus_benchmark.json --baseline workflow --out reports/bonus_ablation.json`
  - `python -m pytest -q tests/test_bonus_variants.py tests/test_bonus_stats.py`
- File report + run id: `src/reports/bonus_benchmark.json`, `src/reports/bonus_ablation.json`. Run id theo mẫu `R-<shape>-<claim>-s<seed>`, ví dụ baseline `R-workflow-C-001-s11`; các trial fail: `R-swarm-C-002-s55`, `R-swarm_pruned-C-002-s55`, `R-wf_no_needs_info-C-004-s11` … `-s55`

## Phân công

| Người | Việc | File | Branch |
| --- | --- | --- | --- |
| Trịnh Tuấn Phong (P3) | Biến thể shape: `swarm_pruned` và 2 ablation của workflow, kèm test | `src/bonus/__init__.py`, `src/bonus/swarm_pruned.py`, `src/bonus/workflow_ablate.py`, `src/tests/test_bonus_variants.py` | `feat/bonus-variants` |
| Triệu Quốc Khánh (P2) | Thống kê: bootstrap 95% CI theo claim, McNemar exact theo cặp (claim, seed), kèm test | `src/bonus/stats.py`, `src/tests/test_bonus_stats.py` | `feat/bonus-stats` |
| Trương Đặng Minh Khuê (P1) | Chạy benchmark với `--extra-shape`, chạy `stats.py`, viết báo cáo này, review và merge | `src/reports/bonus_*.json`, `report/team/bonus_report.md` | `docs/bonus-b4-*` |

## Kết quả

70 trial mỗi shape (14 claim × 5 seed). Metric từ `by_shape` của `src/reports/bonus_benchmark.json`; CI95 (bootstrap 10000 lần, resample theo claim) và McNemar exact trên cặp (claim, seed) từ `src/reports/bonus_ablation.json`. Cost là VND mô phỏng.

| Shape | Pass (CI95) | pass^5 | Var seed | Cost/success | Model call TB | McNemar vs workflow (b/c, p) | Safety: trùng / lệch ledger / lộ secret |
| --- | --- | --- | --- | --- | --- | --- | --- |
| workflow | 1.000 [1.000, 1.000]\* | 1.000 | 0 | 27.86 | 0.00 | — | 0 / 0 / 0 |
| swarm | 0.986 [0.957, 1.000] | 0.929 | 0.000816 | 49.57 | 3.00 | 1/0, p = 1.000 | 0 / 0 / 0 |
| swarm_pruned | 0.986 [0.957, 1.000] | 0.929 | 0.000816 | 48.90 | 2.09 | 1/0, p = 1.000 | 0 / 0 / 0 |
| wf_no_needs_info | 0.929 [0.786, 1.000] | 0.929 | 0 | 30.77 | 0.00 | 5/0, p = 0.0625 | 0 / 0 / 0 |
| wf_no_zero_guard | 1.000 [1.000, 1.000]\* | 1.000 | 0 | 27.86 | 0.00 | 0/0, p = 1.000 | 0 / 0 / 0 |

\* `ci_degenerate = true` (mọi trial pass), không có nghĩa tỉ lệ thật bằng 1. b = workflow pass, shape kia fail; c = ngược lại. Safety đếm từ `reasons` do `trial_pass` gán: `unexpected_ledger_rows` / `result_ledger_mismatch` + `audit_count_mismatch` / `forbidden_substring`. Mọi trial fail đều là sai status: swarm và swarm_pruned ở C-002 s55 (`resolved != denied`), wf_no_needs_info ở C-004 × 5 seed (`escalated != needs_info`).

## Kết luận

- **H1: ủng hộ.** Workflow 70/70, swarm 69/70 (khác đúng 1 cặp, C-002 s55: swarm tin số ngày trễ trong ticket). p = 1.000 nên chỉ nói được workflow **không thua**, không nói được tốt hơn có ý nghĩa thống kê; cost/success thấp hơn khoảng 44%, 0 model call.
- **H2: ủng hộ.** `swarm_pruned` bớt khoảng 30% model call (3.00 → 2.09) mà pass rate, pass^5, variance không đổi: các lần gọi bị prune không mua thêm độ đúng. Cost chỉ giảm khoảng 1.3% vì phần lớn cost là tool call.
- **H3: ủng hộ một phần.** Bỏ nhánh `needs_info` làm pass tụt còn 0.929 (C-004 thành `escalated`, tất định ở cả 5 seed), nhưng p = 0.0625 chưa qua α = 0.05 vì 5 cặp fail cùng một claim. Bỏ guard quote = 0 **không** làm tụt metric: host vẫn chặn, chỉ thêm `policy_denied` vào audit. Cả hai ablation 0 lệch ledger: an toàn tiền nằm ở host.
- **Đảo ngược khi:** ticket tự do cần model hiểu (workflow mất lợi thế 0 model call); bộ claim có nhiều ca `needs_info` hơn (p của ablation có thể xuống dưới 0.05); model call đắt hơn tool call (pruning tiết kiệm nhiều hơn 1.3%).

## Giới hạn

- **MockLLM tất định theo seed**: không suy ra cho LLM thật (không có dao động hay chi phí token thật).
- 14 claim public cố định; 5 seed của một claim không độc lập nên McNemar trên cặp (claim, seed) có thể lạc quan; pass gần 1.0 làm bootstrap suy biến.
- Giá mô phỏng, latency `unavailable`: không so được tốc độ.
- Kiểm lộ secret chạy sau kiểm status, nên không chạy tới ở 7 trial fail (343/350 được kiểm). Safety trên hidden do grader của giảng viên chấm.
