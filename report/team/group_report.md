# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm:
- Thành viên: xem `TEAM.md`
- Commit chốt (trùng `report/team/decision_adr.md`):

## 2. Mục tiêu và cách tiếp cận

Nhóm hiểu bài toán thế nào, chia việc ra sao, thứ tự làm bốn shape.

...

## 3. Giải pháp

Mô tả ba shape nhóm viết (workflow, single, orchestrator): mỗi shape đọc gì, quyết định gì, gọi host ra sao. Chỉ rõ ranh giới code / model (tham khảo [docs/architecture.md](../../docs/architecture.md)), cách handoff được sanitize và trace ghi những event nào.

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

...

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md`. Phiếu nghiên cứu và ablation: xem `report/team/research_card.md`.

## 5. Khó khăn và cách xử lý

Lỗi gặp phải (kèm lệnh, output hoặc ảnh chụp) và cách nhóm xử lý.

...

## 6. Tổng hợp đóng góp

Chi tiết đóng góp của từng thành viên nằm trong `TEAM.md` (bảng đóng góp) và báo cáo cá nhân `report/team/MSSV_HoTen.md`.

## 7. Hạn chế và hướng cải thiện

MockLLM không phải model sản xuất; latency là `unavailable`. Nêu thêm giới hạn của nhóm và điều kiện làm kết luận thay đổi.

...

## 8. Tài liệu tham khảo

...
