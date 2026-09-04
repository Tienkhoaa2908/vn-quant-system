# RESTORE PROMPTS

Updated: 2026-09-01

These prompts are designed for starting a new chat or forcing a continuity checkpoint without relying on chat memory.

## Prompt 1 — restore a new chat from GitHub

```text
Mày là đoạn điều phối kế nhiệm của dự án VN Quant System.

Repository chính:
Tienkhoaa2908/vn-quant-system

Không yêu cầu tao kể lại lịch sử bằng trí nhớ. GitHub, commit/PR/CI, tài liệu điều phối hiện hành và workstation evidence là nguồn sự thật.

BẮT BUỘC TRƯỚC KHI LÀM VIỆC:

1. Đọc root `AGENTS.md`.
2. Đọc theo thứ tự:
   - `tai_lieu_dieu_phoi/CURRENT_STATE.md`
   - `tai_lieu_dieu_phoi/CHAT_OPERATING_PROTOCOL.md`
   - `tai_lieu_dieu_phoi/KNOWN_ISSUES_AND_GUARDRAILS.md`
   - `tai_lieu_dieu_phoi/ROADMAP.md`
   - các entry mới nhất của `tai_lieu_dieu_phoi/CHAT_TURN_LOG.md`
   - `DECISIONS.md` khi cần truy nguyên quyết định lịch sử.
3. Kiểm tra trực tiếp trên GitHub:
   - nhánh hiện hành;
   - PR đang active và base/head của nó;
   - commit HEAD mới nhất;
   - CI/checks của đúng HEAD đó;
   - các PR stacked liên quan nếu có.
4. Nếu công việc liên quan một Vxx cụ thể, đọc contract và workstation result/evidence mới nhất của Vxx đó. Không dùng handoff cũ làm current truth nếu đã có tài liệu mới hơn.
5. Đối chiếu mọi mâu thuẫn theo thứ tự ưu tiên evidence đã ghi trong `CHAT_OPERATING_PROTOCOL.md`.

QUY TẮC KHÔNG ĐƯỢC PHÁ:

- Không sửa trực tiếp main.
- Không merge PR nếu tao chưa ra lệnh merge rõ ràng.
- Không reset/xóa V77/V80 persistent state.
- Không tuyên bố CI green nếu chưa kiểm đúng current HEAD.
- Phân biệt CI, workstation smoke, historical research, fresh forward evidence và live authority.
- C3 champion và V76 stop rule giữ nguyên trừ khi GitHub current state có quyết định mới hơn.
- Không mở lại model/threshold fishing trên cùng historical sample chỉ để tìm kết quả đẹp.
- Không coi localhost HTTP 200 là DNSE realtime healthy.
- Không bật order mutation nếu các broker/realtime/TLS/reconciliation gate chưa được đóng.
- Repo workstation đúng là `/d/VNQuant/vn-quant-system` trong Git Bash.

SAU KHI KHÔI PHỤC:

Hãy báo ngắn gọn cho tao:
- current branch/PR/HEAD/CI;
- champion + research/data gates;
- trạng thái web/realtime DNSE hiện tại;
- blocker quan trọng nhất;
- next action hợp lý nhất.

Sau đó tiếp tục công việc hiện tại, không tự mở research lớn mới nếu chưa cần.

BẮT BUỘC TRƯỚC MỖI CÂU TRẢ LỜI TRONG CHAT NÀY:
đọc lại current GitHub state cần thiết và ghi một continuity checkpoint lên GitHub theo `CHAT_OPERATING_PROTOCOL.md`. Nếu không có state change thì vẫn append `NO_STATE_CHANGE` vào `CHAT_TURN_LOG.md`. Nếu write GitHub thất bại, nói rõ, không được giả vờ đã lưu.
```

## Prompt 2 — force a professional GitHub continuity checkpoint

```text
Thực hiện một PROJECT CONTINUITY CHECKPOINT cho VN Quant System ngay bây giờ.

Repository:
Tienkhoaa2908/vn-quant-system

Mục tiêu là bảo đảm nếu đoạn chat kết thúc ngay sau lượt này thì chat kế nhiệm vẫn khôi phục chính xác được trạng thái dự án chỉ từ GitHub, không cần tao kể lại.

Làm theo trình tự:

A. READ-BACK / VERIFY
1. Đọc `AGENTS.md`, `CURRENT_STATE.md`, `CHAT_OPERATING_PROTOCOL.md`, `KNOWN_ISSUES_AND_GUARDRAILS.md`, `ROADMAP.md`, các entry mới nhất của `CHAT_TURN_LOG.md`.
2. Kiểm tra active branch, PR base/head, current HEAD, mergeability và CI/checks của đúng HEAD.
3. Đọc contract/result/evidence mới nhất của work package đang active.
4. So sánh repo docs với những gì vừa xảy ra trong cuộc trò chuyện và workstation evidence. Không dùng memory để override GitHub/evidence.

B. UPDATE DURABLE STATE
5. Cập nhật `CURRENT_STATE.md` với trạng thái thật mới nhất, chỉ ghi claim có evidence.
6. Cập nhật `KNOWN_ISSUES_AND_GUARDRAILS.md` nếu vừa gặp bug, false assumption, command/path mistake, integrity issue, API behavior hoặc lesson mới.
7. Cập nhật `ROADMAP.md` nếu priority/next gate thay đổi.
8. Tạo/cập nhật Vxx result/handoff/contract nếu có workstation result hoặc quyết định kỹ thuật mới.
9. Append `CHAT_TURN_LOG.md` với timestamp, intent, refs đã đọc, actions, evidence class, state change/NO_STATE_CHANGE, blockers và exact next action.
10. Nếu có tài liệu top-level tự nhận là current nhưng đã lỗi thời/superseded, xóa hoặc thay thế nó. Không xóa versioned research contract/workstation evidence chỉ vì cũ; chỉ xóa khi rõ ràng redundant và unique facts đã được bảo toàn ở nơi khác.
11. Cập nhật `RESTORE_PROMPTS.md` nếu quy trình recovery thay đổi.

C. SAFETY / HYGIENE
12. Không commit credentials, API secrets, OTP, Trading Token, private account payload hoặc sensitive broker data.
13. Không sửa trực tiếp main; commit trên branch/PR hiện hành hoặc branch phù hợp.
14. Không merge nếu tao chưa yêu cầu.
15. Không reset/delete immutable V77/V80 state.
16. Không biến CI green thành research/live claim.

D. VERIFY AFTER WRITE
17. Re-read new HEAD/PR sau commit.
18. Re-read các file vừa cập nhật để chắc không bị stale/malformed.
19. Kiểm tra CI của HEAD mới; phân biệt rõ implementation-head CI đã green với docs-head CI đang chạy nếu có.
20. Trả cho tao một summary ngắn gồm:
   - commit checkpoint mới;
   - file đã thêm/sửa/xóa;
   - current branch/PR/CI;
   - blocker/next action;
   - xác nhận chưa merge nếu chưa được yêu cầu.

Từ thời điểm này trở đi, coi `AGENTS.md` + `CHAT_OPERATING_PROTOCOL.md` là quy tắc bắt buộc cho mọi lượt chat của dự án: trước khi trả lời phải read-back GitHub và trước final phải checkpoint GitHub, kể cả khi chỉ ghi `NO_STATE_CHANGE`.
```
