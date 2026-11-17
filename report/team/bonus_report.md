# Bonus report: B4

- Topic + nguồn (tên, năm, slide): B4 · Baseline công bằng, ablation và thống kê. EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* (slide 44, 59); AgentArch, AACL 2026 (slide 43).
- CLAIM của nguồn (1 câu): "efficiency gain" của multi-agent có thể đến từ cách thiết kế benchmark; có lúc random pruning vẫn giữ được hiệu năng, nên phải so với single-agent và baseline đơn giản, với runtime, model và tool giữ cố định.
- BOUNDARY (model / dataset / setup): (điền sau khi có số liệu)
- HYPOTHESIS trên LogiX: (1) workflow rules-only không thua swarm có ý nghĩa thống kê trên bộ public; (2) swarm bị prune ngẫu nhiên các lần gọi peer/parse vẫn giữ pass rate, tức là các lần gọi đó không mua thêm độ đúng; (3) bỏ bước kiểm tra trong workflow (nhánh `needs_info`, nhánh quote = 0) làm metric tụt, dù host vẫn giữ an toàn tiền.
- Biến cố định / biến thay đổi: cố định 14 claim public × seed 11,22,33,44,55, MockLLM, bảng giá mô phỏng, SQLite mới mỗi trial; thay đổi shape (workflow, swarm, swarm_pruned, wf_no_needs_info, wf_no_zero_guard).
- Lệnh tái lập (copy-paste được): (điền sau khi các PR bonus merge)
- File report + run id: `src/reports/bonus_benchmark.json`, `src/reports/bonus_ablation.json` (điền run id sau)

## Phân công

| Người | Việc | File | Branch |
| --- | --- | --- | --- |
| Trịnh Tuấn Phong (P3) | Biến thể shape: `swarm_pruned` và 2 ablation của workflow, kèm test | `src/bonus/__init__.py`, `src/bonus/swarm_pruned.py`, `src/bonus/workflow_ablate.py`, `src/tests/test_bonus_variants.py` | `feat/bonus-variants` |
| Triệu Quốc Khánh (P2) | Thống kê: bootstrap 95% CI theo claim, McNemar exact theo cặp (claim, seed), kèm test | `src/bonus/stats.py`, `src/tests/test_bonus_stats.py` | `feat/bonus-stats` |
| Trương Đặng Minh Khuê (P1) | Chạy benchmark với `--extra-shape`, chạy `stats.py`, viết báo cáo này, review và merge | `src/reports/bonus_*.json`, `report/team/bonus_report.md` | `docs/bonus-b4-*` |

## Kết quả

(điền từ `src/reports/bonus_ablation.json`)

## Kết luận

(điền sau)

## Giới hạn

(điền sau; bắt buộc nêu MockLLM)
