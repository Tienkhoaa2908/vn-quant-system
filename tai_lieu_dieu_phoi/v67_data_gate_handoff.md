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

## Artifact official-HOSE + price-gap probe đã xác minh

Runner: `scripts/run_v67_hose_official_price_probe_gitbash.sh`

Workstation HEAD:

`83707806ad01f7aa653a03ec12cab66333bca730`

Kết quả network:

- official HOSE request không parse được JSON;
- `network_error = JSONDecodeError: Expecting value: line 1 column 1`;
- `parsed_row_count = 0`;
- vì vậy `matched_current_hsx_count = 0` và `unmatched_current_hsx_count = 121` KHÔNG phải bằng chứng 121 mã không ở HOSE; đó chỉ là collector failure;
- HOSE PIT gate vẫn mở.

Kết quả local price-gap audit trên consecutive VNINDEX sessions:

- gap tuyệt đối `>=18%`: `40` events;
- `>=25%`: `5` events;
- `>=40%`: `2` events;
- `10` symbols có ít nhất một event `>=18%`;
- VIX chiếm `23` events, HHV `5`, GEE `4`;
- hai event lớn nhất trong artifact là VHM `2026-07-22` khoảng `-50.07%` và HHV `2016-11-28` khoảng `+40.09%`.

Đặc biệt VHM có local `2026-07-21 close=136.40` và `2026-07-22 open=68.10`. Đây là bằng chứng đủ mạnh để mở audit provenance/basis riêng, nhưng CHƯA được tự kết luận raw/adjusted hay tự tạo adjustment factor chỉ từ gap.

## Hướng giải quyết hiện tại

Không tải lại 11 năm OHLCV trước khi hiểu provenance đang có.

Thứ tự hiện tại:

1. chạy `scripts/run_v67_market_store_basis_audit_gitbash.sh`;
2. map toàn bộ gap lớn với `fetched_at` trước/sau;
3. map overlap với `market_source_revisions_v49` và `conflicts`;
4. đọc `fetched_ranges` và `market_sync_runs_v49` để tìm seam giữa batch;
5. nếu mixed-basis seam được xác minh thì phải rebuild/normalize history trên một basis duy nhất trước C3;
6. song song sửa HOSE official collector để lấy được current listing metadata, rồi bổ sung transfer/delist history cho PIT sidecar;
7. chỉ khi price-basis gate và HOSE PIT gate cùng đóng mới cho full-history C3 chạy.

Gap audit và basis-seam audit là diagnostic, không tự authorize model training.

## Invariant tiếp tục áp dụng

- champion: `C3_STABLE_3_PAST_IC_SHRUNK`;
- canonical env: `vn_quant_local_system/.venv`;
- C3 training label: benchmark-relative `close(T) -> close(T+20)`;
- tradable execution: earliest `open(T+1)`;
- August 2026 shadow-only;
- CI success không phải research result;
- artifact workstation mới hơn có quyền phủ định giả định từ CI Linux, đặc biệt với lỗi Windows/file-handle;
- collector/network failure không được diễn giải thành market-membership fact;
- price gap không được tự diễn giải thành corporate action factor nếu chưa có provenance/evidence tương ứng.
