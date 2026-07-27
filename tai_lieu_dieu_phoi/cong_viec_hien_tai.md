# Công việc hiện tại

Cập nhật: 2026-07-27

## Mục tiêu vòng

Sửa `PR14_DOCUMENTATION_REGRESSION_BLOCKER` trên PR #14 bằng một commit nối tiếp, không viết lại lịch sử.

## Nền

- Repository: `Tienkhoaa2908/vn-quant-system`.
- Branch: `m4-dac_trung-xep-hang-hoc_may-sach-final`.
- Head trước sửa: `07bc48075be5e44cd410ff8fc2ef02828fc8fd73`.
- Source kỹ thuật: `5aec6ace8423fbf30442aa77db6ff63adb3c854e`.
- Doc base: `8452cfb8ddc521c80d7f1128acd72039b1fca0eb`.
- PR #14 và PR #13 đều phải giữ Open, Draft, chưa merge.

## Phạm vi

1. Phục hồi nguyên nội dung tích lũy của bảy tài liệu từ commit thứ tư.
2. Giữ toàn bộ QD-0001..QD-0059 và nối QD-0060.
3. Giữ toàn bộ README, CLI, hợp đồng Mốc 0–4 và lịch sử Mốc 0–3.
4. Giữ toàn bộ kiến trúc Mốc 4; chỉ thêm durability đa nền tảng tại phần publication.
5. Giữ lộ trình M0–M6 trong kế hoạch tổng thể; chỉ cập nhật trạng thái M4.
6. Cập nhật PR #14, branch final, run #335 và hai Job ID.
7. Không sửa code, test, workflow, `pyproject.toml` hoặc `uv.lock`.

## Cửa hoàn tất

- Tất cả bảy tài liệu có số dòng không thấp hơn bản tại doc base.
- `DECISIONS.md` chứa QD-0001, QD-0059 và QD-0060.
- Diff ngoài bảy tài liệu so với source kỹ thuật bằng 0.
- CI head mới checkout `refs/pull/14/merge`, đạt lock check, frozen sync, compileall và toàn bộ unittest trên Ubuntu/Windows.

## Cấm hiện hành

Không force-push, rebase, squash hoặc amend; không Tier A/Tier B, dữ liệu thật, Ready, merge, LightGBM hoặc Mốc 5.

## Cap nhat QD-0061: contract benchmark close-only

PR canonical hien tai la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Giai doan 2A da hoan tat voi `D.OFFICIAL_VALUES_UNAVAILABLE`, `SEMANTICS_DEFINITION_NOT_FOUND` va `CLOSE_ONLY_BENCHMARK_CONTRACT`; cac tham chieu PR #14/CI cu o phan lich su khong phai trang thai current-head. CI #347 chi la baseline cua head cu truoc patch nay.

Co phieu tiep tuc dung `ThanhOHLCV` strict. Benchmark dung `ThanhBenchmarkDongCua` va schema CSV dung sau cot `ma,ngay,gia_dong_cua,nguon,phien_ban,co_so_gia`; open/high/low/volume benchmark khong duoc dua vao canonical input, sua, suy dien hoac dung trong feature/label. Raw KBS va ho so audit run `m4_tier_a_20260727T081753Z_e2c866db` giu bat bien; khong co correction overlay hay replacement values. Manifest/bao cao cong bo `benchmark_contract=close_only`, hai canh bao bat buoc va gioi han chi kiem tra ky thuat. Exact official OHLC van chua co; dieu nay khong xac nhan co so gia co phieu. Normalization, Tier A pipeline, Tier B va Moc 5 chua chay.

## Cap nhat QD-0062: reporting/provenance blocker

Canonical PR la #16 tren nhanh `m4-dac_trung-xep-hang-hoc_may-sach-final-v2`. Head truoc correction la `2efa627c65cb5387bcc4aa77f4063070812d6aa6`; close-only QD-0061 va CI #351 da dat. Giai doan 2A da hoan tat; blocker hien tai chi la generic runner hard-code reporting/provenance khong thuoc kha nang tu xac minh. Correction QD-0062 tach policy khoi runtime fact, khong chay lai Tier A pipeline va khong mo Giai doan 2B, Tier B hay Moc 5.
