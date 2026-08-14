from decimal import Decimal
from unittest import mock

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from transfers.enums import TransferStatus
from transfers.models import Transfer
from transfers.services import InvalidTransferTransition

TRANSFER_URL = "/api/transfers/"


@pytest.fixture
def api_client():
    return APIClient()


def transfer_payload(**overrides):
    payload = {
        "amount": "100.00",
        "currency": "ngn",
        "recipient_ref": "recipient-123",
    }
    payload.update(overrides)
    return payload


def create_transfer(api_client, key="key-123", **payload_overrides):
    return api_client.post(
        TRANSFER_URL,
        transfer_payload(**payload_overrides),
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def assert_envelope_error(response, response_code):
    assert response.status_code == response_code
    assert response.data["success"] is False
    assert response.data["response_code"] == response_code
    assert isinstance(response.data["message"], str) and response.data["message"]
    assert response.data["data"] is None


@pytest.mark.django_db
def test_create_transfer_requires_idempotency_key(api_client):
    response = api_client.post(TRANSFER_URL, transfer_payload(), format="json")

    assert_envelope_error(response, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
def test_create_transfer_starts_pending(api_client):
    response = create_transfer(api_client)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["success"] is True
    assert response.data["response_code"] == status.HTTP_201_CREATED
    assert response.data["message"] == "Transfer created"
    assert response.data["data"]["status"] == "pending"
    assert response.data["data"]["currency"] == "NGN"
    assert response.data["data"]["provider_transfer_id"] is None
    assert response.data["data"]["reference"].startswith("TRF-")
    assert Transfer.objects.get(pk=response.data["data"]["id"]).status == "pending"


@pytest.mark.django_db
def test_replaying_same_key_and_same_body_returns_original_transfer(api_client):
    first = create_transfer(api_client, key="replay-key")
    replay = create_transfer(api_client, key="replay-key")

    assert first.status_code == status.HTTP_201_CREATED
    assert replay.status_code == status.HTTP_200_OK
    assert replay.data["data"] == first.data["data"]
    assert Transfer.objects.count() == 1


@pytest.mark.django_db
def test_reusing_key_with_different_body_returns_409(api_client):
    first = create_transfer(api_client, key="conflict-key")
    conflict = create_transfer(
        api_client,
        key="conflict-key",
        amount="101.00",
    )

    assert first.status_code == status.HTTP_201_CREATED
    assert conflict.status_code == status.HTTP_409_CONFLICT
    assert conflict.data["success"] is False
    assert conflict.data["message"] == (
        "Idempotency-Key conflict: request body differs from original."
    )
    assert conflict.data["data"] is None
    assert Transfer.objects.count() == 1
    assert Transfer.objects.get(pk=first.data["data"]["id"]).amount == Decimal("100.00")


@pytest.mark.django_db
def test_same_semantic_body_replays_even_if_json_key_order_differs(api_client):
    first = api_client.post(
        TRANSFER_URL,
        {"amount": "100.0", "currency": "ngn", "recipient_ref": "recipient-123"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="order-key",
    )
    replay = api_client.post(
        TRANSFER_URL,
        {"recipient_ref": "recipient-123", "currency": "NGN", "amount": "100.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="order-key",
    )

    assert first.status_code == status.HTTP_201_CREATED
    assert replay.status_code == status.HTTP_200_OK
    assert replay.data["data"]["id"] == first.data["data"]["id"]


@pytest.mark.django_db
def test_idempotency_key_longer_than_model_max_returns_400(api_client):
    response = create_transfer(api_client, key="k" * 256)

    assert_envelope_error(response, status.HTTP_400_BAD_REQUEST)
    assert Transfer.objects.count() == 0


@pytest.mark.django_db
def test_create_rejects_non_positive_amount(api_client):
    response = create_transfer(api_client, amount="0.00")

    assert_envelope_error(response, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
def test_create_rejects_amount_with_more_than_two_fractional_places(api_client):
    response = create_transfer(api_client, amount="10.555")

    assert_envelope_error(response, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
def test_create_rejects_unsupported_currency(api_client):
    response = create_transfer(api_client, currency="CAD")

    assert_envelope_error(response, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
def test_submit_moves_pending_transfer_to_processing_and_assigns_provider_id(
    api_client,
):
    created = create_transfer(api_client)

    response = api_client.post(
        f"{TRANSFER_URL}{created.data['data']['id']}/submit/",
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    assert response.data["message"] == "Transfer submitted"
    assert response.data["data"]["status"] == "processing"
    assert response.data["data"]["provider_transfer_id"].startswith("prov_")
    transfer = Transfer.objects.get(pk=created.data["data"]["id"])
    assert transfer.status == "processing"
    assert (
        transfer.provider_transfer_id == response.data["data"]["provider_transfer_id"]
    )


@pytest.mark.django_db
def test_submit_rejects_non_pending_transfer(api_client):
    created = create_transfer(api_client)
    api_client.post(
        f"{TRANSFER_URL}{created.data['data']['id']}/submit/",
        format="json",
    )

    response = api_client.post(
        f"{TRANSFER_URL}{created.data['data']['id']}/submit/",
        format="json",
    )

    assert_envelope_error(response, status.HTTP_409_CONFLICT)


@pytest.mark.django_db
def test_cancel_moves_pending_transfer_to_cancelled(api_client):
    created = create_transfer(api_client)

    response = api_client.post(
        f"{TRANSFER_URL}{created.data['data']['id']}/cancel/",
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    assert response.data["message"] == "Transfer cancelled"
    assert response.data["data"]["status"] == "cancelled"


@pytest.mark.django_db
def test_cancel_after_submit_returns_409(api_client):
    created = create_transfer(api_client)
    api_client.post(
        f"{TRANSFER_URL}{created.data['data']['id']}/submit/",
        format="json",
    )

    response = api_client.post(
        f"{TRANSFER_URL}{created.data['data']['id']}/cancel/",
        format="json",
    )

    assert_envelope_error(response, status.HTTP_409_CONFLICT)


@pytest.mark.django_db
@pytest.mark.parametrize("terminal_status", ["completed", "failed", "cancelled"])
def test_cancel_rejects_terminal_transfer(api_client, terminal_status):
    transfer = Transfer.objects.create(
        amount=Decimal("100.00"),
        currency="NGN",
        recipient_ref="recipient-123",
        status=terminal_status,
        idempotency_key=f"{terminal_status}-key",
        request_fingerprint=f"{terminal_status}-fingerprint",
    )

    response = api_client.post(f"{TRANSFER_URL}{transfer.pk}/cancel/", format="json")

    assert_envelope_error(response, status.HTTP_409_CONFLICT)


@pytest.mark.django_db
def test_list_returns_newest_first(api_client):
    first = create_transfer(api_client, key="first-key", recipient_ref="first")
    second = create_transfer(api_client, key="second-key", recipient_ref="second")

    response = api_client.get(TRANSFER_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    assert [item["id"] for item in response.data["data"]] == [
        second.data["data"]["id"],
        first.data["data"]["id"],
    ]
    assert response.data["pagination"]["count"] == 2


@pytest.mark.django_db
def test_detail_returns_transfer(api_client):
    created = create_transfer(api_client)

    response = api_client.get(f"{TRANSFER_URL}{created.data['data']['id']}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    assert response.data["data"] == created.data["data"]


@pytest.mark.django_db
def test_unknown_transfer_id_returns_404(api_client):
    response = api_client.get(f"{TRANSFER_URL}00000000-0000-0000-0000-000000000000/")

    assert_envelope_error(response, status.HTTP_404_NOT_FOUND)


@pytest.mark.django_db
@pytest.mark.parametrize("action_name", ["submit", "cancel"])
def test_unknown_transfer_action_returns_404(api_client, action_name):
    response = api_client.post(
        f"{TRANSFER_URL}00000000-0000-0000-0000-000000000000/{action_name}/",
        format="json",
    )

    assert_envelope_error(response, status.HTTP_404_NOT_FOUND)


@pytest.mark.django_db
@pytest.mark.parametrize("action_name", ["submit", "cancel"])
def test_malformed_transfer_uuid_action_returns_404(api_client, action_name):
    response = api_client.post(
        f"{TRANSFER_URL}not-a-valid-uuid/{action_name}/",
        format="json",
    )

    assert_envelope_error(response, status.HTTP_404_NOT_FOUND)


@mock.patch("transfers.views.transition_transfer")
@pytest.mark.django_db
def test_submit_delegates_transition_to_service(mock_transition, api_client):
    created = create_transfer(api_client)
    mock_transition.side_effect = InvalidTransferTransition(
        "Cannot transition from 'pending' to 'processing'."
    )

    response = api_client.post(
        f"{TRANSFER_URL}{created.data['data']['id']}/submit/",
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["success"] is False
    assert response.data["message"] == (
        "Cannot transition from 'pending' to 'processing'."
    )
    mock_transition.assert_called_once_with(mock.ANY, TransferStatus.PROCESSING)


@pytest.mark.django_db
def test_update_and_delete_are_not_allowed(api_client):
    created = create_transfer(api_client)

    update = api_client.patch(
        f"{TRANSFER_URL}{created.data['data']['id']}/",
        {"recipient_ref": "changed"},
        format="json",
    )
    delete = api_client.delete(f"{TRANSFER_URL}{created.data['data']['id']}/")

    assert update.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert delete.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
