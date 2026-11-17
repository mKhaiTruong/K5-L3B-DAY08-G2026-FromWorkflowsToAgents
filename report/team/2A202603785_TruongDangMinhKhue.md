# Báo cáo cá nhân — 2A202603785_TruongDangMinhKhue

## 1. Thông tin thành viên

- Họ tên: Trương Đặng Minh Khuê
- MSSV: 2A202603785
- Email: minhkhai0402@gmail.com
- GitHub: https://github.com/mKhaiTruong

## 2. Phần việc phụ trách

Shape, module hoặc phần báo cáo bạn phụ trách.

- P1 (lead): workflow shape (`src/lab8/shapes/workflow.py`) + integration (review, merge PR, chạy ma trận test trên `main`).

## 3. Đóng góp cụ thể

Commit chính (hash), test đã thêm hoặc sửa, quyết định kỹ thuật bạn đưa ra.

- **CP2: shape A workflow** (`7329935`, PR #2): thay stub bằng pipeline tất định `get_claim_view` → `lookup_order` → `compute_compensation` → `issue_refund`. Tiền chỉ do code tính, không có model call.
  - Quyết định: truyền **quote đầy đủ** vào `issue_refund` để host tự trừ phần đã hoàn (T13, T14). Shape tự `denied` khi quote = 0, nên không sinh audit `policy_denied`.
  - Quyết định: mọi nhánh return đi qua `common.finish()` (dùng `functools.partial`), nên luôn có trace. Trace chỉ ghi `visible/reason` của order, không ghi row thô.
- **CP3: crash-safe** (`721bccd`, PR #5): truyền `crash_at` vào `issue_refund`. Khi `InjectedCrash`, ghi trace rồi re-raise, không nuốt lỗi, để resume dựa vào ledger idempotent.
- **CP4: crash suite + rà approval** (`2c6606a`, `4f88de1`): chạy `lab8.crash_test` ra 20/20. Thêm test cho các nhánh approval và rò rỉ trace.
- **Test** `tests/test_workflow_extra.py` (`dc2f7d1`, `f0f30d5`, `4f88de1`): early return không gọi `issue_refund`; spy kiểm quote đầy đủ (C-014: 150000 → ledger 120000); crash lan ra ngoài và có event `crash`; approval hết hạn, bị thu hồi, của claim khác, không có approval, đơn đã hoàn đủ; trace và stdout của 14 claim không chứa `forbid_substrings`.
- **Integration (lead):** review và merge PR của Khánh (#3, #4, #6, #7) và Phong (#8); phát hiện lệnh `-k single` lọc nhầm test của shape khác; hướng dẫn tạo PR đúng base repo nhóm (fork mặc định trỏ về repo trường).

## 4. Bằng chứng

Link commit, tên test, run id hoặc trích đoạn report liên quan.

- PR: #2 (workflow CP2), #5 (workflow CP3), PR CP4 `chore/cp4-crash`.
- `python -m pytest -q -m student -o addopts= -k workflow`: **62 passed** (gồm T11, T12).
- `python -m pytest -q`: **102 passed** (tại commit `4f88de1`).
- `python -m lab8.crash_test --count 20 --out reports/crash.json`: **`crash_safety 20/20`** (`src/reports/crash.json`).
- Test tiêu biểu: `test_full_quote_is_passed_to_issue_refund`, `test_crash_propagates_and_flushes_trace`, `test_trace_and_stdout_have_no_forbidden_substrings[C-005]`.

## 5. Công cụ AI đã dùng

Công cụ, dùng vào việc gì, và bạn đã tự kiểm tra kết quả thế nào (xem [RULES.md](../../RULES.md)).

...

## 6. Tự đánh giá

...
