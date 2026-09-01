# Bộ tài liệu điều phối dự án VN Quant System

Thư mục này là đầu não bền vững của dự án. GitHub/evidence mới hơn luôn ưu tiên trí nhớ chat.

## Thứ tự đọc bắt buộc cho chat/agent mới

1. `../AGENTS.md`
2. `CURRENT_STATE.md`
3. `CHAT_OPERATING_PROTOCOL.md`
4. `KNOWN_ISSUES_AND_GUARDRAILS.md`
5. `ROADMAP.md`
6. các entry mới nhất trong `CHAT_TURN_LOG.md`
7. contract/result của Vxx đang active
8. `../DECISIONS.md` khi cần truy nguyên quyết định lịch sử

`RESTORE_PROMPTS.md` chứa prompt khôi phục chat mới và prompt continuity checkpoint chuẩn.

## Current vs historical

Current authority chỉ nằm ở bộ file current/protocol phía trên sau khi đã đối chiếu GitHub/evidence.

Các file tên theo phiên bản/ngày như `v83_*`, `v84_*`, `v85_*`, `v86_*` là evidence/contract lịch sử hoặc work-package-specific. Chúng có thể rất quan trọng nhưng không tự động đại diện cho trạng thái hiện tại toàn dự án.

Các file anti-regression và research-standard vẫn là guardrail ổn định nếu không bị current evidence supersede.

## Quy tắc cập nhật bắt buộc

Mỗi prompt trong dự án phải có hai động tác:

1. read-back GitHub trước khi trả lời;
2. GitHub continuity checkpoint trước final response.

Ít nhất phải append `CHAT_TURN_LOG.md`. Nếu có thay đổi bền vững thì cập nhật `CURRENT_STATE.md`, guardrails/roadmap hoặc Vxx result/contract tương ứng.

Nếu không có state change, vẫn ghi `NO_STATE_CHANGE` trong turn log. Nếu GitHub write thất bại, phải nói rõ; không được giả vờ đã lưu.

## Hygiene

- Không tạo thêm nhiều file cùng tự nhận là “current/status/handoff”.
- Không giữ tài liệu top-level đã lỗi thời chỉ vì lịch sử; Git history đã bảo toàn bản cũ.
- Không xóa versioned evidence/contract chỉ vì cũ nếu nó còn giá trị audit.
- Không commit credential/API secret/OTP/Trading Token/private broker payload.
- Không merge nếu user chưa yêu cầu rõ.
