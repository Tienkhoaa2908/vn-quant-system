# Anti-regression bổ sung — V67 data gate và workstation runner

Tài liệu này bổ sung cho `anti_regression_c3_hose.md` và phải được đọc cùng tài liệu đó khi khôi phục chat hoặc sửa V67+.

## 1. DB OHLCV dài không đồng nghĩa có point-in-time HOSE universe

Failure bundle V67 trên workstation xác nhận `dnse_ohlcv.sqlite3` có bảng OHLCV nhưng schema tại thời điểm audit không có `exchange/venue/floor/market` hay bảng membership lịch sử.

Quy tắc:

- Không suy ra HOSE chỉ từ việc mã có OHLCV.
- Không lấy danh sách HOSE hiện tại áp ngược lịch sử.
- Không coi `listing_date + current_exchange` là interval history.
- Trước khi C3 full-HOSE chạy, phải census toàn bộ kho local để tìm sidecar PIT lineage; nếu không có thì data gate vẫn blocked.

## 2. Price basis phải audit trước khi dùng 11 năm để train

Schema `bars` có cột `price_basis`, nhưng chỉ có schema không đủ chứng minh adjusted/raw status.

Quy tắc:

- Census distribution của `price_basis`, `source`, `source_version` và date coverage trước model run.
- Không mặc định dữ liệu DNSE là adjusted hay raw nếu artifact chưa chứng minh.
- Nếu raw/unadjusted và corporate-action lineage chưa đủ, phải coi đây là blocker/risk lớn cho MA250, high-52-week và momentum quanh split/quyền.

## 3. `sqlite3.Connection` context manager không đóng connection

Trên Python/Windows, `with sqlite3.connect(path) as db:` quản lý transaction nhưng không đảm bảo đóng handle khi thoát block. Synthetic V67 test từng PASS trên Linux CI nhưng ERROR khi TemporaryDirectory cleanup trên Windows vì `market.sqlite3` vẫn bị lock.

Quy tắc:

- Test/file tạm trên Windows phải dùng `contextlib.closing(sqlite3.connect(...))` hoặc `db.close()` rõ ràng trước cleanup.
- Cross-platform test phải bao phủ file-lock semantics khi dùng SQLite temp files.

## 4. `tee` có thể che test failure nếu runner tắt errexit sai cách

Runner cũ dùng `set +e; run_all | tee ...` rồi lấy `PIPESTATUS`. Vì `run_all` chạy khi errexit đã tắt, một test có thể fail nhưng command nghiên cứu sau vẫn chạy; nếu command cuối success thì cả run có thể bị báo success sai.

Quy tắc:

- Pipeline được log qua `tee` phải chạy trong subshell/function có `set -euo pipefail` riêng.
- Outer shell chỉ được tắt errexit để thu `PIPESTATUS`, không được làm mất fail-fast bên trong work package.
- CI phải grep/validate contract fail-fast của runner.

## 5. Data-readiness census đứng trước model sophistication

Từ V67 repair, failure bundle phải chứa tối thiểu:

- schema DB;
- min/max day;
- row/symbol coverage;
- asset-type distribution;
- `price_basis` distribution;
- source/source_version distribution;
- metadata keys/values đã redact secret;
- inventory các local file/DB có shape khả dĩ cho PIT exchange lineage.

Chỉ sau khi các gate dữ liệu này đủ mới tiếp tục C3 full-HOSE hoặc challenger ML.
