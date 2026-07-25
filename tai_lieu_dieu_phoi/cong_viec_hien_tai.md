# Công việc hiện tại

Cập nhật: 2026-07-25

## Đoạn phụ trách

Đoạn `04` đã triển khai Mốc 4 bằng fixture ngoại tuyến trên PR #10; đoạn `00` tiếp tục rà soát và quyết định cửa dữ liệu thật.

## Nền bắt buộc

- Kho: `Tienkhoaa2908/vn-quant-system`.
- `main`/base: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Nhánh: `m4-dac_trung-xep_hang-hoc_may`.
- PR #10 tiếp tục Draft.
- Không force-push, không sửa trực tiếp `main`, không commit `du_lieu/`, không mở Mốc 5.

## Đã hoàn tất trên fixture

1. Khóa kiến trúc monthly sample, OOS liên tục, metric top-K và fold một lớp.
2. Khóa `scikit-learn==1.9.0` trong `pyproject.toml`/`uv.lock`.
3. Triển khai 16 module Mốc 4, không sao chép engine Mốc 3.
4. Triển khai PIT universe/coverage, feature, nhãn, walk-forward, Logistic, ranking, metric, adapter và publication.
5. Bổ sung 97 test Mốc 4 theo lỗi nghiệp vụ.
6. Compileall và toàn bộ unittest Python 3.12 đạt trên CI; 121 test hồi quy Mốc 0–3 tiếp tục đạt.

## Công việc còn lại thuộc cửa đoạn 00

- Rà soát diff, metric và sản phẩm của fixture.
- Phê duyệt hoặc yêu cầu sửa PR #10; PR chưa được chuyển Ready.
- Chỉ sau phê duyệt riêng mới xác nhận nguồn VN100/proxy, VNINDEX/lịch benchmark, cơ sở giá và corporate actions để chạy Tier A/Tier B.

## Cấm hiện hành

- Không chạy dữ liệu thật.
- Không thêm LightGBM hoặc pandas.
- Không chia vốn sản xuất.
- Không kết nối SSI, đọc tài khoản hoặc gửi lệnh.
- Không gộp PR và không mở Mốc 5.
