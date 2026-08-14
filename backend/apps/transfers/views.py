import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from transfers.enums import ProviderEventOutcome, TransferStatus
from transfers.models import ProviderEvent, Transfer
from transfers.serializers import (
    CreateTransferSerializer,
    ProviderWebhookSerializer,
    TransferSerializer,
)
from transfers.services import InvalidTransferTransition, transition_transfer


def _fingerprint(validated_data):
    normalized = {
        "amount": format(validated_data["amount"], ".2f"),
        "currency": validated_data["currency"],
        "recipient_ref": validated_data["recipient_ref"],
    }
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _verify_provider_signature(signature, body):
    if not signature or not signature.startswith("sha256="):
        return False
    expected = signature[len("sha256=") :]
    secret = settings.PROVIDER_WEBHOOK_SECRET.encode("utf-8")
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


def _provider_payload_fingerprint(validated_data):
    canonical = {
        "event_id": validated_data["event_id"],
        "provider_transfer_id": validated_data["provider_transfer_id"],
        "status": validated_data["status"],
        "occurred_at": (
            validated_data["occurred_at"].isoformat()
            if validated_data.get("occurred_at")
            else None
        ),
    }
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


class TransferViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Transfer.objects.all()
    serializer_class = TransferSerializer
    authentication_classes = []
    permission_classes = []
    http_method_names = ["get", "post", "head", "options"]
    lookup_field = "pk"

    def get_serializer_class(self):
        if self.action == "create":
            return CreateTransferSerializer
        return TransferSerializer

    @extend_schema(
        request=CreateTransferSerializer,
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.HEADER,
                required=True,
            )
        ],
        responses={
            200: TransferSerializer,
            201: TransferSerializer,
            400: OpenApiResponse(description="Invalid request."),
            409: OpenApiResponse(description="Idempotency conflict."),
        },
    )
    def create(self, request, *args, **kwargs):
        idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY", "").strip()
        if not idempotency_key:
            return Response(
                {"detail": "Idempotency-Key header is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(idempotency_key) > 255:
            return Response(
                {"detail": "Idempotency-Key must be 255 characters or fewer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CreateTransferSerializer(data=request.data)
        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))
            detail = first_error[0] if isinstance(first_error, list) else first_error
            return Response(
                {"detail": str(detail)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated = serializer.validated_data
        fingerprint = _fingerprint(validated)

        try:
            with transaction.atomic():
                transfer = Transfer.objects.create(
                    amount=validated["amount"],
                    currency=validated["currency"],
                    recipient_ref=validated["recipient_ref"],
                    idempotency_key=idempotency_key,
                    request_fingerprint=fingerprint,
                )
            out = TransferSerializer(transfer)
            return Response(out.data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            existing = Transfer.objects.filter(idempotency_key=idempotency_key).first()
            if existing is None:
                raise
            if existing.request_fingerprint == fingerprint:
                out = TransferSerializer(existing)
                return Response(out.data, status=status.HTTP_200_OK)
            return Response(
                {
                    "detail": (
                        "Idempotency-Key conflict: request body differs from original."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

    @extend_schema(
        request=None,
        responses={
            200: TransferSerializer,
            404: OpenApiResponse(description="Transfer not found."),
            409: OpenApiResponse(description="Invalid transfer state."),
        },
    )
    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        try:
            transfer = Transfer.objects.only("pk").get(pk=pk)
        except (Transfer.DoesNotExist, ValidationError):
            return Response(
                {"detail": "Transfer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            with transaction.atomic():
                locked = transition_transfer(transfer, TransferStatus.PROCESSING)
                locked.provider_transfer_id = f"prov_{uuid.uuid4().hex}"
                locked.save(update_fields=["provider_transfer_id", "updated_at"])
        except InvalidTransferTransition as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        out = TransferSerializer(locked)
        return Response(out.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=None,
        responses={
            200: TransferSerializer,
            404: OpenApiResponse(description="Transfer not found."),
            409: OpenApiResponse(description="Invalid transfer state."),
        },
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        try:
            transfer = Transfer.objects.get(pk=pk)
            locked = transition_transfer(transfer, TransferStatus.CANCELLED)
        except (Transfer.DoesNotExist, ValidationError):
            return Response(
                {"detail": "Transfer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except InvalidTransferTransition as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )

        out = TransferSerializer(locked)
        return Response(out.data, status=status.HTTP_200_OK)


class ProviderWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        request=ProviderWebhookSerializer,
        parameters=[
            OpenApiParameter(
                name="X-Provider-Signature",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.HEADER,
                required=True,
            )
        ],
        responses={
            200: OpenApiResponse(description="Event applied, duplicate, or ignored."),
            400: OpenApiResponse(description="Malformed JSON or invalid payload."),
            401: OpenApiResponse(description="Missing or invalid signature."),
            404: OpenApiResponse(description="Unknown provider transfer id."),
            409: OpenApiResponse(description="Conflicting event or illegal state."),
        },
    )
    def post(self, request, *args, **kwargs):
        signature = request.META.get("HTTP_X_PROVIDER_SIGNATURE", "")
        if not _verify_provider_signature(signature, request.body):
            return Response(
                {"detail": "Invalid provider signature."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            payload = json.loads(request.body)
        except (ValueError, TypeError, UnicodeDecodeError):
            return Response(
                {"detail": "Malformed JSON body."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProviderWebhookSerializer(data=payload)
        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))
            detail = first_error[0] if isinstance(first_error, list) else first_error
            return Response(
                {"detail": str(detail)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated = serializer.validated_data
        event_id = validated["event_id"]
        provider_transfer_id = validated["provider_transfer_id"]
        fingerprint = _provider_payload_fingerprint(validated)

        try:
            with transaction.atomic():
                existing = (
                    ProviderEvent.objects.select_for_update()
                    .filter(event_id=event_id)
                    .first()
                )
                if existing is not None:
                    if existing.payload_fingerprint == fingerprint:
                        return Response(
                            {"detail": "Duplicate event."},
                            status=status.HTTP_200_OK,
                        )
                    return Response(
                        {"detail": "Event id conflict: payload differs."},
                        status=status.HTTP_409_CONFLICT,
                    )

                transfer = (
                    Transfer.objects.select_for_update()
                    .filter(provider_transfer_id=provider_transfer_id)
                    .first()
                )
                if transfer is None:
                    return Response(
                        {"detail": "Unknown provider transfer id."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                if transfer.status == TransferStatus.PENDING:
                    return Response(
                        {"detail": "Transfer has not been submitted."},
                        status=status.HTTP_409_CONFLICT,
                    )

                if transfer.status == TransferStatus.PROCESSING:
                    transition_transfer(transfer, validated["status"])
                    outcome = ProviderEventOutcome.APPLIED
                else:
                    outcome = ProviderEventOutcome.IGNORED_TERMINAL

                ProviderEvent.objects.create(
                    transfer=transfer,
                    event_id=event_id,
                    provider_transfer_id=provider_transfer_id,
                    provider_status=validated["status"],
                    occurred_at=validated.get("occurred_at"),
                    payload_fingerprint=fingerprint,
                    outcome=outcome,
                )
                return Response(
                    {"detail": "Provider event recorded."},
                    status=status.HTTP_200_OK,
                )
        except IntegrityError:
            with transaction.atomic():
                existing = ProviderEvent.objects.select_for_update().get(
                    event_id=event_id
                )
            if existing.payload_fingerprint == fingerprint:
                return Response(
                    {"detail": "Duplicate event."},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"detail": "Event id conflict: payload differs."},
                status=status.HTTP_409_CONFLICT,
            )
