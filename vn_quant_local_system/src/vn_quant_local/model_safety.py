"""Calendar guards cho canonical C3 và sell-review.

Kho dữ liệu có thể dừng ở phiên cuối tháng vừa hoàn tất trong vài ngày đầu tháng
mới. Logic cũ luôn bỏ tháng cuối cùng trong kho nên có thể chậm một tháng cho tới
khi xuất hiện bar đầu tiên của tháng mới. V47 xác định tháng hoàn tất theo ngày
lịch local: mọi tháng nhỏ hơn tháng hiện tại đều là tháng hoàn tất.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Sequence

from . import c3_model


def local_today() -> date:
    return datetime.now().astimezone().date()


def completed_month_signal_days(
    calendar: Sequence[date],
    *,
    count: int = 3,
    today: date | None = None,
) -> list[date]:
    if count < 1:
        raise ValueError("count phải lớn hơn 0")
    if not calendar:
        raise ValueError("Market calendar rỗng")
    current = today or local_today()
    current_key = (current.year, current.month)
    months: dict[tuple[int, int], date] = {}
    for day in calendar:
        months[(day.year, day.month)] = day
    completed = [key for key in sorted(months) if key < current_key]
    if len(completed) < count:
        raise ValueError(
            f"Cần ít nhất {count} tháng hoàn tất; hiện có {len(completed)}"
        )
    return [months[key] for key in reversed(completed[-count:])]


def robust_signal_days(
    calendar: Sequence[date],
    *,
    today: date | None = None,
) -> tuple[date, date]:
    if not calendar:
        raise ValueError("Market calendar rỗng")
    canonical = completed_month_signal_days(
        calendar,
        count=1,
        today=today,
    )[0]
    return canonical, calendar[-1]


def apply() -> None:
    """Áp dụng patch tại runtime cho mọi entrypoint hiện có."""

    c3_model._signal_days = robust_signal_days
    # Import muộn để tránh vòng import khi package đang khởi tạo.
    from . import weekly_plan

    weekly_plan._completed_month_signal_days = completed_month_signal_days
