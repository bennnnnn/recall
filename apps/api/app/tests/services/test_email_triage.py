from app.gateways.google_gmail_gateway import GmailMessage
from app.services.email_triage import (
    InboxBucket,
    classify_message,
    format_triaged_inbox_block,
)


def _msg(
    *,
    subject: str,
    snippet: str = "",
    from_address: str = "",
    label_ids: tuple[str, ...] = (),
) -> GmailMessage:
    return GmailMessage(
        id="1",
        subject=subject,
        snippet=snippet,
        body_text=snippet,
        received_at=None,
        from_address=from_address,
        label_ids=label_ids,
    )


def test_classify_promotional_as_noise():
    promo = _msg(
        subject="180-day lowest price on items for you",
        snippet="Y Factory Price Customized Shoes for Men.",
        from_address="Shop <shop@store.example>",
        label_ids=("INBOX", "CATEGORY_PROMOTIONS", "UNREAD"),
    )
    assert classify_message(promo).bucket is InboxBucket.NOISE


def test_classify_paypal_legal_as_noise():
    legal = _msg(
        subject="We're making some changes to our PayPal legal agreements",
        snippet="Hello Binalfew, view changes on our website.",
        from_address="PayPal <service@paypal.com>",
        label_ids=("INBOX", "UNREAD"),
    )
    assert classify_message(legal).bucket is InboxBucket.NOISE


def test_classify_unread_personal_question_as_attention():
    personal = _msg(
        subject="Can you review the contract draft?",
        snippet="Let me know if you can follow up tomorrow.",
        from_address="Alex Chen <alex@company.com>",
        label_ids=("INBOX", "UNREAD", "IMPORTANT"),
    )
    assert classify_message(personal).bucket is InboxBucket.NEEDS_ATTENTION


def test_format_triaged_block_hides_noise_and_lists_attention():
    messages = [
        _msg(
            subject="180-day lowest price on items for you",
            snippet="Shoes sale",
            from_address="Shop <shop@store.example>",
            label_ids=("CATEGORY_PROMOTIONS",),
        ),
        _msg(
            subject="Can you review the contract draft?",
            snippet="Please respond by Friday.",
            from_address="Alex Chen <alex@company.com>",
            label_ids=("INBOX", "UNREAD", "IMPORTANT"),
        ),
    ]
    block = format_triaged_inbox_block(
        google_email="me@example.com",
        messages=messages,
        pending_suggestions=[],
    )
    assert "Needs attention (1):" in block
    assert "contract draft" in block
    assert "Filtered as promotional" in block
    assert "lowest price" not in block
