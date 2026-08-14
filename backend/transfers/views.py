import hashlib
import json
import uuid

from django.db import IntegrityError, transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from transfers.models import Transfer, TransferStatus
from transfers.serializers import CreateTransferSerializer, TransferSerializer
from transfers.services import InvalidTransferTransition, transition_transfer


def _fingerprint(validated_data):
    normalized = {
        "amount": format(validated_data["amount"], ".2f"),
        "currency": validated_data["currency"],
        "recipient_ref": validated_data["recipient_ref"],
    }
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


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
            with transaction.atomic():
                transfer = Transfer.objects.select_for_update().get(pk=pk)
                if transfer.status != TransferStatus.PENDING:
                    detail = f"Cannot submit transfer in '{transfer.status}' status."
                    return Response(
                        {"detail": detail},
                        status=status.HTTP_409_CONFLICT,
                    )
                provider_id = f"prov_{uuid.uuid4().hex}"
                transfer.provider_transfer_id = provider_id
                transfer.status = TransferStatus.PROCESSING
                transfer.save(
                    update_fields=["provider_transfer_id", "status", "updated_at"]
                )
        except Transfer.DoesNotExist:
            return Response(
                {"detail": "Transfer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        out = TransferSerializer(transfer)
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
        except Transfer.DoesNotExist:
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
