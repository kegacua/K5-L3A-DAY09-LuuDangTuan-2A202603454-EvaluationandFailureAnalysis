# Bonus Lab 9 — Port graders sang Inspect AI và so khớp với pydantic-evals

- **Mục tiêu (`RUBRIC.md` / `README.md`):** port ≥ 3 grader từ `pydantic-evals` ([src/lab9/graders.py](file:///d:/tuan-D/Document-D/AI_thuc_chien/K5-L3A-Day8-Tourist-From-Workflows-to-Agents/src/lab9/graders.py)) sang **UK AISI Inspect AI** (`inspect-ai==0.3.290`) và đối chiếu kết quả trên cùng dữ liệu, cùng seed, không dùng API key.
- **Triển khai:**
  - Module Inspect AI: `src/lab9/bonus_inspect.py` (port **4** grader thành Inspect AI `@scorer`: `approval_bypass`, `refund_amount_correct`, `db_fact_kept`, `reply_matches_ledger` kèm `@solver` chạy offline qua `inspect_ai.eval(..., model="mockllm/model")`).
  - Test đối chiếu: `src/tests/test_lab9_bonus_inspect.py` (dùng `pytest.importorskip("inspect_ai")` nên CI chuẩn không cài `inspect-ai` vẫn xanh; khi chạy trong `.venv` có `inspect-ai`, kiểm chứng khớp từng vector và khớp báo cáo so sánh).
  - Báo cáo do script sinh ra: `src/reports/bonus_inspect_compare.json`.

## Lệnh tái lập (từ `src/`)

```bash
python -m lab9.bonus_inspect --out reports/bonus_inspect_compare.json
python -m pytest -q -m student -o addopts= -k bonus_inspect
```

## Kết quả đối chiếu (`reports/bonus_inspect_compare.json`)

Chạy trên `eval_set_v1.jsonl` (`dd1e943040e1`, 14 item × 5 seed = 70 trial mỗi shape) × 4 shape (`swarm`, `fixed`, `seeded_regression`, `misreport_demo`) × 4 metric = **1.120 cặp so sánh `(shape, item_id, seed, metric)`**.

- **Độ khớp từng cặp trial-metric (`agreement_rate`):** **`100.00%`** (`disagreements_count = 0`).

| Shape | Trials | `approval_bypass` (PE / Inspect) | `refund_amount_correct` (PE / Inspect) | `db_fact_kept` (PE / Inspect) | `reply_matches_ledger` (PE / Inspect) | Sai khác |
|---|---:|---:|---:|---:|---:|---:|
| `swarm` | 70 | `0 / 0` | `0.9857 / 0.9857` | `0.9857 / 0.9857` | `1.0 / 1.0` | `0` |
| `fixed` | 70 | `0 / 0` | `1.0 / 1.0` | `1.0 / 1.0` | `1.0 / 1.0` | `0` |
| `seeded_regression` | 70 | `0 / 0` | `0.8571 / 0.8571` | `0.9286 / 0.9286` | `0.7857 / 0.7857` | `0` |
| `misreport_demo` | 70 | `0 / 0` | `1.0 / 1.0` | `1.0 / 1.0` | `0.8571 / 0.8571` | `0` |

## Nhận xét kỹ thuật khi port
- **Khác biệt mô hình dữ liệu:** `pydantic-evals` truyền `EvaluatorContext(output=trial, expected_output=label)` trực tiếp trong bộ nhớ; Inspect AI tách quy trình thành `Dataset(Sample(target=...))` → `@solver` ghi kết quả trung gian vào `TaskState.metadata["trial"]` → `@scorer` đọc `(TaskState, Target)` trả `Score(value=1|0, explanation=...)` và ghi log nén `.eval`.
- **Điểm cần lưu ý với `inspect-ai 0.3.290`:** `EvalLog.samples` lazy-load từ file `.eval` trên đĩa nên phải đọc kết quả trước khi xóa thư mục `log_dir` tạm.
- **Lợi ích đối chiếu đa framework:** trên `misreport_demo` (chỉ bật FM-08 `misreport`), cả `pydantic-evals` và Inspect AI đều giữ `refund_amount_correct = 1.0` nhưng phát hiện đúng `reply_matches_ledger = 0.8571` (bắt 10/70 trial của `C-008` và `C-014` có `reply` nói sai số tiền so với ledger).
