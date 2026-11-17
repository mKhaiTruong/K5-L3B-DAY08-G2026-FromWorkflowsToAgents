# Báo cáo cá nhân — 2A202603749_TrieuQuocKhanh

## 1. Thông tin thành viên

- Họ tên: Triệu Quốc Khánh
- MSSV: 2A202603749
- Email: 26ai.khanhtq4@vinuni.edu.vn
- GitHub: qockhah253

## 2. Phần việc phụ trách

Vai trò P2 trong nhóm: shape B (single, ReAct) và phần nghiên cứu.

| Hạng mục                            | File                                                           |
| ----------------------------------- | -------------------------------------------------------------- |
| Shape B                             | `src/lab8/shapes/single.py`                                    |
| Test của shape B                    | `src/tests/test_single_extra.py`                               |
| Research card (câu R2) và ablation  | `report/team/research_card.md`, `src/reports/ablation_r2.json` |
| Mục 3.2 báo cáo nhóm (shape single) | `report/team/group_report.md`                                  |

## 3. Đóng góp cụ thể

Commit chính (đã vào `main` qua PR #3, #4, #6):

| Commit    | Nội dung                                                                                              |
| --------- | ----------------------------------------------------------------------------------------------------- |
| `794f84e` | `feat(single)`: shape B với `run_react`, chỉ gọi tool đọc, truyền quote đầy đủ và `crash_at` vào host |
| `732c010` | `test(single)`: 4 test (chỉ tool đọc, giới hạn 8 bước, không tin ticket, trace không có secret)       |
| `41ccea9` | `test(single)`: 7 test CP4 cho các nhánh approval và đơn đã hoàn                                      |
| `c735ba6` | `test(single)`: 4 test T11 (gọi lại cùng claim) và T12 (crash ở 3 điểm rồi resume)                    |
| `ffe7ca3` | `docs(single)`: research card R2 và kết quả ablation                                                  |

Quyết định kỹ thuật:

- `decide` không đọc ticket; số ngày trễ lấy từ order row, tiền lấy từ `compute_compensation`.
- Quote ≤ 0 thì `denied` và không gọi `issue_refund`, quote > 0 thì truyền quote đầy đủ để host tự cap theo đơn.
- `except InjectedCrash` chỉ ghi trace rồi `raise` lại, không nuốt lỗi.
- Trace chỉ ghi tên tool, `visible`, `reason`, `amount_vnd`, `clause_ids`, `status`; không ghi ticket hay order row thô.

## 4. Bằng chứng

- PR đã merge: #3 (shape B), #4 (test CP4, T11, T12), #6 (research card).
- `python -m pytest -q -m student -o addopts= -k "single and not workflow and not orchestrator and not swarm"`: 62 passed.
- `python -m pytest -q tests\test_single_extra.py`: 19 passed.
- Ablation: `python -m lab8.benchmark --shapes swarm,single --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/ablation_r2.json`. Swarm pass rate 0,986, pass^5 0,929; single 1,000 và 1,000. Trial fail duy nhất của swarm: run id `R-swarm-C-002-s55`; cùng claim và seed của single: `R-single-C-002-s55` (denied, đúng).

## 5. Công cụ AI đã dùng

| Công cụ            | Dùng vào việc                                                                                                                                                   | Cách kiểm tra kết quả                                                                                                                                                                            |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Claude (Anthropic) | Đọc tài liệu và code của repo, soạn bản nháp `single.py` và các test, tra nguồn paper MAST cho research card, soạn mô tả PR, giải thích từng bước trong lúc làm | Tự chạy `pytest`, `lab8.benchmark` và `lab8.check_submission` trên máy; đối chiếu luật với `docs/business_rules.md` và `docs/contracts.md`; mỗi thay đổi đều qua PR và có người trong nhóm duyệt |

## 6. Tự đánh giá

- Hoàn thành phần việc CP2 đến CP4 cho shape B và phần research card của CP5; các PR #3, #4, #6 đã được duyệt và merge.
- Hạn chế: `decide` hiện chỉ dùng `lookup_order` và `compute_compensation`, chưa dùng `lookup_refund_history` hay `lookup_policy` vì host đã tự cap theo đơn và `compute_compensation` đã lọc policy hiệu lực. Mới kiểm trên 14 claim public, chưa chạy bộ `student_drop/`.
