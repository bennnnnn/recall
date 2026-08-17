from app.gateways.google_gmail_gateway import GmailMessage
from app.services.email_sender_templates import (
    display_sender,
    email_domain,
    extract_from_sender_template,
)


def _message(
    *,
    from_address: str,
    subject: str,
    snippet: str = "",
    body_text: str = "",
) -> GmailMessage:
    return GmailMessage(
        id="m1",
        subject=subject,
        snippet=snippet,
        body_text=body_text,
        received_at=None,
        from_address=from_address,
    )


def test_email_domain_strips_angle_brackets():
    assert email_domain("Amazon <shipment-tracking@amazon.com>") == "amazon.com"
    assert email_domain("auto-confirm@amazon.co.uk") == "amazon.co.uk"
    assert email_domain("no-at-sign") == ""


def test_display_sender_prefers_rfc_name():
    assert display_sender("Amazon.com <shipment-tracking@amazon.com>") == "Amazon.com"
    assert display_sender("shipment-tracking@ups.com") == "UPS"


def test_amazon_shipped_uses_package_template():
    item = extract_from_sender_template(
        _message(
            from_address="Amazon <auto-confirm@amazon.com>",
            subject="Your order has shipped",
            snippet="Out for delivery tomorrow",
        )
    )
    assert item is not None
    assert item.title.startswith("Amazon delivery")
    assert item.confidence >= 0.8


def test_amazon_marketing_without_cue_falls_through():
    assert (
        extract_from_sender_template(
            _message(
                from_address="Amazon <deals@amazon.com>",
                subject="Deals for you",
                snippet="Save on headphones",
            )
        )
        is None
    )


def test_opentable_reservation_template():
    item = extract_from_sender_template(
        _message(
            from_address="OpenTable <noreply@opentable.com>",
            subject="Reservation confirmed",
            snippet="Table for 2 on Friday",
        )
    )
    assert item is not None
    assert "OpenTable reservation" in item.title


def test_calendly_appointment_template():
    item = extract_from_sender_template(
        _message(
            from_address="Calendly <notifications@calendly.com>",
            subject="New event: Meeting with Alex",
            snippet="You are booked for Thursday",
        )
    )
    assert item is not None
    assert item.title.startswith("Calendly appointment")


def test_airline_sender_is_not_a_template():
    """Flights are a separate FEATURES item — do not steal them here."""
    assert (
        extract_from_sender_template(
            _message(
                from_address="Delta <itinerary@delta.com>",
                subject="Your flight is confirmed",
                snippet="DL 123 departing SFO",
            )
        )
        is None
    )
