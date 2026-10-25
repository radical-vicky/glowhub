import logging
log = logging.getLogger(__name__)


def on_booking_transition(booking, old, new):
    """Called from Booking.transition. Money-ledger effects are synchronous and idempotent;
    reward effects must never break a booking."""
    from payouts import services as payouts
    if new == "CONFIRMED":
        payouts.credit_booking(booking)
    elif new in ("CANCELLED_BY_CUSTOMER", "CANCELLED_BY_PROVIDER"):
        payouts.reverse_booking(booking)
    try:
        from rewards import services as rewards
        if new == "COMPLETED":
            rewards.on_booking_completed(booking)
        elif new in ("CANCELLED_BY_CUSTOMER", "CANCELLED_BY_PROVIDER"):
            rewards.clawback_booking(booking)
    except Exception:
        log.exception("rewards hook failed")
