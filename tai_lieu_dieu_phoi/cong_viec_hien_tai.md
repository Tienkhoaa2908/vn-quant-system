# Công việc hiện tại

Cập nhật: 2026-07-25

## Đoạn phụ trách

Đoạn `00 Điều phối trung tâm` phụ trách soạn và điều phối phê duyệt đặc tả Mốc 4.

## Nền bắt buộc

- Kho: `Tienkhoaa2908/vn-quant-system`.
- `main`: `bb25ff16761b7c79e701fbd4f3a5af02f1644e07`.
- Nhánh điều phối: `dac_ta-moc-4`.
- Phạm vi nhánh: chỉ tài liệu đặc tả và điều phối.
- Không force-push.
- Không sửa trực tiếp `main`.
- Không commit tệp dưới `du_lieu/`.
- Không triển khai mã Mốc 4 trên nhánh này.

## Mốc 3 đã đóng hoàn toàn

- PR số 7 và PR số 8 đã gộp bằng merge commit.
- CI cuối trên `main`: run `#185`, Run ID `30151712433`, Job ID `89663090052`, `completed/success`.
- Engine và 121 kiểm thử đã được nghiệm thu.
- Xác minh ba mã chỉ chứng minh kỹ thuật, không chứng minh hiệu quả đầu tư.

## Công việc của PR đặc tả

1. Thêm `tai_lieu/dac_ta_moc_4.md`.
2. Chốt universe point-in-time và phương án proxy.
3. Chốt dữ liệu nhiều năm, warm-up và coverage.
4. Chốt feature, nhãn, walk-forward và Logistic Regression.
5. Chốt ranking, backtest ngoài mẫu, sản phẩm và kiểm thử.
6. Cập nhật ba tài liệu điều phối và kế hoạch tổng thể.
7. Mở PR Draft.
8. Xác minh CI.
9. Chờ người dùng phê duyệt các quyết định.
10. Chỉ gộp bằng lệnh riêng.

## Cửa kiểm soát

- Mốc 4 chưa được mở triển khai.
- Không tạo nhánh chuyên môn trước khi đặc tả được phê duyệt và gộp.
- LightGBM không nằm trong lần triển khai đầu tiên.
- Mốc 5 chưa mở.
