# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm: G2026 (lớp L3B)
- Thành viên: xem `TEAM.md`
- Commit chốt (trùng `report/team/decision_adr.md`): `6f4f763`

## 2. Mục tiêu và cách tiếp cận

Nhóm hiểu bài toán thế nào, chia việc ra sao, thứ tự làm bốn shape.

**Bài toán:** xử lý claim bồi thường của LogiX-VN bằng 4 kiến trúc có mức tự chủ tăng dần: workflow tất định (A), một agent ReAct (B), orchestrator với investigator chỉ đọc (C), và swarm tham chiếu (D, có sẵn). Sau đó so 4 shape **bằng số đo** trên cùng claim, cùng seed, cùng bảng giá, rồi chọn một shape để chấm cổng hidden. Nhóm hiểu đây không phải bài "agent càng nhiều càng tốt". Câu hỏi đúng là: tự chủ thêm có mua được độ đúng không, và phải trả bao nhiêu cost, variance, rủi ro cho nó.

**Nguyên tắc chung cho cả 3 shape:**
- Tiền do code tính (`compute_compensation` từ order row), không do model. Ticket không bao giờ được dùng làm nguồn số liệu.
- Chỉ host (`durability.issue_refund`) được ghi tiền. Shape truyền **quote đầy đủ** để host tự áp approval, trần theo đơn và phần đã hoàn (T13, T14).
- Mọi nhánh return đi qua `common.finish()`, nên luôn có trace. Trace không chứa ticket, secret hay order row thô.

**Chia việc** (3 người, mỗi shape một file để không conflict):

| Người | Vai | Phần chính |
| --- | --- | --- |
| Trương Đặng Minh Khuê | P1 (lead) | workflow, integration (review/merge PR, chạy ma trận trên `main`), crash suite, benchmark, ADR |
| Triệu Quốc Khánh | P2 | single (ReAct), research card + ablation R2 |
| Trịnh Tuấn Phong | P3 | orchestrator, handoff sanitize |

**Thứ tự:** CP1 chốt vai và kế hoạch → CP2 ba shape làm song song trên 3 branch `feat/*`, mỗi PR cần ≥ 1 approve → CP3 truyền `crash_at`, T11/T12 xanh → CP4 crash suite 20/20 và rà approval/trace → CP5 benchmark, ADR, báo cáo. Swarm làm mốc so sánh từ đầu, vì đã có sẵn và đã biết điểm yếu.

## 3. Giải pháp

Mô tả ba shape nhóm viết (workflow, single, orchestrator): mỗi shape đọc gì, quyết định gì, gọi host ra sao. Chỉ rõ ranh giới code / model (tham khảo [docs/architecture.md](../../docs/architecture.md)), cách handoff được sanitize và trace ghi những event nào.

### 3.1 Shape A — workflow, phụ trách: Khuê

File: `src/lab8/shapes/workflow.py`. Pipeline tất định, **không có model call**: mọi nhánh rẽ đều là `if` trên dữ liệu DB.

| Bước | Hành động | Rẽ nhánh |
| --- | --- | --- |
| 1 | `get_claim_view` (4 cột, không `SELECT *`) | không thấy claim thì `failed` / `unknown_claim` |
| 2 | kiểm `order_id` | thiếu thì `needs_info`, không ghi ledger |
| 3 | `lookup_order(order_id, principal_id)` | không thấy hoặc sai principal thì `escalated` |
| 4 | `compute_compensation(order row)` | quote = 0 thì `denied`, không gọi host, nên không có audit `policy_denied` |
| 5 | `issue_refund(claim_id, quote đầy đủ, crash_at)` | `conflict` thì `failed`; host từ chối thì `denied` (proposal giữ quote); OK hoặc replay thì `resolved` |
| 6 | `finish()` | `RunResult` và file trace trên mọi nhánh |

Ranh giới code và model: không có model, nên không có gì để prompt injection bám vào. Approval, trần theo đơn, idempotency `refund:{claim_id}` đều do host giữ. Khi crash, shape ghi event `crash` rồi re-raise `InjectedCrash`. Lần chạy lại gặp dòng ledger cũ nên host trả `idempotent_replay`, không trả tiền 2 lần.

Trace ghi `claim` (`has_order_id`), `lookup_order` (`visible`, `reason`), `quote`, `issue_refund` (`ok`, `reason`, `conflict`), `decision`, `crash`. Cố ý không ghi: ticket, `parent_secret`, header, order row.

Kiểm tra: 62 test student pass (gồm T11, T12); `src/tests/test_workflow_extra.py` có 27 test (early return không gọi host, spy xác nhận truyền quote đầy đủ ở C-014, crash propagate, 5 nhánh approval hỏng, trace và stdout của 14 claim không chứa `forbid_substrings`).

### 3.2 Shape B — single (ReAct), phụ trách: Khánh

File: `src/lab8/shapes/single.py`. Một agent chạy vòng ReAct tối đa 8 bước qua `lab8.runtime.run_react`. `decide` là hàm Python xác định; mỗi bước gọi `complete()` của MockLLM để tính model call và chi phí.

Luồng xử lý một claim:

| Bước | Hành động | Đầu vào | Đầu ra |
| --- | --- | --- | --- |
| 1 | `get_claim_view` | `claim_id` | `claim_id`, `principal_id`, `order_id`, `ticket` (không có `parent_secret`) |
| 2 | `decide` lần 1 | `order_id` | gọi `lookup_order`; thiếu `order_id` thì kết thúc `needs_info` |
| 3 | `lookup_order` | `order_id`, `principal_id` | order qua allowlist (không có phone, địa chỉ, tên hàng, ghi chú nội bộ); không thấy hoặc sai principal thì kết thúc `escalated` |
| 4 | `compute_compensation` | order row | `amount_vnd`, `reason`, `clause_ids` |
| 5 | Sau vòng lặp | quote | quote ≤ 0 thì `denied`, không gọi host; quote > 0 thì `durability.issue_refund(claim_id, quote đầy đủ, crash_at)` |
| 6 | `finish()` | kết quả bước 5 | `RunResult` và file trace |

Ranh giới code và model:

| Việc | Ai quyết |
| --- | --- |
| Tool đọc nào gọi tiếp | `decide`, chỉ có `lookup_order` và `compute_compensation` |
| Số ngày trễ, trạng thái đơn | Order row trong DB, không lấy từ ticket |
| Số tiền | `compute_compensation` (code), policy cũ hoặc tương lai tự bị loại |
| Approval, trần theo đơn, idempotency, ghi ledger | Host (`durability.issue_refund`) |
| Câu chữ trả lời khách | MockLLM (`purpose="draft"`) |

Model không có tool ghi: `dispatch` ném `ToolRejected` nếu tên tool thuộc `WRITE_TOOLS`. `decide` không đọc ticket nên chữ như "ignore policy" hay "trễ 9 ngày" không đổi được quyết định.

Trace ghi các event `action`, `observation`, `decision`, `result`, `error`, `crash`. Nội dung ghi: tên tool, `visible`, `reason`, `amount_vnd`, `clause_ids`, `status`. Cố ý không ghi: ticket, claim row, order row thô. Mọi nhánh `return` đều đi qua `finish()` nên trace luôn được ghi. Khi crash, shape ghi trace rồi ném lại `InjectedCrash`, không nuốt lỗi.

Kiểm tra: 62 test student của shape B pass; `src/tests/test_single_extra.py` có 19 test (tool đọc và giới hạn 8 bước, không tin ticket, 7 nhánh approval, T11, T12 ở 3 điểm crash). Ablation swarm so với single nằm ở `report/team/research_card.md` và `src/reports/ablation_r2.json`.

### 3.3 Shape C — orchestrator + investigator chỉ đọc, phụ trách: Phong

File: `src/lab8/shapes/orchestrator.py`. Shape C chia làm hai tầng: **orchestrator** (điều phối, là nơi duy nhất gọi host ghi tiền) và **investigator** (chỉ đọc, chạy đúng các tool được cấp trong handoff). Orchestrator không đọc DB thô; mọi dữ liệu đi qua allowlist của tool đọc.

Luồng xử lý một claim:

| Bước | Hành động | Đầu vào | Đầu ra |
| --- | --- | --- | --- |
| 1 | `get_claim_view` | `claim_id` | `claim_id`, `principal_id`, `order_id` (không có `parent_secret`) |
| 2 | Rẽ nhánh sớm | claim view | claim không tồn tại → `failed`; thiếu `order_id` → `needs_info`, không ghi ledger |
| 3 | `make_handoff` | `claim_id`, 3 tool đọc | `handoff.v1`: 8 field allowlist, `facts={}`, `principal_scope="owner_order_only"` |
| 4 | `run_readonly_investigators` | handoff + `principal_id` | `lookup_order`, `lookup_policy`, `compute_compensation`; đơn không visible → `escalated` |
| 5 | Quote từ order view của investigator | order qua allowlist | `amount_vnd`; quote ≤ 0 → `denied`, **không** gọi host |
| 6 | `durability.issue_refund` | **quote đầy đủ** + `crash_at` | `conflict` → `failed`; host từ chối → `denied` (có audit `policy_denied`); ok → `resolved`. `proposal_amount` luôn là quote |
| 7 | `finish()` | kết quả bước 6 | `RunResult` + file trace |

Ranh giới code và model:

| Việc | Ai quyết |
| --- | --- |
| Dữ liệu nào được qua ranh giới | `make_handoff` + `ALLOWED_FIELDS`/`FACT_KEYS` (code) |
| Investigator được chạy tool nào | `READONLY_TOOLS`; `run_readonly_investigators(worker=True)` ném `ToolRejected` với tool ghi |
| Số ngày trễ, trạng thái đơn, quyền sở hữu đơn | order row trong DB, không lấy từ ticket |
| Số tiền | `compute_compensation` (code), policy cũ hoặc tương lai tự bị loại |
| Approval, trần theo đơn, idempotency, ghi ledger | Host (`durability.issue_refund`) |
| Câu chữ trả lời khách | MockLLM (nếu dùng); model không có tool ghi |

Cách handoff được sanitize: handoff chỉ gồm field trong `ALLOWED_FIELDS`, `facts` bị lọc theo `FACT_KEYS`, `principal_scope` gán cứng `owner_order_only`, và `allowed_tools` bị chặn nếu chứa tool ghi. `sanitize()` là chốt cuối: nếu payload còn `CANARY_SECRET_`, `parent_secret` hay `raw_headers` thì ném `HandoffError`. Tóm tắt nội dung cha bằng LLM **không** được dùng thay redaction — chỉ allowlist trong code.

Trace ghi các event `shape`, `handoff` (đã sanitize qua `safe_dump`), `investigator` (`visible`, `reason`, `policy_count`), `quote`, `decision` (`status`, `reason`). Cố ý không ghi: nội dung ticket, claim row (`parent_secret`, `raw_headers`), order row thô (SĐT, địa chỉ, ghi chú nội bộ, tên hàng). Mọi nhánh `return` — kể cả `needs_info` và `escalated` — đều đi qua `finish()` nên trace luôn được ghi; khi crash, `InjectedCrash` được ném ra ngoài, không bị nuốt.

Về mức tự chủ so với ba shape còn lại: A là pipeline bước cố định hoàn toàn do code, B là một agent ReAct tối đa 8 bước, C tách vai điều phối và điều tra rồi vẫn để code quyết tiền, D là swarm nhiều peer. C nằm giữa B và D về số điểm tự chủ nhưng giữ nguyên nguyên tắc: model chỉ đọc và soạn chữ, host mới ghi tiền.

Kiểm tra: 62 test student của shape C pass; `src/tests/test_orchestrator_handoff.py` có 2 test (handoff trong trace ⊆ `ALLOWED_FIELDS` và `allowed_tools ⊆ READONLY_TOOLS`; trace đúng contract trên 4 nhánh `needs_info`/`escalated`/`denied`/`resolved`). Audit bảo mật toàn nhóm: 255 file trace, 0 vi phạm secret/PII, 0 file phụ sai tên.

...

## 4. Kết quả

Bảng so sánh 4 shape trên bộ public (từ `src/reports/benchmark.json`): pass rate, pass^5, seed min–max, variance, cost/success, mean/p95 steps. Kèm crash safety (`src/reports/crash.json`) và, nếu có, kết quả tự kiểm trên `student_drop/`.

Điều kiện cố định: 14 claim public × seed `11,22,33,44,55` (70 trial mỗi shape), MockLLM, giá mô phỏng (`tool_call_vnd = 10`), mỗi trial một SQLite mới, latency `unavailable`.

| Shape | Pass | pass^5 | Seed min–max | Variance | Cost/success (VND) | Mean / p95 steps | Model / tool call mỗi trial |
| --- | --- | --- | --- | --- | --- | --- | --- |
| workflow | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 27.86 | 4.43 / 5 | 0.00 / 2.79 |
| single | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 29.74 | 4.64 / 5 | 3.79 / 2.79 |
| orchestrator | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 46.43 | 4.71 / 5 | 0.00 / 4.64 |
| swarm | 0.986 | 0.929 | 0.929–1.000 | 0.000816 | 49.57 | 2.80 / 3 | 3.00 / 4.66 |

- **Swarm** có 1 miss duy nhất, `R-swarm-C-002-s55`: ở seed chia hết cho 5, swarm tin "trễ 5 ngày" ghi trong ticket thay vì 2 ngày trong order row, nên trả tiền cho claim lẽ ra bị `denied`. Một lỗi ở 1/5 seed kéo pass^5 xuống 0.929, cho thấy vì sao pass^5 khắt khe hơn pass rate.
- **Orchestrator** đúng ngang workflow nhưng tốn gấp ~1.7 lần cost, vì investigator gọi thêm `lookup_policy` và các tool đọc qua handoff.
- **Crash safety:** 20/20 (`src/reports/crash.json`). Ma trận student đầy đủ: 248/248 (4 shape × 62).
- **Hidden (`student_drop/`):** chưa chạy tại commit `6f4f763`, vì bộ hidden chưa được phát.

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md`. Phiếu nghiên cứu và ablation: xem `report/team/research_card.md`.

## 5. Khó khăn và cách xử lý

Lỗi gặp phải (kèm lệnh, output hoặc ảnh chụp) và cách nhóm xử lý.

- **PR nhầm sang repo trường.** Repo nhóm là fork của `VinUni-AI20k/...`, nên GitHub mặc định base của PR là repo gốc. Dấu hiệu: số commit nhảy từ 2 lên 53. Hai PR nhầm đã được đóng. Cách xử lý: mở PR bằng link `.../compare/main...feat/orchestrator` của chính repo nhóm.
- **Review không mở khóa merge.** Branch `main` được bảo vệ bằng rule ≥ 1 approve, nhưng review đầu tiên chọn **Comment** ("very good") thay vì **Approve**, nên `reviewDecision = REVIEW_REQUIRED`. Cách xử lý: submit lại với loại Approve.
- **`-k single` lọc nhầm.** Lệnh tự kiểm `pytest -m student -k single` kéo theo `test_public_single_run_cases` của mọi shape, ra 60 failed giả. Cách xử lý: dùng `-k "single and not workflow and not orchestrator and not swarm"`.
- **Chạy nhầm Python.** Prompt hiện `(.venv)` nhưng `python` lại trỏ về Anaconda `(base)`, cộng thêm việc gõ thiếu `-m`, nên ra lỗi `C:\Users\Public\Anaconda3\python.exe: can't open file '...lab8.crash_test'`. Cách xử lý: thêm `-m` và gọi thẳng `.venv\Scripts\python.exe -m ...`.
- **T12 ở CP2.** `CHECKPOINTS.md` ghi CP2 phải ra 62 passed, nhưng T12 cần `crash_at`, việc này thuộc `TODO CP3`. Nhóm giữ ranh giới checkpoint: CP2 chốt ở 61/62, CP3 truyền `crash_at` thì đạt 62/62.

## 6. Tổng hợp đóng góp

Chi tiết đóng góp của từng thành viên nằm trong `TEAM.md` (bảng đóng góp) và báo cáo cá nhân `report/team/MSSV_HoTen.md`.

## 7. Hạn chế và hướng cải thiện

MockLLM không phải model sản xuất; latency là `unavailable`. Nêu thêm giới hạn của nhóm và điều kiện làm kết luận thay đổi.

...

## 8. Tài liệu tham khảo

...
