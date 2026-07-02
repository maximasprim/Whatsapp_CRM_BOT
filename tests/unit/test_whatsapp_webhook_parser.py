from __future__ import annotations

from app.whatsapp.webhook_parser import parse_webhook_payload


def _wrap_messages_payload(messages: list[dict], statuses: list[dict] | None = None) -> dict:
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "123456"}}
    if messages:
        value["messages"] = messages
    if statuses:
        value["statuses"] = statuses
    return {
        "entry": [{
            "id": "entry1",
            "changes": [{"field": "messages", "value": value}],
        }]
    }


class TestParseTextMessage:
    def test_parses_basic_text_message(self):
        payload = _wrap_messages_payload([{
            "id": "wamid.123",
            "from": "254712345678",
            "timestamp": "1700000000",
            "type": "text",
            "text": {"body": "Hello, I need help"},
        }])
        messages, statuses = parse_webhook_payload(payload)
        assert len(messages) == 1
        assert messages[0].text == "Hello, I need help"
        assert messages[0].from_number == "254712345678"
        assert messages[0].message_type == "text"
        assert len(statuses) == 0


class TestParseMediaMessages:
    def test_parses_image_message_with_caption(self):
        payload = _wrap_messages_payload([{
            "id": "wamid.456",
            "from": "254712345678",
            "timestamp": "1700000001",
            "type": "image",
            "image": {"id": "media123", "mime_type": "image/jpeg", "caption": "Check this out"},
        }])
        messages, _ = parse_webhook_payload(payload)
        assert messages[0].media_id == "media123"
        assert messages[0].media_mime_type == "image/jpeg"
        assert messages[0].caption == "Check this out"

    def test_parses_document_message_with_filename(self):
        payload = _wrap_messages_payload([{
            "id": "wamid.789",
            "from": "254712345678",
            "timestamp": "1700000002",
            "type": "document",
            "document": {"id": "doc123", "mime_type": "application/pdf", "filename": "invoice.pdf"},
        }])
        messages, _ = parse_webhook_payload(payload)
        assert messages[0].filename == "invoice.pdf"
        assert messages[0].media_mime_type == "application/pdf"


class TestParseLocationMessage:
    def test_parses_location_coordinates(self):
        payload = _wrap_messages_payload([{
            "id": "wamid.loc1",
            "from": "254712345678",
            "timestamp": "1700000003",
            "type": "location",
            "location": {"latitude": -1.286389, "longitude": 36.817223, "name": "Nairobi"},
        }])
        messages, _ = parse_webhook_payload(payload)
        assert messages[0].latitude == -1.286389
        assert messages[0].longitude == 36.817223
        assert messages[0].location_name == "Nairobi"


class TestParseInteractiveReplies:
    def test_parses_button_reply(self):
        payload = _wrap_messages_payload([{
            "id": "wamid.btn1",
            "from": "254712345678",
            "timestamp": "1700000004",
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "confirm_yes", "title": "Yes, confirm"},
            },
        }])
        messages, _ = parse_webhook_payload(payload)
        assert messages[0].button_reply_id == "confirm_yes"
        assert messages[0].button_reply_title == "Yes, confirm"
        assert messages[0].text == "Yes, confirm"

    def test_parses_list_reply(self):
        payload = _wrap_messages_payload([{
            "id": "wamid.list1",
            "from": "254712345678",
            "timestamp": "1700000005",
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "product_42", "title": "Premium Plan"},
            },
        }])
        messages, _ = parse_webhook_payload(payload)
        assert messages[0].list_reply_id == "product_42"
        assert messages[0].text == "Premium Plan"


class TestParseStatusUpdates:
    def test_parses_delivered_status(self):
        payload = _wrap_messages_payload([], statuses=[{
            "id": "wamid.123",
            "recipient_id": "254712345678",
            "status": "delivered",
            "timestamp": "1700000006",
        }])
        messages, statuses = parse_webhook_payload(payload)
        assert len(messages) == 0
        assert len(statuses) == 1
        assert statuses[0].status == "delivered"
        assert statuses[0].message_id == "wamid.123"

    def test_parses_failed_status_with_error_details(self):
        payload = _wrap_messages_payload([], statuses=[{
            "id": "wamid.456",
            "recipient_id": "254712345678",
            "status": "failed",
            "timestamp": "1700000007",
            "errors": [{"code": 131026, "title": "Message undeliverable"}],
        }])
        _, statuses = parse_webhook_payload(payload)
        assert statuses[0].status == "failed"
        assert statuses[0].error_code == "131026"
        assert statuses[0].error_title == "Message undeliverable"


class TestParseMalformedPayloads:
    def test_empty_payload_returns_empty_lists(self):
        messages, statuses = parse_webhook_payload({})
        assert messages == []
        assert statuses == []

    def test_payload_missing_entry_key_does_not_crash(self):
        messages, statuses = parse_webhook_payload({"object": "whatsapp_business_account"})
        assert messages == []
        assert statuses == []

    def test_non_messages_field_changes_are_ignored(self):
        payload = {
            "entry": [{
                "changes": [{"field": "account_alerts", "value": {"some": "data"}}],
            }]
        }
        messages, statuses = parse_webhook_payload(payload)
        assert messages == []
        assert statuses == []

    def test_message_missing_required_fields_is_skipped_not_crashed(self):
        payload = _wrap_messages_payload([{"type": "text", "text": {"body": "no id or from"}}])
        messages, _ = parse_webhook_payload(payload)
        assert messages == []
