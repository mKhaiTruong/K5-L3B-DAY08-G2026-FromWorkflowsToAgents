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
- **CP5: benchmark + ADR + báo cáo nhóm** (`6f4f763`, `879fdf8`, `22116dc`): chạy benchmark 4 shape × 14 claim × 5 seed; chọn **workflow** trong `decision_adr.md` (pass = pass^5 = 1.000 như single và orchestrator, nhưng cost/success thấp nhất 27.86 VND và 0 model call); viết `group_report.md` mục 1, 2, 3.1, 4, 5.
  - Quyết định: khi 3 shape hòa về độ đúng thì chọn theo cost và bề mặt tấn công. Workflow không đọc ticket để lấy số, nên ticket nói dối hay injection (đúng lỗi của `R-swarm-C-002-s55`) không tác động được.
- **Test** `tests/test_workflow_extra.py` (`dc2f7d1`, `f0f30d5`, `4f88de1`): early return không gọi `issue_refund`; spy kiểm quote đầy đủ (C-014: 150000 → ledger 120000); crash lan ra ngoài và có event `crash`; approval hết hạn, bị thu hồi, của claim khác, không có approval, đơn đã hoàn đủ; trace và stdout của 14 claim không chứa `forbid_substrings`.
- **Integration (lead):** review và merge PR của Khánh (#3, #4, #6, #7) và Phong (#8); phát hiện lệnh `-k single` lọc nhầm test của shape khác; hướng dẫn tạo PR đúng base repo nhóm (fork mặc định trỏ về repo trường).

## 4. Bằng chứng

Link commit, tên test, run id hoặc trích đoạn report liên quan.

- PR: #2 (workflow CP2), #5 (workflow CP3), #9 (CP4 `chore/cp4-crash`), PR CP5 `chore/cp5-benchmark`.
- `python -m pytest -q -m student -o addopts= -k workflow`: **62 passed** (gồm T11, T12).
- `python -m pytest -q`: **102 passed** (tại commit `4f88de1`).
- `python -m lab8.crash_test --count 20 --out reports/crash.json`: **`crash_safety 20/20`** (`src/reports/crash.json`).
- `python -m pytest -q -m student -o addopts=` (4 shape): **248 passed**.
- `python -m lab8.benchmark --shapes workflow,single,orchestrator,swarm --seeds 11,22,33,44,55 --out reports/benchmark.json` tại commit `6f4f763`: workflow pass 1.000, pass^5 1.000, variance 0, cost/success 27.86 VND. Run id dẫn chứng `R-workflow-C-001-s11`.
- `python -m lab8.check_submission`: **0 FAIL** sau khi điền ADR.
- Test tiêu biểu: `test_full_quote_is_passed_to_issue_refund`, `test_crash_propagates_and_flushes_trace`, `test_trace_and_stdout_have_no_forbidden_substrings[C-005]`.

## 5. Công cụ AI đã dùng

Công cụ, dùng vào việc gì, và bạn đã tự kiểm tra kết quả thế nào (xem [RULES.md](../../RULES.md)).

- **Claude Code (CLI agent):**
  - Dùng vào việc: đọc và giải thích `swarm_reference.py`, `durability.issue_refund`, `common.finish()`; gợi ý code `workflow.py` (CP2, CP3); viết `tests/test_workflow_extra.py`; chạy pytest, crash suite, benchmark, `check_submission`; soạn mô tả PR; review PR của teammate (chạy test của branch trong worktree tạm); nháp ADR và các mục báo cáo nhóm của P1.
  - Cách tự kiểm tra:
    - Code `workflow.py` ở CP2 do mình tự paste và đọc từng nhánh, đối chiếu với 8 bước trong docstring đầu file.
    - Mọi số liệu trong ADR và báo cáo đều lấy từ `src/reports/benchmark.json` và `crash.json` do lệnh thật sinh ra, không chép tay. Mình đối chiếu lại các tỉ lệ cost (rẻ hơn single 6%, rẻ hơn orchestrator 40%).
    - Test mới phải xanh trên cả `pytest -q` lẫn ma trận student, rồi mới commit.
    - Ở CP2 mình chủ động **không** cho AI làm luôn phần `crash_at` của CP3 (để T12 đỏ có chủ đích), để giữ đúng ranh giới checkpoint.
  - Chỗ AI sai hoặc thiếu, mình phát hiện được: lệnh `-k single` của đề lọc nhầm test của shape khác. Cảnh báo "TEAM.md dễ conflict" cũng không đúng, vì nhóm đã thống nhất chỉ lead sửa file này.

## 6. Tự đánh giá

**Làm tốt:**
- Vai lead: lần đầu dùng PR chuẩn chỉnh, cảm giác rất tốt, hiểu cách merge branch rõ ràng hơn. Teammate giao tiếp cũng tốt. Tự đánh giá cao, mọi việc trơn tru.
- Ranh giới checkpoint: nói thật là mình không biết chắc, vì mình không phải chuyên gia. Nhưng với nhiều test case để kiểm tra như vậy, với mình làm vậy luôn là đúng đắn.
- Hiểu bộ test 62/62 và crash 20/20 là để kiểm tra code có đúng nghiệp vụ và chịu được crash hay không.

**Chưa tốt / cần cải thiện:**
- PR #1 (chia việc CP1) mình để mở cho teammate đọc. Sau mới hiểu PR kiểu chia việc có thể merge ngay, để `main` luôn có thông tin mới nhất.
- Lúc đầu nhờ AI giải thích, nó dùng nhiều từ nghiệp vụ bằng tiếng Anh rất khó hiểu. Mình phải nhờ nó liệt kê keywords và giải thích từng cái, sau đó đề bài sáng hơn hẳn.

**Học được:**
- Testing: cách người ta làm việc thực tế.
- Git và GitHub.
- Hiểu tại sao trong bài này, 1 agent hoặc workflow đơn giản lại tốt hơn multi-agent (MAS): đúng ngang nhau nhưng rẻ hơn và ổn định hơn.
