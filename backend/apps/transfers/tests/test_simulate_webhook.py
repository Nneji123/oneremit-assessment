from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from transfers.models import ProviderEvent, Transfer

TRANSFER_URL = "/api/transfers/"


@pytest.fixture
def api_client():
    return APIClient()


def make_transfer(status="processing", provider_transfer_id="prov_sim", **overrides):
    fields = {
        "amount": Decimal("100.00"),
        "currency": "NGN",
        "recipient_ref": "recipient-123",
        "status": status,
        "provider_transfer_id": provider_transfer_id,
        "idempotency_key": f"key-{provider_transfer_id}",
        "request_fingerprint": f"fingerprint-{provider_transfer_id}",
    }
    fields.update(overrides)
    return Transfer.objects.create(**fields)


def simulate(client, transfer_id, status_name="completed"):
    return client.post(
        f"{TRANSFER_URL}{transfer_id}/simulate-webhook/",
        {"status": status_name},
        format="json",
    )


def assert_envelope_error(response, response_code):
    assert response.status_code == response_code
    assert response.data["success"] is False
    assert response.data["response_code"] == response_code
    assert isinstance(response.data["message"], str) and response.data["message"]
    assert response.data["data"] is None


@pytest.mark.django_db
def test_simulate_completed_moves_processing_transfer_to_completed(api_client):
    transfer = make_transfer()

    response = simulate(api_client, transfer.pk, "completed")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    assert response.data["message"] == "Simulated provider event applied."
    assert response.data["data"]["id"] == str(transfer.pk)
    assert response.data["data"]["status"] == "completed"
    transfer.refresh_from_db()
    assert transfer.status == "completed"
    event = ProviderEvent.objects.get(transfer_id=transfer.pk)
    assert event.provider_status == "completed"
    assert event.outcome == "applied"
    assert event.event_id.startswith("sim_")


@pytest.mark.django_db
def test_simulate_failed_moves_processing_transfer_to_failed(api_client):
    transfer = make_transfer()

    response = simulate(api_client, transfer.pk, "failed")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    assert response.data["data"]["status"] == "failed"
    transfer.refresh_from_db()
    assert transfer.status == "failed"
    event = ProviderEvent.objects.get(transfer_id=transfer.pk)
    assert event.provider_status == "failed"


@pytest.mark.django_db
def test_simulate_rejects_pending_transfer(api_client):
    transfer = make_transfer(status="pending", provider_transfer_id=None)

    response = simulate(api_client, transfer.pk, "completed")

    assert_envelope_error(response, status.HTTP_409_CONFLICT)
    assert transfer.status == "pending"
    assert ProviderEvent.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("terminal_status", ["completed", "failed", "cancelled"])
def test_simulate_rejects_terminal_transfer(api_client, terminal_status):
    transfer = make_transfer(status=terminal_status)

    response = simulate(api_client, transfer.pk, "completed")

    assert_envelope_error(response, status.HTTP_409_CONFLICT)
    assert ProviderEvent.objects.count() == 0


@pytest.mark.django_db
def test_simulate_rejects_invalid_status(api_client):
    transfer = make_transfer()

    response = simulate(api_client, transfer.pk, "pending")

    assert_envelope_error(response, status.HTTP_400_BAD_REQUEST)
    assert transfer.status == "processing"
    assert ProviderEvent.objects.count() == 0


@pytest.mark.django_db
def test_simulate_unknown_transfer_returns_404(api_client):
    response = simulate(
        api_client,
        "00000000-0000-0000-0000-000000000000",
        "completed",
    )

    assert_envelope_error(response, status.HTTP_404_NOT_FOUND)
