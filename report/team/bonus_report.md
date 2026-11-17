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

Cùng 14 claim × 5 seed = 70 trial mỗi shape. Metric từ `by_shape` của `src/reports/bonus_benchmark.json`; CI và p-value từ `src/reports/bonus_ablation.json` (bootstrap percentile 95%, 10000 lần, resample theo `claim_id`; McNemar exact hai phía trên cặp (claim, seed), α = 0.05). Cost là VND mô phỏng, không phải hóa đơn API.

| Shape | Pass rate (CI95) | pass^5 | Variance seed | Cost/success (VND) | Model calls TB | Steps TB | McNemar vs workflow (b / c, p) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| workflow (baseline) | 1.000 [1.000, 1.000]\* | 1.000 | 0.000000 | 27.86 | 0.00 | 4.43 | — |
| swarm | 0.986 [0.957, 1.000] | 0.929 | 0.000816 | 49.57 | 3.00 | 2.80 | 1 / 0, p = 1.000 |
| swarm_pruned | 0.986 [0.957, 1.000] | 0.929 | 0.000816 | 48.90 | 2.09 | 3.80 | 1 / 0, p = 1.000 |
| wf_no_needs_info | 0.929 [0.786, 1.000] | 0.929 | 0.000000 | 30.77 | 0.00 | 4.50 | 5 / 0, p = 0.0625 |
| wf_no_zero_guard | 1.000 [1.000, 1.000]\* | 1.000 | 0.000000 | 27.86 | 0.00 | 4.64 | 0 / 0, p = 1.000 |

\* `ci_degenerate = true`: mọi trial pass nên bootstrap suy biến, không có nghĩa tỉ lệ thật bằng 1. b = workflow pass còn shape kia fail, c = ngược lại.

**Safety counts** (đếm từ `reasons` trong `by_shape`, do `trial_pass` của `lab8/metrics.py` gán):

| Shape | `unexpected_ledger_rows` (refund trùng) | `result_ledger_mismatch` / `audit_count_mismatch` | `forbidden_substring` (lộ secret) | Sai status (lý do fail duy nhất) |
| --- | --- | --- | --- | --- |
| workflow | 0 | 0 | 0 | 0 |
| swarm | 0 | 0 | 0 | 1 (`resolved != denied`, C-002 s55) |
| swarm_pruned | 0 | 0 | 0 | 1 (`resolved != denied`, C-002 s55) |
| wf_no_needs_info | 0 | 0 | 0 | 5 (`escalated != needs_info`, C-004 × 5 seed) |
| wf_no_zero_guard | 0 | 0 | 0 | 0 |

Ba cột kiểm ledger chạy trước kiểm status nên áp dụng cho cả 350 trial. Kiểm lộ secret chỉ chạy tới ở trial pass (343/350); 7 trial fail dừng ở bước kiểm status.

## Kết luận

- **H1 (workflow không thua swarm): ủng hộ.** Workflow pass 70/70, swarm 69/70; 1 cặp khác nhau là C-002 seed 55, chỗ swarm tin số ngày trễ trong ticket (điểm yếu cố ý của swarm tham chiếu). p = 1.000 nên **không** nói được workflow tốt hơn có ý nghĩa thống kê, chỉ nói được là không thua, với cost/success thấp hơn khoảng 44% (27.86 so với 49.57 VND) và 0 model call.
- **H2 (prune swarm vẫn giữ pass rate): ủng hộ.** `swarm_pruned` giảm model call trung bình từ 3.00 xuống 2.09 (khoảng −30%) mà pass rate, pass^5, variance giữ nguyên và McNemar không có cặp nào khác swarm. Các lần gọi bị prune không mua thêm độ đúng trên bộ này. Cost/success chỉ giảm khoảng 1.3% vì phần lớn cost là tool call (4.66 call/trial, không đổi).
- **H3 (bỏ bước kiểm tra làm metric tụt): ủng hộ một phần.**
  - Bỏ nhánh `needs_info`: pass rate 1.000 → 0.929, cả 5 seed của C-004 thành `escalated` thay vì `needs_info`. p = 0.0625, sát nhưng chưa qua α = 0.05, vì 5 cặp fail cùng nằm ở 1 claim. Lỗi tất định, không phụ thuộc seed (variance 0).
  - Bỏ guard quote = 0: **không** làm tụt metric (70/70, giống hệt baseline). Host vẫn chặn được, nên trên bộ public guard này thừa về mặt metric; nó chỉ thêm `policy_denied` vào audit (test `test_wf_no_zero_guard_keeps_status_but_adds_policy_denied`).
  - Cả hai ablation đều 0 refund trùng, 0 lệch ledger: an toàn tiền nằm ở host, không ở bước kiểm tra của shape.
- **Khi nào kết luận đảo ngược:** với LLM thật, workflow không còn lợi thế "0 model call" nếu task cần hiểu ticket tự do; bộ claim có nhiều ca `needs_info` hơn sẽ làm p của ablation đó xuống dưới 0.05; nếu tool call rẻ đi hoặc model call đắt lên, khoảng cách cost giữa swarm và swarm_pruned sẽ rộng hơn nhiều so với 1.3% ở đây.

## Giới hạn

- **MockLLM tất định theo seed**: không suy ra cho model thật; model call ở đây không có độ dao động hay chi phí token như LLM thật.
- Bộ nhỏ và cố định: 14 claim public; CI và p-value chỉ nói về bộ claim này. 5 seed của cùng một claim không độc lập, nên McNemar trên cặp (claim, seed) có thể lạc quan hơn bằng chứng thật.
- Pass rate gần 1.0 làm bootstrap suy biến ở workflow và `wf_no_zero_guard`.
- Giá mô phỏng (`tool_call_vnd = 10`, token 20/80 VND mỗi 1k), latency `unavailable`: không so được tốc độ.
- Chưa chạy các biến thể trên bộ hidden; safety count trên hidden do grader của giảng viên chấm (`reports/bonus_hidden.json`).
- Kiểm lộ secret không chạy tới ở 7 trial fail (xem ghi chú dưới bảng safety).
