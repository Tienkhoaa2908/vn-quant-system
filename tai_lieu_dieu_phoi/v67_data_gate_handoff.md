# V67 data-gate handoff

Tài liệu này ghi trạng thái workstation đã xác minh cho lane C3/HOSE V67. Repo mới hơn và artifact workstation mới hơn luôn thắng tài liệu này.

## Artifact census đã xác minh

Runner: `scripts/run_v67_data_readiness_gitbash.sh`

Workstation HEAD khi chạy:

`17280eb0ad9773973b96f997679416b0953d1e45`

Store:

`vn_quant_local_system/data/market/dnse_ohlcv.sqlite3`

SHA256:

`2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`

Canonical Python:

`vn_quant_local_system/.venv/Scripts/python.exe`

## Coverage thực tế

- ngày đầu: `2015-06-29`;
- ngày cuối: `2026-08-13`;
- tổng bars: `300541`;
- tổng symbol: `122`;
- STOCK: `297792` bars, `121` mã;
- INDEX: `2749` bars, `1` mã (`VNINDEX`);
- source toàn bộ: `dnse_openapi`;
- source version toàn bộ: `0.5.0`.

## Blocker đã xác minh

### 1. HOSE point-in-time lineage

Market DB không có exchange/market/floor/venue hoặc bảng membership lịch sử.

Local scan trong các vùng data/validation/outputs không tìm thấy sidecar có shape đủ điều kiện `symbol + venue + effective date/interval`:

- `strict_shape_candidate_count = 0`;
- không được dùng static/current HOSE mapping áp ngược lịch sử;
- chưa được train C3 full-history cho tới khi PIT HOSE lineage được đóng.

### 2. Price basis

Toàn bộ `300541` bars có:

`price_basis = CHUA_XAC_NHAN`

Do đó không được tự coi series là adjusted hoặc raw. MA250, momentum, relative strength và 52-week-high có thể sai quanh corporate action nếu price basis chưa được xác minh.

## Hướng giải quyết hiện tại

Không tải lại 11 năm OHLCV nếu không cần. Giữ local store làm price store và bổ sung evidence/metadata lineage riêng:

1. probe metadata niêm yết công khai từ HOSE chính thức cho 121 local stocks;
2. không coi `ngày niêm yết hiệu lực` là `first HOSE trading day` cho transfer case;
3. transfer case chỉ được dùng sau khi first HOSE trading date được xác minh;
4. audit gap open so với previous close trên consecutive VNINDEX sessions để phát hiện price-reset/corporate-action-like discontinuity;
5. gap audit chỉ là diagnostic: không tự tạo adjustment factor và không tự đóng price-basis gate;
6. C3 training vẫn bị khóa cho tới khi cả HOSE PIT và price-basis gate đủ evidence.

Runner probe kế tiếp:

`scripts/run_v67_hose_official_price_probe_gitbash.sh`

Probe này research/data-readiness only, không train model, không sửa market DB và không thay champion C3.

## Invariant tiếp tục áp dụng

- champion: `C3_STABLE_3_PAST_IC_SHRUNK`;
- canonical env: `vn_quant_local_system/.venv`;
- C3 training label: benchmark-relative `close(T) -> close(T+20)`;
- tradable execution: earliest `open(T+1)`;
- August 2026 shadow-only;
- CI success không phải research result;
- artifact workstation mới hơn có quyền phủ định giả định từ CI Linux, đặc biệt với lỗi Windows/file-handle.
