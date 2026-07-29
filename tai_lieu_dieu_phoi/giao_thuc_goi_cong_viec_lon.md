# Giao thức gói công việc lớn

Cập nhật: 2026-07-29

## 1. Mục tiêu

Giao thức này thay cách điều phối bằng nhiều lát cắt nhỏ bằng một gói công việc theo kết quả. Một gói phải đủ lớn để tạo tiến bộ kỹ thuật có ý nghĩa, nhưng vẫn có ranh giới, kiểm thử và cửa nghiệm thu rõ ràng.

Mặc định, một gói gồm nhiều tác vụ liên quan, một nhánh, một Draft PR và một báo cáo cuối. Không quay lại đoạn `00` sau từng thao tác nhỏ.

## 2. Nguyên nhân cần thay đổi

Cách điều phối cũ tạo ba loại lãng phí:

1. lặp lại cùng nền, cùng cấm và cùng checklist trong nhiều prompt;
2. chia việc theo thao tác như điều tra, tải, hash, trích xuất, triển khai thay vì theo một kết quả hoàn chỉnh;
3. tiếp tục phát prompt mới dù blocker thực tế là năng lực môi trường, không phải thiếu chỉ dẫn.

Gói công việc lớn phải loại bỏ ba loại lãng phí này mà không làm yếu các cửa chống look-ahead, survivorship bias, dữ liệu giả hoặc tuyên bố nghiên cứu sai.

## 3. Đơn vị điều phối mới

Đơn vị mặc định là `WORK_PACKAGE`, không phải lát cắt vi mô.

Một work package nên chứa từ 5 đến 15 tác vụ có cùng mục tiêu và cùng cửa nghiệm thu. Ví dụ:

```text
đọc hợp đồng
→ kiểm tra năng lực môi trường
→ thiết kế
→ triển khai
→ viết test
→ tự rà soát
→ sửa lỗi trong phạm vi
→ chạy full test
→ mở Draft PR
→ báo cáo bằng chứng cuối
```

Không tách chuỗi trên thành nhiều prompt nếu không có quyết định ngữ nghĩa mới hoặc blocker không thể xử lý trong phạm vi.

## 4. Quyền tự tiếp tục trong phạm vi

Khi nhận work package, đoạn chuyên môn được phép tự thực hiện liên tục các bước sau mà không xin lại phép:

- đọc mã, test và tài liệu liên quan;
- nghiên cứu nguồn công khai trong phạm vi đã giao;
- thiết kế chi tiết phù hợp với contract đã khóa;
- tạo hoặc cập nhật nhánh chuyên môn;
- triển khai toàn bộ file được phép;
- bổ sung và sửa test;
- chạy kiểm tra cục bộ khả dụng;
- tự rà soát diff;
- sửa lỗi phát hiện trong cùng phạm vi;
- commit, push và mở Draft PR;
- theo dõi CI, sửa CI trong cùng phạm vi và push lại;
- tạo một báo cáo cuối duy nhất.

Không dừng chỉ vì một tác vụ con bị chặn. Phải tiếp tục mọi lane độc lập còn làm được.

## 5. Những việc bắt buộc quay lại đoạn 00

Chỉ dừng và xin quyết định khi gặp một trong các trường hợp:

1. cần thay đổi ngữ nghĩa contract đã khóa;
2. cần mở rộng sang file, package, dependency hoặc mốc ngoài phạm vi;
3. cần dùng credential, access control hoặc dữ liệu có quyền lưu trữ chưa rõ;
4. cần xóa, force-push, rewrite history hoặc thao tác không thể hoàn tác an toàn;
5. cần nâng một bằng chứng noncanonical thành canonical;
6. cần chuyển `RESEARCH_GATE` từ `FAIL` sang trạng thái khác;
7. cần mở Mốc 5, paper trading hoặc sử dụng kết quả như tín hiệu vận hành;
8. blocker làm vô hiệu toàn bộ mục tiêu gói, không chỉ một lane.

Các quyết định cục bộ, có thể hoàn tác và không thay đổi contract không cần quay lại đoạn `00`.

## 6. Preflight năng lực bắt buộc

Trong 10% đầu của work package, phải kiểm tra tối thiểu:

```text
repository_read
repository_write
local_checkout
python_runtime
frozen_dependency_sync
full_test_execution
outbound_network
javascript_browser
raw_byte_download
restricted_archive_write
hash_tools
github_auth
ci_visibility
```

Mỗi năng lực nhận một trạng thái:

```text
AVAILABLE
UNAVAILABLE
PARTIAL
NOT_REQUIRED
```

Kế hoạch thực thi phải được điều chỉnh ngay theo ma trận này.

Không được dành cả work package để thử lại một năng lực đã xác định `UNAVAILABLE` do môi trường.

## 7. Stop-loss cho blocker môi trường

Nếu cùng một thao tác thất bại một lần với nguyên nhân rõ ràng ở tầng môi trường, ví dụ DNS, outbound, JavaScript browser, quyền file hoặc GitHub auth:

1. ghi exact error;
2. thử tối đa một fallback độc lập đã biết;
3. nếu fallback cũng thất bại, đánh dấu capability blocked;
4. không phát lại cùng tác vụ bằng prompt mới trong cùng môi trường;
5. tạo một action kit ngắn cho workstation phù hợp;
6. tiếp tục các lane không phụ thuộc capability đó.

Hai vòng 01F-C và 01F-C2 đều có `document_count_acquired=0` do không có raw-byte transfer. Vì vậy không được tiếp tục lặp official-byte recovery trong cùng môi trường ChatGPT.

## 8. Thực thi theo lane song song

Một gói có thể có nhiều lane:

- `LANE_A_IMPLEMENTATION`: mã, schema, validator, builder, auditor;
- `LANE_B_EVIDENCE`: nguồn, raw byte, hash, provenance;
- `LANE_C_INTEGRATION`: kết nối runner, preflight và publication;
- `LANE_D_AUDIT`: test đối nghịch, kiểm leakage, kiểm deterministic;
- `LANE_E_DOCUMENTATION`: contract, runbook, trạng thái và bàn giao.

Blocker ở một lane không tự động dừng các lane khác. Báo cáo cuối phải nêu rõ quan hệ phụ thuộc và phần nào đã hoàn tất độc lập.

## 9. WIP limit và đường găng

Tối đa hai work package ở trạng thái active:

1. một package nằm trên đường găng;
2. một package song song không làm tăng rủi ro tích hợp.

Đường găng hiện hành của dự án là đóng bốn data gate:

```text
VN100_POINT_IN_TIME_HISTORY_INCOMPLETE
HOSE_EOD_CROSSCHECK_INCOMPLETE
CORPORATE_ACTION_INVENTORY_INCOMPLETE
PRICE_BASIS_UNCONFIRMED
```

Model optimization, LightGBM và Mốc 5 không nằm trên đường găng hiện tại.

## 10. Kích thước gói và tiêu chí hoàn tất

Một gói chỉ được coi là hoàn tất khi có đầy đủ:

- outcome nghiệp vụ đã mô tả;
- diff đúng scope;
- test mới cho hành vi mới;
- full regression khả dụng;
- tự rà soát và sửa lỗi trong cùng gói;
- bằng chứng current-head CI nếu có PR;
- giới hạn và blocker còn lại;
- một next gate duy nhất.

Không tạo PR chỉ để cập nhật trạng thái sau mỗi thao tác nhỏ. Điều phối hậu gộp được gom theo batch hoặc cập nhật cùng PR kế tiếp khi an toàn.

## 11. Failure budget và tự sửa

Mỗi work package có quyền tự sửa tối đa ba vòng trong cùng Draft PR:

```text
implementation review
→ local/full test repair
→ CI repair
```

Không cần prompt mới cho từng vòng sửa nếu không đổi contract hoặc scope.

Nếu sau ba vòng vẫn thất bại, báo cáo root cause, diff hiện tại và lựa chọn thu hẹp rõ ràng cho đoạn `00`.

## 12. Prompt tối giản

Prompt chuyên môn không lặp lại toàn bộ lịch sử dự án. Prompt chỉ chứa:

1. exact anchor;
2. mục tiêu outcome;
3. file hoặc package được phép;
4. contract canonical cần đọc;
5. các lane;
6. cửa nghiệm thu;
7. quyết định phải escalation;
8. output cuối.

Các nguyên tắc ổn định được tham chiếu bằng đường dẫn đến tài liệu này và `nguyen_tac_du_an.md`.

## 13. Vệ sinh tài liệu điều phối

- `DECISIONS.md` là append-only cho quyết định kiến trúc.
- Trạng thái hiện hành phải nằm trong `tai_lieu_dieu_phoi/ban_dieu_phoi_hien_hanh.md`.
- Các tài liệu trạng thái tích lũy cũ chỉ là lịch sử, không được dùng để xác định current anchor nếu mâu thuẫn với bảng hiện hành.
- Git history giữ lịch sử; không cần chép lại toàn bộ lịch sử vào mọi prompt hoặc status file.

## 14. Cửa chất lượng để giảm sửa đi sửa lại

Trước khi push, đoạn chuyên môn phải tự kiểm:

```text
scope_diff
contract_consistency
negative_tests
boundary_dates
lookahead
survivorship
stable_ordering
finite_values
hash_and_manifest
cross_platform_behavior
error_messages
backward_compatibility
full_regression
```

Mọi claim phải phân biệt:

```text
implemented
locally_verified
ci_verified
observed_external
reported_not_verified
blocked
```

Không dùng một trạng thái chung như `VERIFIED` cho nhiều mức bằng chứng.

## 15. Báo cáo cuối của work package

Báo cáo cuối nên ngắn và có đúng các phần:

1. phán quyết;
2. outcome hoàn thành;
3. branch, commit và PR;
4. changed files;
5. test và CI;
6. evidence hoặc artifact;
7. blocker còn lại;
8. quyết định cần đoạn `00`;
9. next gate duy nhất.

Không gửi nhật ký thao tác dài trừ khi phục vụ điều tra lỗi.
