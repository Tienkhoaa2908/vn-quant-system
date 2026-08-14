# V68 consolidated C3/HOSE research

Mục tiêu V68 là giảm số vòng workstation. Một lần chạy phải gom các lane độc lập thay vì dừng toàn bộ package ở blocker dữ liệu đầu tiên.

## Champion và môi trường

- Champion: `C3_STABLE_3_PAST_IC_SHRUNK`.
- Canonical workstation env: `vn_quant_local_system/.venv`.
- Không chạy Logistic/HGB/LightGBM trong V68.
- C3 training label vẫn là benchmark-relative `close(T) -> close(T+20)`.
- Tradable outcome vẫn bắt đầu sớm nhất `open(T+1)`.

## Một lần chạy V68 làm gì

1. Census local store và local sidecar candidates.
2. Basis/provenance audit: gap, fetched timestamp, revision, conflict, fetched range, sync-run.
3. Best-effort HOSE public metadata probe; network failure không dừng pipeline và không được diễn giải thành membership fact.
4. Dựng temporary diagnostic stores, không sửa canonical SQLite.
5. Chạy C3 native trên các sensitivity universe:
   - `BROAD_PROVISIONAL`: toàn bộ local STOCK symbols;
   - `SEAM_CLEAN`: loại symbol có mixed-basis seam candidate;
   - `GAP18_CLEAN`: loại symbol có bất kỳ consecutive-session gap >=18%;
   - `STRICT_PIT_PRICE_CLEAN`: chỉ chạy nếu lineage probe có ít nhất 10 symbol PIT-accepted và không có gap >=18%.
6. Với từng variant: monthly C3 baseline, C3 weight history, weekly preview, 36 protection/opportunity cohorts và August shadow.
7. Cluster bootstrap theo tuần cho từng cohort/horizon; BH-FDR trong từng kind+horizon.
8. Year/era stability.
9. So top10 ranking giữa các universe bằng Jaccard và exact-set rate.
10. Xuất một consolidated report và một bundle duy nhất.

## Cách diễn giải

V68 chủ động cho phép diagnostic C3 chạy trước khi hai data gate đóng, nhưng không hạ chuẩn:

- provisional universe không được gọi là point-in-time HOSE master panel;
- loại gap symbol chỉ là sensitivity test, không phải corporate-action adjustment;
- `canonical_research_claim_authorized=false` cho tới khi cả price basis và PIT HOSE lineage đủ evidence;
- `promotion_authorized=false` cố định trong V68;
- August 2026 vẫn shadow-only;
- không có broker/order/live action.

Mục đích của ba/four sensitivity universe là đo xem C3, protection và opportunity có đổi kết luận mạnh khi bỏ các symbol nghi ngờ hay không. Nếu kết quả ổn định, research vẫn tiến được trong lúc data lineage được hoàn thiện. Nếu kết quả đảo chiều, đó là bằng chứng data quality đang chi phối model và phải ưu tiên sửa store/sidecar trước.

## Runner

`scripts/run_v68_consolidated_c3_hose_gitbash.sh`

Artifact thành công:

`UPLOAD_THIS_v68_CONSOLIDATED_C3_HOSE-*.zip`

V68 không được promote model hoặc policy trực tiếp. Bước sau phụ thuộc artifact workstation, không phụ thuộc CI.
