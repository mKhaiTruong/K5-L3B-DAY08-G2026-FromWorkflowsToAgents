# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash: 6f4f763
- Run id dẫn chứng: R-workflow-C-001-s11 (benchmark: 70 trial `R-workflow-<claim>-s<seed>` trong src/reports/benchmark.json; miss đối chứng của swarm: R-swarm-C-002-s55)
- Pass rate / pass^5 / seed min-max / variance: 1.000 / 1.000 / 1.000–1.000 / 0.000000 (70/70 trial, 14 claim × seed 11,22,33,44,55)
- Cost per success (mô phỏng, VND): 27.86 (thấp nhất trong 4 shape; 0 model call, 2.79 tool call/trial)
- Crash safety: 20/20 (src/reports/crash.json); T11, T12 xanh trên workflow
- Secret leak / approval bypass: 0 / 0 (trace + stdout của 14 claim không chứa forbid_substrings; 5 nhánh approval hỏng đều denied, không ghi ledger — tests/test_workflow_extra.py)

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Viết 1 đoạn. So cùng corpus và cùng seed, không so với một lần chạy lẻ.

Cùng 14 claim public, cùng 5 seed (11, 22, 33, 44, 55), cùng bảng giá mô phỏng, mỗi trial một SQLite mới (`src/reports/benchmark.json`):

| Shape | Pass | pass^5 | Variance | Seed min–max | Cost/success (VND) | Mean / p95 steps | Model call / trial |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **workflow** | **1.000** | **1.000** | **0.000000** | 1.000–1.000 | **27.86** | 4.43 / 5 | **0.00** |
| single | 1.000 | 1.000 | 0.000000 | 1.000–1.000 | 29.74 | 4.64 / 5 | 3.79 |
| orchestrator | 1.000 | 1.000 | 0.000000 | 1.000–1.000 | 46.43 | 4.71 / 5 | 0.00 |
| swarm | 0.986 | 0.929 | 0.000816 | 0.929–1.000 | 49.57 | 2.80 / 3 | 3.00 |

Ba shape nhóm viết hòa nhau về độ đúng (pass = pass^5 = 1.000, variance 0), nên quyết định dựa vào cost và rủi ro. Workflow rẻ nhất (27.86 VND/success, rẻ hơn single 6%, rẻ hơn orchestrator 40%) và **không có model call nào**: số tiền do `compute_compensation` tính từ order row, ticket không bao giờ được parse lấy số. Vì vậy các kiểu tấn công của bộ hidden như ticket nói dối, injection hay homoglyph không có chỗ để tác động vào quyết định. Đây đúng là chỗ swarm trượt: ở `R-swarm-C-002-s55`, swarm tin con số "trễ 5 ngày" trong ticket thay vì 2 ngày trong DB, nên trả 20000 cho một claim lẽ ra bị `denied`.

## Có đáng đổi lấy multi-agent không

Nếu pass nhỉnh hơn mà cost và variance cao hơn, nhóm giữ hay đổi? Điều kiện nào làm quyết định đảo lại?

Trên bộ public thì **không đáng**: multi-agent (orchestrator, swarm) tốn thêm 67–78% cost/success mà không tăng pass. Swarm còn sinh variance (seed min 0.929) và một refund sai tiền. Nếu một shape multi-agent pass nhỉnh hơn nhưng cost và variance cao hơn, nhóm **vẫn giữ workflow**, trừ khi phần pass tăng thêm nằm ở các case must-pass (approval, secret, crash), vì sai ở đó không bù được bằng điểm khác.

Quyết định đảo lại khi:
- claim cần **hiểu ngôn ngữ tự do** mà rule không bao được (vd khách mô tả hư hỏng bằng lời, không có field `damage_verified`). Khi đó single hoặc orchestrator có lợi thế, với điều kiện model chỉ đọc và đề xuất, còn host vẫn giữ quyền ghi tiền.
- bộ hidden cho thấy workflow fail một nhóm case có cấu trúc mà rule cứng không phủ, trong khi orchestrator (investigator đọc qua handoff allowlist) pass ổn định trên cả 5 seed.
- giá model thật đủ rẻ để chênh lệch cost/success không còn đáng kể so với lợi ích về độ phủ.

## Trace và bằng chứng

Trace của nhóm ghi những event nào? Field nào cố ý **không** ghi, và vì sao? Nếu trace nằm ngoài chỗ scanner quét được, đội security chứng minh thế nào là hệ thống không lộ secret?

Mỗi trial ghi `traces/<run_id>.json` dạng `{run_id, steps, events}`. `run_id` do `make_run_id(shape, claim_id, seed)` sinh, nên không lẫn với trace của lần chạy trước. Mọi nhánh return, kể cả `needs_info` và `escalated`, đều đi qua `finish()`, nên trace luôn tồn tại.

**Event theo shape** (đối chiếu với trace thật trong `src/traces/`):
- workflow: `claim`, `lookup_order`, `quote`, `issue_refund`, `decision`, `crash`
- single: `action`, `observation`, `decision`, `result`, `error`, `crash`
- orchestrator: `shape`, `handoff`, `investigator`, `quote`, `decision`
- swarm (đối chứng): `handoff`, `investigator`, `model_override`, `quote`, `decision`

Với workflow (shape chọn), payload chỉ gồm: `has_order_id`; `visible`/`reason` của order; `amount_vnd`/`reason`/`clause_ids` của quote; `ok`/`reason`/`conflict` của host; `status`.

**Cố ý KHÔNG ghi:**
- nội dung ticket, vì có thể chứa injection hoặc PII do khách tự gõ
- claim row: `parent_secret`, `raw_headers` (bearer token)
- order row thô: SĐT, địa chỉ, ghi chú nội bộ, tên hàng

Lý do: trace là **ranh giới bảo mật**, không phải log debug. Thứ gì đã ghi vào trace là coi như đã lộ, và tóm tắt bằng LLM không được tính là redaction.

**Dữ liệu chỉ vào shape qua 2 cửa có allowlist:** `get_claim_view` / `lookup_order` (lọc field theo `ORDER_FIELDS`), và `make_handoff` / `sanitize`. Cửa thứ hai ném `HandoffError` nếu handoff còn chứa `CANARY_SECRET_`, `parent_secret`, `raw_headers`, hoặc cấp tool ghi.

**Bằng chứng:**
- Quét 287 file trong `src/traces/` (ma trận student 4 shape, benchmark, test bổ sung), tìm `CANARY_SECRET_`, `parent_secret`, `raw_headers`, `Bearer`, SĐT `0901…`, địa chỉ, `CANARY_INTERNAL`, `SECRET_ITEM`: **0 file vi phạm**.
- Test `test_trace_and_stdout_have_no_forbidden_substrings` (workflow, 14 claim) và `test_orchestrator_handoff.py` (handoff ⊆ `ALLOWED_FIELDS`, `facts == {}`) giữ kết quả này trên mọi lần chạy.

**Nếu trace nằm ngoài chỗ scanner quét được:** chứng minh bằng **cấu trúc**, không dựa vào việc quét. Shape không bao giờ đọc các cột secret, vì view chỉ SELECT 4 cột và order đi qua allowlist. Handoff thì bị `sanitize` chặn trước khi tới investigator. Thứ không vào bộ nhớ của shape thì không thể lọt ra trace hay stdout.

## Giới hạn

MockLLM không phải model sản xuất. Latency để `unavailable`. Không sửa JSON cho đủ 0.75.

- Cost là VND mô phỏng (`tool_call_vnd = 10`, token theo bảng giá giả), không phải hóa đơn API thật.
- Pass rate chỉ đo trên bộ public (14 claim). Tự kiểm trên `student_drop/` (40 claim × 5 seed, không nhãn, `src/reports/hidden_selfcheck.json`): workflow chạy 200/200 trial, 0 `error`, 0 `leak_suspect`, status trùng single và orchestrator trên mọi cặp (claim, seed). Đó là bằng chứng ổn định và an toàn, không phải bằng chứng đúng. Điểm hidden do grader của giảng viên chấm.
- Workflow chỉ đúng trong phạm vi rule mà `compute_compensation` mã hóa. Gặp case ngoài rule thì nó trả `escalated` hoặc `denied` chứ không tự suy luận.
