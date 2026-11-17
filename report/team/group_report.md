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
