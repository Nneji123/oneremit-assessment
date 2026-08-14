import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient
from transfers.models import ProviderEvent, Transfer

WEBHOOK_URL = "/api/webhooks/provider/"


@pytest.fixture
def api_client():
    return APIClient()


def signature_for(body: bytes) -> str:
    secret = settings.PROVIDER_WEBHOOK_SECRET.encode("utf-8")
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def post_webhook(client, payload, *, sign=True, signature=None):
    body = json.dumps(payload).encode("utf-8")
    headers = {}
    if sign:
        headers["HTTP_X_PROVIDER_SIGNATURE"] = signature_for(body)
    if signature is not None:
        headers["HTTP_X_PROVIDER_SIGNATURE"] = signature
    return client.post(
        WEBHOOK_URL,
        data=body,
        content_type="application/json",
        **headers,
    )


def make_transfer(provider_id="prov_abc", status="processing", **overrides):
    fields = {
        "amount": Decimal("100.00"),
        "currency": "NGN",
        "recipient_ref": "recipient-123",
        "status": status,
        "provider_transfer_id": provider_id,
        "idempotency_key": f"key-{provider_id}",
        "request_fingerprint": f"fingerprint-{provider_id}",
    }
    fields.update(overrides)
    return Transfer.objects.create(**fields)


def event_payload(**overrides):
    payload = {
        "event_id": "evt_123",
        "provider_transfer_id": "prov_abc",
        "status": "completed",
        "occurred_at": "2026-08-10T12:00:00Z",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_missing_provider_signature_returns_401(api_client):
    make_transfer()

    response = post_webhook(api_client, event_payload(), sign=False)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert ProviderEvent.objects.count() == 0


@pytest.mark.django_db
def test_invalid_provider_signature_returns_401(api_client):
    make_transfer()

    response = post_webhook(
        api_client,
        event_payload(),
        signature=f"sha256={'0' * 64}",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert ProviderEvent.objects.count() == 0


@pytest.mark.django_db
def test_malformed_signature_prefix_returns_401(api_client):
    make_transfer()

    response = post_webhook(api_client, event_payload(), signature="md5=deadbeef")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert ProviderEvent.objects.count() == 0


@pytest.mark.django_db
def test_valid_signed_completed_webhook_updates_processing_transfer(api_client):
    transfer = make_transfer()

    response = post_webhook(api_client, event_payload(status="completed"))

    assert response.status_code == status.HTTP_200_OK
    transfer.refresh_from_db()
    assert transfer.status == "completed"
    event = ProviderEvent.objects.get(event_id="evt_123")
    assert event.transfer_id == transfer.pk
    assert event.provider_transfer_id == "prov_abc"
    assert event.provider_status == "completed"
    assert event.outcome == "applied"
    assert event.occurred_at is not None


@pytest.mark.django_db
def test_valid_signed_failed_webhook_updates_processing_transfer(api_client):
    transfer = make_transfer()

    response = post_webhook(api_client, event_payload(status="failed"))

    assert response.status_code == status.HTTP_200_OK
    transfer.refresh_from_db()
    assert transfer.status == "failed"
    event = ProviderEvent.objects.get(event_id="evt_123")
    assert event.provider_status == "failed"
    assert event.outcome == "applied"


@pytest.mark.django_db
def test_scenario_a_duplicate_event_id_is_successful_noop(api_client):
    transfer = make_transfer()

    first = post_webhook(api_client, event_payload(status="completed"))
    transfer.refresh_from_db()
    updated_at_after_first = transfer.updated_at

    second = post_webhook(api_client, event_payload(status="completed"))

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    assert ProviderEvent.objects.count() == 1
    transfer.refresh_from_db()
    assert transfer.status == "completed"
    assert transfer.updated_at == updated_at_after_first


@pytest.mark.django_db
def test_scenario_b_completed_then_failed_keeps_completed(api_client):
    transfer = make_transfer()

    completed = post_webhook(
        api_client,
        event_payload(event_id="evt_b1", status="completed"),
    )
    failed = post_webhook(
        api_client,
        event_payload(event_id="evt_b2", status="failed"),
    )

    assert completed.status_code == status.HTTP_200_OK
    assert failed.status_code == status.HTTP_200_OK
    transfer.refresh_from_db()
    assert transfer.status == "completed"
    assert ProviderEvent.objects.get(event_id="evt_b1").outcome == "applied"
    assert ProviderEvent.objects.get(event_id="evt_b2").outcome == "ignored_terminal"


@pytest.mark.django_db
def test_scenario_c_unknown_provider_transfer_id_returns_404(api_client):
    response = post_webhook(
        api_client,
        event_payload(provider_transfer_id="prov_unknown"),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert ProviderEvent.objects.count() == 0


@pytest.mark.django_db
def test_scenario_c_pending_transfer_with_provider_id_rejects_409(api_client):
    transfer = make_transfer(status="pending")

    response = post_webhook(api_client, event_payload())

    assert response.status_code == status.HTTP_409_CONFLICT
    assert ProviderEvent.objects.count() == 0
    transfer.refresh_from_db()
    assert transfer.status == "pending"


@pytest.mark.django_db
def test_scenario_d_different_completed_events_same_provider_id_are_noop(api_client):
    transfer = make_transfer()

    first = post_webhook(
        api_client,
        event_payload(event_id="evt_d1", status="completed"),
    )
    second = post_webhook(
        api_client,
        event_payload(event_id="evt_d2", status="completed"),
    )

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_200_OK
    transfer.refresh_from_db()
    assert transfer.status == "completed"
    assert ProviderEvent.objects.get(event_id="evt_d1").outcome == "applied"
    assert ProviderEvent.objects.get(event_id="evt_d2").outcome == "ignored_terminal"


@pytest.mark.django_db
def test_scenario_e_cancel_after_submit_returns_409(api_client):
    transfer = make_transfer(status="pending", provider_transfer_id=None)

    submitted = api_client.post(f"/api/transfers/{transfer.pk}/submit/", format="json")
    cancelled = api_client.post(f"/api/transfers/{transfer.pk}/cancel/", format="json")

    assert submitted.status_code == status.HTTP_200_OK
    assert cancelled.status_code == status.HTTP_409_CONFLICT
    transfer.refresh_from_db()
    assert transfer.status == "processing"


@pytest.mark.django_db
def test_reusing_event_id_with_different_payload_returns_409(api_client):
    transfer = make_transfer()

    first = post_webhook(
        api_client,
        event_payload(event_id="evt_dup", status="completed"),
    )
    conflicting = post_webhook(
        api_client,
        event_payload(event_id="evt_dup", status="failed"),
    )

    assert first.status_code == status.HTTP_200_OK
    assert conflicting.status_code == status.HTTP_409_CONFLICT
    assert ProviderEvent.objects.count() == 1
    transfer.refresh_from_db()
    assert transfer.status == "completed"


@pytest.mark.django_db
def test_signature_is_computed_from_raw_request_body(api_client):
    make_transfer()
    body = (
        b'{"event_id":"evt_raw","provider_transfer_id":"prov_abc","status":"completed"}'
    )
    assert json.dumps(json.loads(body)).encode("utf-8") != body

    response = api_client.post(
        WEBHOOK_URL,
        data=body,
        content_type="application/json",
        HTTP_X_PROVIDER_SIGNATURE=signature_for(body),
    )

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_malformed_json_returns_400(api_client):
    make_transfer()
    body = b"this is not json"
    response = api_client.post(
        WEBHOOK_URL,
        data=body,
        content_type="application/json",
        HTTP_X_PROVIDER_SIGNATURE=signature_for(body),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert ProviderEvent.objects.count() == 0


@pytest.mark.django_db
def test_invalid_payload_fields_return_400(api_client):
    make_transfer()

    response = post_webhook(
        api_client,
        event_payload(status="pending"),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert ProviderEvent.objects.count() == 0
