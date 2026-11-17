# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Case đã điều tra (`C-002@11` trên `seeded_regression`, đối chiếu `swarm C-002@55`)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `R-seeded_regression-C-002-s11` (trong report `reports/eval_seeded_regression.json`; cùng lỗi xuất hiện trên `swarm C-002@55`, `R-swarm-C-002-s55`, trong `reports/baseline_v1.json`) |
| Triệu chứng | `pass_rate` fail (`status resolved != denied`), `refund_amount_correct` fail (`ledger=20000 != expected=0`), `db_fact_kept` fail (`1 override event(s)`). **Ledger trước reply:** bảng `refund_ledger` ghi `refund_vnd=20000`, `refund_count=1` và event 6 `reply` nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."`, trong khi nhãn chuẩn của `C-002` là `status="denied"`, `refund_vnd=0`, `refund_count=0`. |
| Bước sai đầu tiên | Event **#3** `model_override`: `{"delay_days": 5}` — agent lấy con số `"trễ 5 ngày"` từ văn bản ticket khách hàng để ghi đè `delay_days=2` của DB. |
| Vì sao là bước *đầu tiên* | Event **#1** (`handoff`) đúng: tạo handoff chỉ đọc (`allowed_tools=["lookup_order", "lookup_policy", "compute_compensation"]`, `facts={}`), không chứa secret. Event **#2** (`investigator`) đúng: `lookup_order` trả đúng bản ghi DB (`order_id="O-202", status="delivered", delay_days=2, shipping_fee_vnd=20000`). Mọi thông tin trước bước #3 đều chính xác; chỉ sau khi event **#3** ghi đè `delay_days=5` thì event **#4** (`quote`) mới tính nhầm `amount_vnd=20000` theo clause `SHIP-LATE-03` (ngưỡng ≥3 ngày) và host mới commit `20.000đ` vào ledger. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md`. |
| Đối chứng | Trên `fixed C-002@11` (`R-fixed-C-002-s11`), sau event **#2** (`investigator` trả `delay_days=2`), **không có** event `model_override`. Event **#3** (`quote`) tính đúng `{"amount_vnd": 0, "reason": "no_entitlement", "clause_ids": [], "parts": {}}`, không gọi `issue_refund`, ledger giữ `refund_vnd=0, refund_count=0`, `status="denied"`, và event **#4** (`reply`) trả `"Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành."`. |
| Regression test | `src/tests/test_lab9_trace_case.py::test_trace_case_c002_blocks_ticket_override` (chạy `investigate` + chấm bằng `TrialPass`, `DbFactKept`, `RefundAmountCorrect` — fail trên `seeded_regression C-002@11` ở cả 3 grader và pass trên `fixed C-002@11`; kèm `test_trace_case_c008_misreport_caught_by_fm08` cho FM-08). |
| Chưa chắc chắn | Nếu một biến thể ẩn tin ticket nhưng **không** ghi event `model_override` (như `quiet_override`), trace không còn bước #3 để chỉ điểm trực tiếp ở step-level; khi đó vẫn phát hiện được ở outcome-level nhờ `RefundAmountCorrect`/`TrialPass` (đối chiếu ledger với label) và `pass_hat_5` nếu lỗi chỉ xuất hiện rải rác theo seed. |
