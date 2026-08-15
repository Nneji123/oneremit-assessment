import json

from core.mixins import ResponseMixin
from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from transfers.exceptions import (
    DuplicateProviderEvent,
    IdempotencyConflict,
    InvalidTransferTransition,
    ProviderEventConflict,
    TransferNotFound,
    TransferNotSubmitted,
    UnknownProviderTransfer,
)
from transfers.serializers import (
    CreateTransferSerializer,
    ProviderWebhookSerializer,
    SimulateProviderEventSerializer,
    TransferSerializer,
)
from transfers.services import (
    cancel_transfer,
    create_transfer,
    process_provider_event,
    simulate_provider_event,
    submit_transfer,
    verify_provider_signature,
)

_TRANSFER_EXAMPLE = {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "reference": "TRF-9c2f6a1b4e3d4a2f8b6c7d8e9f0a1b2c",
    "amount": "150.00",
    "currency": "NGN",
    "recipient_ref": "Jane Doe - Access Bank 0123456789",
    "status": "pending",
    "provider_transfer_id": None,
    "created_at": "2026-08-15T09:12:00Z",
    "updated_at": "2026-08-15T09:12:00Z",
}


def _envelope(data=None, message="", success=True, response_code=200, pagination=None):
    payload = {
        "success": success,
        "message": message,
        "response_code": response_code,
        "data": data,
    }
    if pagination is not None:
        payload["pagination"] = pagination
    return payload


@extend_schema_view(
    list=extend_schema(
        tags=["Transfers"],
        summary="List transfers",
        description=(
            "Returns a paginated list of transfers, most recently created first. "
            "Use the `page` and `page_size` query parameters to page through results."
        ),
        parameters=[
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Page number to fetch (defaults to 1).",
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Number of transfers per page (defaults to 20).",
            ),
        ],
        examples=[
            # drf-spectacular auto-nests a single list-response example into
            # the paginated envelope (data/pagination) declared by
            # StandardResultsSetPagination.get_paginated_response_schema, so
            # this value must be one raw transfer item, not the full envelope.
            OpenApiExample(
                "Transfer",
                summary="One transfer as it appears in the paginated list",
                value=_TRANSFER_EXAMPLE,
                response_only=True,
            ),
        ],
    ),
)
class TransferViewSet(
    ResponseMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = TransferSerializer.Meta.model.objects.all()
    serializer_class = TransferSerializer
    authentication_classes = []
    permission_classes = []
    http_method_names = ["get", "post", "head", "options"]
    lookup_field = "pk"

    def get_serializer_class(self):
        if self.action == "create":
            return CreateTransferSerializer
        return TransferSerializer

    def http_method_not_allowed(self, request, *args, **kwargs):
        return self.get_response(
            data=None,
            message="Method not allowed.",
            success=False,
            response_code=405,
        )

    @extend_schema(
        tags=["Transfers"],
        summary="Create a transfer",
        description=(
            "Creates a new payout transfer in the `pending` state. Requires a "
            "client-generated `Idempotency-Key` header — replaying the same key "
            "with the same body returns the original transfer (200); reusing the "
            "key with a different body is rejected as a conflict (409)."
        ),
        request=CreateTransferSerializer,
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.HEADER,
                required=True,
                description=(
                    "Client-generated unique key (e.g. a UUID) that makes retried "
                    "create requests safe to resend."
                ),
            )
        ],
        responses={
            200: TransferSerializer,
            201: TransferSerializer,
            400: OpenApiResponse(description="Invalid request."),
            409: OpenApiResponse(description="Idempotency conflict."),
        },
        examples=[
            OpenApiExample(
                "Create transfer",
                summary="Send 150.00 NGN",
                value={
                    "amount": "150.00",
                    "currency": "NGN",
                    "recipient_ref": "Jane Doe - Access Bank 0123456789",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Created",
                summary="New transfer accepted",
                value=_envelope(
                    data=_TRANSFER_EXAMPLE,
                    message="Transfer created",
                    response_code=201,
                ),
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Idempotent replay",
                summary="Same Idempotency-Key and body resent",
                value=_envelope(
                    data=_TRANSFER_EXAMPLE,
                    message="Idempotent replay",
                    response_code=200,
                ),
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Idempotency conflict",
                summary="Same key reused with a different body",
                value=_envelope(
                    data=None,
                    success=False,
                    message="Idempotency-Key conflict: request body differs from original.",
                    response_code=409,
                ),
                response_only=True,
                status_codes=["409"],
            ),
        ],
    )
    def create(self, request, *args, **kwargs):
        idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY", "").strip()
        if not idempotency_key:
            return self.get_response(
                data=None,
                message="Idempotency-Key header is required.",
                success=False,
                response_code=status.HTTP_400_BAD_REQUEST,
            )
        if len(idempotency_key) > 255:
            return self.get_response(
                data=None,
                message="Idempotency-Key must be 255 characters or fewer.",
                success=False,
                response_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CreateTransferSerializer(data=request.data)
        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))
            detail = first_error[0] if isinstance(first_error, list) else first_error
            return self.get_response(
                data=None,
                message=str(detail),
                success=False,
                response_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            transfer, created = create_transfer(
                serializer.validated_data, idempotency_key
            )
        except IdempotencyConflict as exc:
            return self.get_response(
                data=None,
                message=str(exc),
                success=False,
                response_code=status.HTTP_409_CONFLICT,
            )

        out = TransferSerializer(transfer)
        return self.get_response(
            data=out.data,
            message="Transfer created" if created else "Idempotent replay",
            success=True,
            response_code=(status.HTTP_201_CREATED if created else status.HTTP_200_OK),
        )

    @extend_schema(
        tags=["Transfers"],
        summary="Get a transfer",
        description="Returns a single transfer by its id.",
        request=None,
        responses={
            200: TransferSerializer,
            404: OpenApiResponse(description="Transfer not found."),
        },
        examples=[
            OpenApiExample(
                "Transfer",
                summary="Existing transfer",
                value=_envelope(data=_TRANSFER_EXAMPLE),
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Not found",
                summary="Unknown transfer id",
                value=_envelope(
                    data=None,
                    success=False,
                    message="Transfer not found.",
                    response_code=404,
                ),
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except Http404:
            return self.get_response(
                data=None,
                message="Transfer not found.",
                success=False,
                response_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(instance)
        return self.get_response(
            data=serializer.data,
            success=True,
            response_code=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Transfers"],
        summary="Submit a transfer to the provider",
        description=(
            "Moves a `pending` transfer to `processing` by submitting it to the "
            "payout provider. Only valid while the transfer is `pending`."
        ),
        request=None,
        responses={
            200: TransferSerializer,
            404: OpenApiResponse(description="Transfer not found."),
            409: OpenApiResponse(description="Invalid transfer state."),
        },
        examples=[
            OpenApiExample(
                "Submitted",
                summary="Transfer moved to processing",
                value=_envelope(
                    data={**_TRANSFER_EXAMPLE, "status": "processing"},
                    message="Transfer submitted",
                ),
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Invalid state",
                summary="Transfer is not pending",
                value=_envelope(
                    data=None,
                    success=False,
                    message="Cannot transition Transfer from 'completed' to 'processing'.",
                    response_code=409,
                ),
                response_only=True,
                status_codes=["409"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        try:
            locked = submit_transfer(pk)
        except TransferNotFound:
            return self.get_response(
                data=None,
                message="Transfer not found.",
                success=False,
                response_code=status.HTTP_404_NOT_FOUND,
            )
        except InvalidTransferTransition as exc:
            return self.get_response(
                data=None,
                message=str(exc),
                success=False,
                response_code=status.HTTP_409_CONFLICT,
            )

        out = TransferSerializer(locked)
        return self.get_response(
            data=out.data,
            message="Transfer submitted",
            success=True,
            response_code=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Transfers"],
        summary="Cancel a transfer",
        description=(
            "Cancels a `pending` transfer before it has been submitted to the "
            "provider. Transfers that are already `processing` or terminal "
            "cannot be cancelled."
        ),
        request=None,
        responses={
            200: TransferSerializer,
            404: OpenApiResponse(description="Transfer not found."),
            409: OpenApiResponse(description="Invalid transfer state."),
        },
        examples=[
            OpenApiExample(
                "Cancelled",
                summary="Transfer cancelled",
                value=_envelope(
                    data={**_TRANSFER_EXAMPLE, "status": "cancelled"},
                    message="Transfer cancelled",
                ),
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Invalid state",
                summary="Transfer is already processing",
                value=_envelope(
                    data=None,
                    success=False,
                    message="Cannot transition Transfer from 'processing' to 'cancelled'.",
                    response_code=409,
                ),
                response_only=True,
                status_codes=["409"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        try:
            locked = cancel_transfer(pk)
        except TransferNotFound:
            return self.get_response(
                data=None,
                message="Transfer not found.",
                success=False,
                response_code=status.HTTP_404_NOT_FOUND,
            )
        except InvalidTransferTransition as exc:
            return self.get_response(
                data=None,
                message=str(exc),
                success=False,
                response_code=status.HTTP_409_CONFLICT,
            )

        out = TransferSerializer(locked)
        return self.get_response(
            data=out.data,
            message="Transfer cancelled",
            success=True,
            response_code=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Transfers"],
        summary="Simulate a provider webhook outcome",
        description=(
            "Local demo helper that drives a `processing` transfer straight to a "
            "terminal `completed` or `failed` state, without a signed provider "
            "webhook. Intended for exercising the UI/websocket flow in "
            "development; use the real `/api/webhooks/provider/` endpoint for "
            "actual provider callbacks."
        ),
        request=SimulateProviderEventSerializer,
        responses={
            200: TransferSerializer,
            400: OpenApiResponse(description="Invalid status."),
            404: OpenApiResponse(description="Transfer not found."),
            409: OpenApiResponse(description="Transfer is not processing."),
        },
        examples=[
            OpenApiExample(
                "Simulate success",
                summary="Mark the transfer as completed",
                value={"status": "completed"},
                request_only=True,
            ),
            OpenApiExample(
                "Simulate failure",
                summary="Mark the transfer as failed",
                value={"status": "failed"},
                request_only=True,
            ),
            OpenApiExample(
                "Applied",
                summary="Transfer moved to a terminal state",
                value=_envelope(
                    data={**_TRANSFER_EXAMPLE, "status": "completed"},
                    message="Simulated provider event applied.",
                ),
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Not processing",
                summary="Transfer has not been submitted yet",
                value=_envelope(
                    data=None,
                    success=False,
                    message=(
                        "Cannot simulate a provider event for transfer in state "
                        "'pending'; only 'processing' transfers can be simulated."
                    ),
                    response_code=409,
                ),
                response_only=True,
                status_codes=["409"],
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="simulate-webhook")
    def simulate_webhook(self, request, pk=None):
        serializer = SimulateProviderEventSerializer(data=request.data)
        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))
            detail = first_error[0] if isinstance(first_error, list) else first_error
            return self.get_response(
                data=None,
                message=str(detail),
                success=False,
                response_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            locked = simulate_provider_event(pk, serializer.validated_data["status"])
        except TransferNotFound:
            return self.get_response(
                data=None,
                message="Transfer not found.",
                success=False,
                response_code=status.HTTP_404_NOT_FOUND,
            )
        except InvalidTransferTransition as exc:
            return self.get_response(
                data=None,
                message=str(exc),
                success=False,
                response_code=status.HTTP_409_CONFLICT,
            )

        out = TransferSerializer(locked)
        return self.get_response(
            data=out.data,
            message="Simulated provider event applied.",
            success=True,
            response_code=status.HTTP_200_OK,
        )


class ProviderWebhookView(ResponseMixin, APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        tags=["Webhooks"],
        summary="Receive a payout provider webhook",
        description=(
            "Applies a provider-signed status update to a `processing` transfer, "
            "moving it to `completed` or `failed`. The request body must be "
            "signed: compute `hmac_sha256(PROVIDER_WEBHOOK_SECRET, raw_body)` and "
            "send it hex-encoded as `sha256=<digest>` in the "
            "`X-Provider-Signature` header. Events are deduplicated by "
            "`event_id` — replaying the same event id with an identical payload "
            "returns 200 without reapplying it."
        ),
        request=ProviderWebhookSerializer,
        parameters=[
            OpenApiParameter(
                name="X-Provider-Signature",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.HEADER,
                required=True,
                description=(
                    "HMAC-SHA256 signature of the raw request body, formatted as "
                    "`sha256=<hex digest>`, keyed with PROVIDER_WEBHOOK_SECRET."
                ),
            )
        ],
        responses={
            200: OpenApiResponse(description="Event applied, duplicate, or ignored."),
            400: OpenApiResponse(description="Malformed JSON or invalid payload."),
            401: OpenApiResponse(description="Missing or invalid signature."),
            404: OpenApiResponse(description="Unknown provider transfer id."),
            409: OpenApiResponse(description="Conflicting event or illegal state."),
        },
        examples=[
            OpenApiExample(
                "Provider event",
                summary="Provider reports a completed payout",
                value={
                    "event_id": "evt_8f1e6b2c9a3d4e5f6a7b8c9d0e1f2a3b",
                    "provider_transfer_id": "prov_5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c",
                    "status": "completed",
                    "occurred_at": "2026-08-15T09:15:00Z",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Event recorded",
                summary="Event applied",
                value=_envelope(data=None, message="Provider event recorded."),
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Invalid signature",
                summary="Signature missing or does not match the body",
                value=_envelope(
                    data=None,
                    success=False,
                    message="Invalid provider signature.",
                    response_code=401,
                ),
                response_only=True,
                status_codes=["401"],
            ),
            OpenApiExample(
                "Unknown transfer",
                summary="provider_transfer_id does not match any transfer",
                value=_envelope(
                    data=None,
                    success=False,
                    message="Unknown provider transfer id.",
                    response_code=404,
                ),
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        signature = request.META.get("HTTP_X_PROVIDER_SIGNATURE", "")
        if not verify_provider_signature(request.body, signature):
            return self.get_response(
                data=None,
                message="Invalid provider signature.",
                success=False,
                response_code=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            payload = json.loads(request.body)
        except (ValueError, TypeError, UnicodeDecodeError):
            return self.get_response(
                data=None,
                message="Malformed JSON body.",
                success=False,
                response_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProviderWebhookSerializer(data=payload)
        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))
            detail = first_error[0] if isinstance(first_error, list) else first_error
            return self.get_response(
                data=None,
                message=str(detail),
                success=False,
                response_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            process_provider_event(serializer.validated_data)
        except DuplicateProviderEvent:
            return self.get_response(
                data=None,
                message="Duplicate event.",
                success=True,
                response_code=status.HTTP_200_OK,
            )
        except ProviderEventConflict:
            return self.get_response(
                data=None,
                message="Event id conflict: payload differs.",
                success=False,
                response_code=status.HTTP_409_CONFLICT,
            )
        except UnknownProviderTransfer:
            return self.get_response(
                data=None,
                message="Unknown provider transfer id.",
                success=False,
                response_code=status.HTTP_404_NOT_FOUND,
            )
        except TransferNotSubmitted:
            return self.get_response(
                data=None,
                message="Transfer has not been submitted.",
                success=False,
                response_code=status.HTTP_409_CONFLICT,
            )
        except InvalidTransferTransition as exc:
            return self.get_response(
                data=None,
                message=str(exc),
                success=False,
                response_code=status.HTTP_409_CONFLICT,
            )

        return self.get_response(
            data=None,
            message="Provider event recorded.",
            success=True,
            response_code=status.HTTP_200_OK,
        )
