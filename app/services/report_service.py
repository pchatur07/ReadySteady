"""Daily sales report for the canteen admin (FR-15)."""
from collections import Counter

from ..order_state import Status
from ..repository import OrderRepo

SOLD = [Status.PLACED.value, Status.ACCEPTED.value, Status.PREPARING.value, Status.READY.value, Status.PICKED_UP.value]


def daily_report(conn, canteen_id, day):
    prefix = day.isoformat()
    orders = OrderRepo.for_day(conn, canteen_id, prefix)
    by_status = Counter(o["status"] for o in orders)
    sold = [o for o in orders if o["status"] in SOLD]
    busiest = Counter(o["slot_start"] for o in sold).most_common(1)
    return {
        "date": prefix,
        "orders_total": len(orders),
        "orders_by_status": {s.value: by_status.get(s.value, 0) for s in Status},
        "revenue_paise": sum(o["total_paise"] for o in sold),
        "average_order_paise": round(sum(o["total_paise"] for o in sold) / len(sold)) if sold else 0,
        "busiest_slot": busiest[0][0] if busiest else None,
        "top_items": OrderRepo.top_items(conn, canteen_id, prefix, SOLD),
    }
