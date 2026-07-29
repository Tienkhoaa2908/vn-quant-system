# Mẫu prompt gói công việc lớn

Cập nhật: 2026-07-29

Dùng mẫu này cho mọi đoạn chuyên môn. Không sao chép toàn bộ lịch sử dự án vào prompt.

```text
Bạn đang thực hiện WORK_PACKAGE: <MA_GOI>

Repository:
Tienkhoaa2908/vn-quant-system

Exact anchor:
<SHA_MAIN>

Đọc bắt buộc:
- tai_lieu_dieu_phoi/nguyen_tac_du_an.md
- tai_lieu_dieu_phoi/giao_thuc_goi_cong_viec_lon.md
- tai_lieu_dieu_phoi/ban_dieu_phoi_hien_hanh.md
- <CONTRACT_VA_TAI_LIEU_CHUYEN_MON>

OUTCOME DUY NHẤT
<MÔ_TẢ KẾT QUẢ HOÀN CHỈNH, KHÔNG MÔ TẢ TỪNG THAO TÁC NHỎ>

LANES
A. <IMPLEMENTATION HOẶC NGHIÊN CỨU>
B. <EVIDENCE/DATA>
C. <INTEGRATION>
D. <AUDIT/TEST>
E. <DOCUMENTATION>

PREFLIGHT BẮT BUỘC
Trong phần đầu, kiểm tra và ghi AVAILABLE/UNAVAILABLE/PARTIAL/NOT_REQUIRED cho:
repository_write, local_checkout, python_runtime, full_test_execution,
outbound_network, javascript_browser, raw_byte_download,
restricted_archive_write, hash_tools, github_auth, ci_visibility.

Nếu một capability bị chặn ở tầng môi trường:
- thử tối đa một fallback độc lập;
- ghi exact error;
- không lặp lại bằng prompt mới;
- tiếp tục mọi lane độc lập;
- tạo action kit ngắn nếu cần người dùng thực hiện.

PHẠM VI ĐƯỢC PHÉP
- <FILE/PACKAGE/BRANCH>
- được tự thiết kế chi tiết phù hợp contract;
- được tự sửa tối đa ba vòng trong cùng Draft PR;
- được commit, push, mở Draft PR và sửa CI trong cùng scope.

KHÔNG ĐƯỢC
- đổi contract đã khóa;
- mở rộng dependency hoặc mốc ngoài scope;
- nâng noncanonical thành canonical;
- chuyển RESEARCH_GATE khỏi FAIL;
- sửa PR #20 hoặc mở Mốc 5 nếu không được ghi rõ;
- force-push, rewrite history hoặc thao tác phá hủy.

CHỈ ESCALATE KHI
- cần quyết định ngữ nghĩa;
- cần quyền truy cập/credential;
- cần mở rộng scope;
- cần canonical promotion;
- blocker làm vô hiệu toàn bộ outcome.

CỬA NGHIỆM THU
- <OUTCOME CHECKLIST>
- test mới cho hành vi mới;
- negative/boundary tests;
- full regression;
- diff đúng scope;
- current-head CI;
- một báo cáo cuối duy nhất.

BÁO CÁO CUỐI
1. Phán quyết
2. Outcome hoàn thành
3. Branch/commit/PR
4. Changed files
5. Test/CI
6. Evidence/artifacts
7. Blocker còn lại
8. Quyết định cần đoạn 00
9. Next gate duy nhất

Không dừng sau từng lane. Không gửi prompt phụ. Không tự mở work package kế tiếp.
```

## Quy tắc viết outcome

Outcome tốt:

```text
Triển khai đầy đủ tầng dữ liệu VN100 PIT v2 bằng fixture tổng hợp, gồm registry,
normalization, interval builder, coverage validator, auditor và Mốc 4 preflight,
có test đối nghịch và Draft PR xanh trên Ubuntu/Windows.
```

Outcome không tốt:

```text
Viết schema.
Sau đó quay lại xin phép viết parser.
Sau đó quay lại xin phép viết test.
```

## Quy tắc gom task

Gom chung khi các task:

- cùng contract;
- cùng package hoặc boundary;
- có thể kiểm thử trong một regression suite;
- không cần quyết định ngữ nghĩa ở giữa.

Tách riêng khi:

- thay đổi contract;
- có dependency hoặc quyền truy cập mới;
- có canonical promotion;
- cần merge một nền kỹ thuật trước khi tích hợp an toàn.
