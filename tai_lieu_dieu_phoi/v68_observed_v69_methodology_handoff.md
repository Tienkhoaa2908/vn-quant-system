# V68 observed result -> V69 methodology handoff

Tài liệu này ghi các fact đã quan sát từ artifact workstation V68 chạy trên data local và các guardrail thống kê bắt buộc cho V69. Artifact mới hơn và repo mới hơn luôn thắng.

## Provenance V68 đã xác minh

- branch: `agent/v68-consolidated-c3-hose-research`;
- workstation HEAD: `445648971387bbe80fbb21066412bb195a39bedb`;
- Python: `vn_quant_local_system/.venv` trên Windows;
- source store SHA256: `2959f8cce0c11e8e4186fcb49ae75bf7babf86b84afe64ca3b843a7470d58b1a`;
- 25/25 workstation regression tests PASS;
- consolidated run status `SUCCESS`;
- champion vẫn là `C3_STABLE_3_PAST_IC_SHRUNK`;
- August 2026 shadow-only;
- không có promotion/live authorization.

## Data facts

- local stock count: 121;
- coverage: 2015-06-29 -> 2026-08-13;
- price basis vẫn `CHUA_XAC_NHAN`;
- PIT HOSE gate vẫn mở;
- official HOSE collector vẫn lỗi JSON và không được diễn giải `0 match` thành membership fact;
- 10 symbol có gap liên phiên >=18%: APH, BCM, GEE, HHV, HNG, OCB, SIP, VHM, VIB, VIX;
- chỉ VHM được basis-provenance audit xác định là mixed-batch seam candidate;
- VHM 2026-07-22 có revision old open/close `136.2/126.9` thành new `68.1/63.45`, trong khi 2026-07-21 nằm fetch batch cũ. Đây là mixed price-basis seam evidence, chưa phải adjustment factor được phép áp dụng tự động.

## C3 observations

Ba sensitivity universe đều chạy 110 monthly snapshots:

- BROAD_PROVISIONAL: 121 symbols;
- SEAM_CLEAN: 120 symbols, loại VHM toàn lịch sử chỉ để sensitivity;
- GAP18_CLEAN: 111 symbols, loại 10 gap symbols toàn lịch sử chỉ để sensitivity.

SEAM/GAP exclusion KHÔNG phải phương pháp sửa corporate action; đó chỉ là sensitivity test và confound symbol removal với data repair.

Top10 stability:

- BROAD vs SEAM mean Jaccard khoảng 0.969;
- BROAD vs GAP18 mean Jaccard khoảng 0.895;
- latest 2026-07-31 BROAD vs SEAM cùng Top10 set;
- latest GAP18 thay SSB bằng DHC.

Historical monthly Top10 mean excess:

- horizon 5: khoảng +0.15% tới +0.17%/snapshot;
- horizon 10: khoảng +0.57% tới +0.60%;
- horizon 20: khoảng +1.14% tới +1.29%.

Nhưng 2026 deteriorates: BROAD mean monthly Top10 excess khoảng -0.72% tại h10 và -1.73% tại h20. Không được diễn giải aggregate long-history edge là current-regime edge.

C3 weight history ổn định về cấu trúc: relative-strength-120 và high-52-week thường chi phối; low-vol weight nhỏ hơn nhưng tăng lại trong 2026. Latest BROAD 2026-07-31 xấp xỉ low-vol 0.259 / RS120 0.370 / high52 0.372.

Latest canonical 2026-07-31 BROAD Top10:
VPI, MSB, HCM, VIC, GMD, LPB, STB, BAF, ACB, SSB.

## August shadow observations

2026-08-13 BROAD Preview:

1 MSB, 2 TLG, 3 HCM, 4 LPB, 5 BAF, 6 STB, 7 BWE, 8 DHC, 9 KDC, 10 GMD, 11 SAB, 12 SBT, 13 VPI, 14 VIC, ...

VPI:

- canonical rank 1;
- preview rank 13, prior preview rank 4;
- below MA20/MA50, weak relative returns and 20d drawdown;
- frozen cohort matches: `R03`, `R05`, `R06`, `R12`, `R13`, `R14`, `R15`.

Điều này chứng minh weekly architecture có thể nhìn thấy deterioration của VPI dù monthly canonical còn cao. Nhưng V68 historical RISK inference chưa đủ mạnh để biến các trigger này thành mechanical exit.

TLG:

- ngoài canonical;
- Preview rank 2 (BROAD/SEAM), rank 3 GAP18;
- frozen leader matches: `L01`, `L02`, `L03`, `L04`, `L10`, `L11`, `L13`, `L14`, `L18`;
- không match `L15` vì prior preview rank tuần trước không ở Top10.

Do đó `L15_PERSIST_REL` không tự giải quyết bài toán fast-emerging leader kiểu TLG.

## V68 statistical limitation discovered

Hai metric V68 không được dùng làm promotion evidence:

1. `bootstrap_two_sided_p` được suy ra từ bootstrap distribution quanh observed sample, không phải null randomisation distribution. Không được gọi đây là p-value chuẩn rồi BH-FDR cho quyết định cuối.
2. `leader_incremental_mean_excess_vs_raw_top5` lấy unconditional cohort mean trừ unconditional raw Top5 mean toàn lịch sử. Nó có market-state/date-composition confounding và không phải matched incremental effect.

Manual audit từ artifact cho thấy `L15_PERSIST_REL` vẫn là leader filter đáng nghiên cứu nhất, nhưng matched-week effect nhỏ hơn rất nhiều so với unconditional difference. Recent 2023-2026 và GAP18 sensitivity cũng yếu hơn aggregate history. Không được promote L15 chỉ dựa V68.

## V69 mandatory inference contract

- không đổi C3;
- không đổi 36 frozen cohort threshold;
- Top5-scoped leader cohort phải so với raw emerging Top5 cùng tuần;
- Top10-scoped leader cohort phải so với raw emerging Top10 cùng tuần;
- RISK cohort phải so với canonical Top10 không bị signal cùng tuần;
- protection phải đo cả forward loss, MAE/adverse excursion và rebound/opportunity cost;
- weekly overlapping horizon 10 phải gom vào contiguous two-calendar-month blocks trước inference;
- inferential p-value dùng block sign-flip randomisation under null;
- finite simulation p-value dùng `(extreme+1)/(B+1)`, không bao giờ báo 0;
- bootstrap chỉ dùng cho confidence interval, không dùng thay null test;
- BH-FDR áp trên valid sign-flip p-value trong cùng variant/kind;
- xuất symbol concentration và cohort-overlap;
- xuất recent 2023-2026 riêng;
- August shadow chỉ audit trigger, không tune/select;
- V69 vẫn là robustness audit, không phải pristine untouched holdout và không promotion.

## Current V69 branch

`agent/v69-matched-control-block-robustness`

Runner dự kiến:

`scripts/run_v69_matched_control_gitbash.sh`

Runner phải chạy V68 resource-safe + V69 trong cùng một workstation package và trả một bundle duy nhất.
