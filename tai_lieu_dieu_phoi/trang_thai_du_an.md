# Trạng thái dự án

Cập nhật gần nhất: 2026-07-26

## Kho mã nguồn

- Kho: `Tienkhoaa2908/vn-quant-system`.
- `main`/base Mốc 4: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh: `m4-dac_trung-xep_hang-hoc_may`.
- PR #10 tiếp tục Draft.
- Python mục tiêu 3.12; môi trường `uv`; `scikit-learn==1.9.0`.

## Mốc 0–Mốc 3

Đã đóng. 121 test ngoại tuyến và engine Mốc 3 tiếp tục là nền hồi quy bắt buộc.

## Mốc 4

Đã triển khai pipeline đầu-cuối bằng fixture ngoại tuyến:

- runner/CLI tệp cục bộ, không gọi mạng;
- PIT universe, benchmark metadata, corporate actions và event;
- feature monthly căn theo lịch benchmark chính thức, không nén thời gian;
- coverage đầy đủ theo ngày/mã/lý do/fold/nguồn;
- nhãn T+20, expanding walk-forward, Logistic Regression và momentum baseline OOS;
- target 0/ngày tái cân bằng rỗng, adapter `muc_tieu_bang_0`, backtest Mốc 3 liên tục;
- metric fail closed, NaN/Inf rejection;
- 16 sản phẩm và manifest tự tính input/product SHA-256, công bố nguyên tử.

Suite hiện có 146 test Mốc 4 + 121 test Mốc 0–3 = 267 test. Kịch bản vàng xác minh 17 tệp, fold, prediction, ranking, T+1, NAV, manifest, CLI và tái lập byte-for-byte.

## Cửa kiểm soát

- Tier A/Tier B chưa chạy.
- Chưa tải dữ liệu thật; nguồn VN100/VNINDEX/lịch/cơ sở giá/corporate actions thật chưa được đoạn 00 phê duyệt.
- Không tuyên bố hiệu quả chiến lược từ fixture.
- Không LightGBM, SSI, đọc tài khoản hoặc gửi lệnh.
- Không Ready, không merge và không mở Mốc 5.
