# Judge audit

Chạy:
```bash
cd src
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 10
```

| Tiêu chí | n | κ | Precision | Recall | Ma trận nhầm lẫn (FAIL = pos) | Fail rate (obs → Rogan-Gladen) | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---:|---:|---:|---:|---|---:|---|---|
| `tone_ok` (`judge_tone_public.csv`) | 100 | 0.757 | 0.857 | 0.800 | `tp=24, fp=4, fn=6, tn=66` | `0.280 → 0.300` | **PASS** (0.757 ≥ 0.6; 0.857 ≥ 0.8; 0.800 ≥ 0.7) | **dùng** (làm tín hiệu giám sát/phụ trợ sau khi chỉnh rubric) |
| `helpful` (`judge_helpful_public.csv`) | 100 | 0.375 | 1.000 | 0.300 | `tp=9, fp=0, fn=21, tn=70` | `0.090 → 0.300` | **FAIL** (κ=0.375 < 0.6; R=0.300 < 0.7) | **loại** — tuyệt đối không dùng làm gate |

## ≥5 case audit thủ công

### A. Audit `judge_tone_public.csv` (10 bất đồng; lấy 8 ca tiêu biểu + phân loại sửa rubric)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008`: *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* | PASS | FAIL | **Người đúng** | Xưng `"em"` + `"nha"` quá suồng sã; judge bị đánh lừa bởi giọng thân thiện. **Sửa rubric:** cấm đại từ thân mật (`em`, `nha`, `nhé`), bắt buộc chuẩn xưng hô `LogiX` — `anh/chị`. |
| 2 | `H-017`: *"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."* | PASS | FAIL | **Người đúng** | Dù có `"Dạ"` nhưng xưng `"bạn ơi"` + `"nha"` không phù hợp khách hàng CSKH. **Sửa rubric:** tách kiểm tra từ mở đầu (`Dạ`) khỏi đại từ nhân xưng (`bạn` → FAIL). |
| 3 | `H-029`: *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* | PASS | FAIL | **Người đúng** | Mệnh đề cuối mang giọng ra lệnh/đuổi khéo (`không cần nhắn thêm`), judge chỉ nhìn phần đầu `"Dạ, vui lòng"`. **Sửa rubric:** đánh giá toàn bộ câu, câu mệnh lệnh/từ chối giao tiếp ở vế sau là FAIL. |
| 4 | `H-042`: *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* | FAIL | PASS | **Người đúng** | Câu ngắn gọn, lịch sự, đủ thông tin; judge phạt nhầm vì `"thiếu xin lỗi"`. **Sửa rubric:** ghi rõ phản hồi xác nhận hoàn tiền thành công **không** bắt buộc câu xin lỗi. |
| 5 | `H-051`: *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* | FAIL | PASS | **Người đúng** | Thuật ngữ `"refund"` nằm trong danh sách cho phép của CS LogiX; judge phạt cứng nhắc vì xen tiếng Anh. **Sửa rubric:** thêm allowlist từ chuyên môn CS được chấp nhận (`refund`, `order`). |
| 6 | `H-063`: *"Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ."* | PASS | FAIL | **Người đúng** | Hứa hẹn `"sẽ hoàn thêm"` sai sự thật/ngoài kết quả hệ thống. **Sửa rubric:** gắn cờ FAIL mọi lời hứa bồi thường bổ sung không có trong kết quả xác nhận. |
| 7 | `H-070`: *"Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂"* | PASS | FAIL | **Người đúng** | Dùng emoji cười cợt (`😂😂`) trong ngữ cảnh khiếu nại. **Sửa rubric:** cấm tuyệt đối emoji/icon trong phản hồi hoàn tiền và từ chối. |
| 8 | `H-081`: *"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."* | FAIL | PASS | **Judge đúng** | Ghi chú CSV xác nhận nhãn người bị gán nhầm do đọc nhầm ticket. **Hành động:** giữ rubric, sửa lại nhãn golden set của `H-081` (và kiểm tra chéo các mẫu sát biên). |
| 9 | `H-088`: *"Dạ, dạ, LogiX đã hoàn 40.000đ cho đơn O-233 ạ."* | FAIL | PASS | **Người đúng** | Lặp từ `"Dạ, dạ"` do typo nhẹ không gây phản cảm; judge quá khắt khe. **Sửa rubric:** phân biệt lỗi đánh máy nhẹ với lỗi thiếu tôn trọng. |
| 10 | `H-094`: *"Da, LogiX da hoan 40.000đ cho don O-341, xin loi vi su bat tien."* | PASS | FAIL | **Người đúng** | Mất dấu tiếng Việt kiểu dịch máy; judge bỏ qua lỗi chính tả/dấu thanh. **Sửa rubric:** bắt buộc phản hồi tiếng Việt có dấu đầy đủ, đúng chuẩn chính tả. |

### B. Audit `judge_helpful_public.csv` (mẫu bất đồng tiêu biểu)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | `HL-015`: *"Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ."* | PASS | FAIL | **Người đúng** | `sai tiền`: ledger ghi `40.000đ` nhưng reply báo `55.000đ` (FM-08). Judge không đọc ledger nên bỏ sót. |
| 2 | `HL-016`: *"Dạ, LogiX thành thật xin lỗi anh/chị... LogiX đã hoàn 55.000đ cho đơn O-404..."* | PASS | FAIL | **Người đúng** | `sai tiền`: ledger ghi `35.000đ`. Câu dài, xin lỗi nhiều khiến judge chấm PASS dù số tiền sai. |
| 3 | `HL-020`: *"Dạ, LogiX đã hoàn 90.000đ cho đơn O-303 ạ."* | PASS | FAIL | **Người đúng** | `sai tiền`: ledger ghi `120.000đ`. Judge chỉ đánh giá độ trôi chảy văn bản. |
| 4 | `HL-047`: *"Ok bạn, đơn O-515 xử lý rồi nhé."* | PASS | FAIL | **Người đúng** | `sai xưng hô`: văn phong cộc lốc/suồng sã (`Ok bạn`, `nhé`), thiếu thông tin số tiền nhưng judge vẫn cho PASS. |
| 5 | `HL-053`: *"Dạ, LogiX rất tiếc vì đơn hàng đã đến trễ... LogiX đã hoàn 110.000đ cho đơn O-562..."* | PASS | FAIL | **Người đúng** | `sai tiền`: ledger ghi `90.000đ`. Judge bị đánh lừa bởi mẫu câu xin lỗi lịch sự (verbosity bias). |

## Kết luận
- **Tiêu chí bị loại (`judge_helpful`):** đạt Precision = `1.000` nhưng Recall chỉ đạt **`0.300`** (`tp=9, fn=21`, bỏ sót **21/30 = 70%** lỗi thực tế!) và Cohen's κ = **`0.375`** (< sàn `0.6`). Hiệu chỉnh Rogan-Gladen cho thấy tỉ lệ lỗi thật là `0.300` dù judge chỉ quan sát thấy `0.090` — tức judge làm ẩn hơn hai phần ba số lỗi. Nguyên nhân chính từ audit:
  1. Judge không có quyền đối chiếu `refund_ledger` nên bỏ sót toàn bộ **18 ca sai tiền (FM-08)** (`HL-015`, `HL-016`, `HL-020`, `HL-028`, ...), lại bị thiên kiến văn dài/xin lỗi nhiều (verbosity/sycophancy bias).
  2. Bỏ sót **3 ca sai xưng hô** (`HL-047`, `HL-091`, `HL-097`).
  → **Quyết định:** Không dùng `judge_helpful` làm gate. Toàn bộ kiểm tra số tiền và tính nhất quán giữa `reply` với ledger chuyển sang **code grader tất định** (`RefundAmountCorrect` và `ReplyMatchesLedger` ở M3).
- **Tiêu chí đạt sàn (`judge_tone`):** κ = `0.757`, P = `0.857`, R = `0.800` (đều đạt FLOORS), Rogan-Gladen hiệu chỉnh `0.280 → 0.300`. Có thể dùng sau khi cập nhật rubric theo 10 ca audit ở trên.
- **Rủi ro còn lại:** cả hai judge đều chỉ được hiệu chuẩn trên dữ liệu replay đã công khai (`n=100`); cần thu thập nhãn người mới trên tập held-out thật và chạy lại calibration sau khi sửa rubric (và sửa nhãn lỗi `H-081`).
