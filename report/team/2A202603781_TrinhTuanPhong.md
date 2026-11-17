# Báo cáo cá nhân — 2A202603781_TrinhTuanPhong

## 1. Thông tin thành viên

- Họ tên: Trịnh Tuấn Phong
- MSSV: 2A202603781
- Email:  26ai.phongtt2@vinuni.edu.vn
- GitHub: https://github.com/trinhtuanphong123

## 2. Phần việc phụ trách

- **Shape C — orchestrator** (`src/lab8/shapes/orchestrator.py`): handoff allowlist, investigator chỉ đọc, quote từ code, gọi host ghi refund và map `status`.
- **Handoff / security**: đảm bảo dữ liệu qua ranh giới chỉ gồm field allowlist, trace không lộ secret/PII.
- **Test**: `src/tests/test_orchestrator_handoff.py`.
- **CP4**: rà trace + stdout của cả 3 shape cho must-pass "không lộ `CANARY_SECRET_*`".
- **Báo cáo**: mục 3.3 (Shape C) trong `report/team/group_report.md` và đoạn "Trace và bằng chứng" cho `report/team/decision_adr.md` (gửi nhóm trưởng ghép).
- **Bonus B4 (variants)**: `src/bonus/swarm_pruned.py`, `src/bonus/workflow_ablate.py`, `src/tests/test_bonus_variants.py` — 2 biến thể + 2 ablation cho baseline công bằng.

## 3. Đóng góp cụ thể

Commit trên nhánh `feat/orchestrator` (đã merge vào `main` qua PR #8, merge commit `05fb00e`):

| Commit | Nội dung |
| --- | --- |
| `7891114` | scaffold `orchestrator.py`: vòng đời connection, `Budget`, `run_id`, `Trace`, tool cost |
| `38f0830` | nhánh sớm: `unknown_claim` → `failed`, thiếu `order_id` → `needs_info` |
| `75bb4bd` | handoff `handoff.v1` với 3 tool đọc đúng thứ tự + trace handoff đã sanitize |
| `e431092` | chạy investigator chỉ đọc, nhánh `escalated` khi đơn ngoài scope principal |
| `11e4d10` | quote từ code, `quote ≤ 0` → `denied`/0, gọi `issue_refund` với quote đầy đủ, map `conflict/failed`, `denied`, `resolved` |
| `fba76f5` | `test_orchestrator_handoff.py` (2 test) + dọn 2 điểm lệch của trace |

Quyết định kỹ thuật chính:

1. **Không truyền số đã trừ vào host**: luôn truyền quote đầy đủ để host tự trừ phần claim trước trên cùng đơn, tránh trừ hai lần (T13/T14).
2. **Luôn gọi `issue_refund` khi quote > 0**, kể cả khi shape đoán approval hỏng, vì chỉ host mới ghi được audit `policy_denied` — shape tự từ chối sẽ fail.
3. **Trace tối giản**: chỉ ghi `visible`/`reason`/`policy_count`/`quote`/`decision`, không dump `order_view` hay claim row; `safe_dump` không redact nên dữ liệu phải sạch từ trước.
4. **Không bắt `InjectedCrash`**: để crash thật nổi ra ngoài cho T12 kiểm, không "làm im" lỗi.
5. **Thứ tự `allowed_tools`**: `lookup_order` → `lookup_policy` → `compute_compensation`, vì `compute_compensation` chỉ chạy khi `lookup_order` đã có kết quả.

Nhánh `feat/bonus-variants` (PR #19): `ade5e01` thêm `swarm_pruned` (prune peer/parse p=0.5 theo
`random.Random(f"{seed}:{claim_id}")`) và 2 ablation `wf_no_needs_info` / `wf_no_zero_guard` + 4 test;
`1488547` bổ sung hidden selfcheck và mốc thời gian audit vào chính báo cáo này.
## 4. Bằng chứng

- Test riêng: `src/tests/test_orchestrator_handoff.py` — 2 test pass (`handoff` trong trace ⊆ `ALLOWED_FIELDS`, `allowed_tools ⊆ READONLY_TOOLS`, `facts == {}`, không `CANARY_SECRET_`/`parent_secret`; trace đúng contract trên 4 nhánh).
- Ma trận student: `python -m pytest -q -m student -o addopts=` → **248 passed** (62/62 của shape C; T11 + T12 nằm trong đó).
- Cổng host: `python -m pytest -q` → **102 passed, 0 failed** (sau khi merge main có `crash.json` + test CP4 của P1).
- Crash: `src/reports/crash.json` → `crash_safety: "20/20"`.
- Audit bảo mật CP4 (255 file trace của 4 shape, quét lúc 12:05 17/11 trên nhánh sau merge `d0ab363`): **0** vi phạm `CANARY_SECRET_`/`parent_secret`/`raw_headers`, **0** chứa SĐT `0901…`/địa chỉ/ghi chú nội bộ/tên hàng, **0** file phụ sai tên `^R-`, **0** lệnh `print(` trong `lab8/shapes/`; stdout claim C-010 sạch trên cả 3 shape.
- Hidden selfcheck (`src/reports/hidden_selfcheck.json`, 40 claim × 5 seed): orchestrator **200/200 trial, 0 error, 0 leak_suspect**, cost tổng **9.700 VND** (cao nhất trong 3 shape, do 4,85 tool call/trial); status trùng workflow và single trên toàn bộ 200 cặp (claim, seed): 90 resolved · 95 denied · 5 needs_info · 10 escalated.
- Run id mẫu: `R-orchestrator-C-001-s11` (resolved, ledger 35.000), `R-orchestrator-C-013-s11` (denied + `policy_denied: order_already_refunded`, ledger 0), `R-orchestrator-C-014-s11` (proposal 150.000, ledger 120.000).

- Bonus B4: `pytest -q tests/test_bonus_variants.py` → **4 passed**; cổng host **106 passed**.
  Benchmark 5 shape × 70 trial: workflow 1.000/27.86 · swarm 0.986/49.57 · **swarm_pruned 0.986/48.90**
  · **wf_no_needs_info 0.929/30.77** · **wf_no_zero_guard 1.000/27.86** (bỏ zero-guard không đổi metric
  vì host vẫn chặn `non_positive_amount`).
- `src/reports/bonus_benchmark.json`: 350 dòng `trials[]` (5 shape × 14 claim × 5 seed) cho McNemar cặp (claim, seed).
## 5. Công cụ AI đã dùng

- **Trợ lý AI (DeepSeek Harness)**: dùng để (a) đọc và đối chiếu bộ tài liệu (README, CHECKPOINTS, business_rules, contracts, architecture), (b) soạn khung code và test theo đúng docstring/hợp đồng của đề, (c) chẩn đoán lỗi môi trường (sandbox PowerShell, quoting khi truyền `python -c`), (d) soạn checklist và báo cáo.
- **Cách tự kiểm tra**: đọc lại từng thay đổi trước khi commit; tự chạy toàn bộ lệnh kiểm (`pytest -q -m student`, `pytest -q`, `-k "t11 or t12"`, `lab8.run` cho C-001/C-008/C-013/C-014, `crash_test`, audit trace); đối chiếu số tiền với `docs/business_rules.md` T01/T13/T14; tự chạy audit CP4 và kiểm lại bằng tay 2 lần. Không dùng AI để tạo số liệu, run id hay commit hash.
- Không có API key, không gọi model thật; mọi lời gọi model trong shape đi qua MockLLM. Không copy khối `REFERENCE_WEAKNESS` của swarm.

## 6. Tự đánh giá

**Điểm mạnh**: shape C hoàn chỉnh đủ 5 nhánh (`failed`/`needs_info`/`escalated`/`denied`/`resolved`), giữ đúng ranh giới code–model, trace tối giản và có test bảo vệ; phần audit CP4 cho bằng chứng định lượng (255 trace, 0 vi phạm) thay vì chỉ nói suông.

**Điểm cần cải thiện**: lần mở PR đầu tiên tôi để GitHub chọn base repository mặc định nên PR đi nhầm sang repo của ban tổ chức (đã đóng #133/#134); tôi cũng merge PR trước khi đồng bộ `main` nên phải chạy lại ma trận sau merge. Lần sau: kiểm dropdown `base repository` trước khi tạo PR và sync `main` vào nhánh **trước** khi merge. Ngoài ra phần code được AI hỗ trợ nhiều, nên tôi vẫn cần tự viết lại từ đầu ít nhất một lần để chắc mình giải thích được từng nhánh khi bị hỏi.
Phần bonus B4 giúp tôi thấy rõ một bước "kiểm tra" trong shape có thể **thừa** khi host đã chặn cùng điều kiện:
bỏ guard `quote <= 0` không đổi pass rate, còn bỏ guard `needs_info` thì tụt 0.929.
