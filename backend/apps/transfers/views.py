import json

from core.mixins import ResponseMixin
from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from transfers.serializers import (
    CreateTransferSerializer,
    ProviderWebhookSerializer,
    TransferSerializer,
)
from transfers.services import (
    DuplicateProviderEvent,
    IdempotencyConflict,
    InvalidTransferTransition,
    ProviderEventConflict,
    TransferNotFound,
    TransferNotSubmitted,
    UnknownProviderTransfer,
    cancel_transfer,
    create_transfer,
    process_provider_event,
    submit_transfer,
    verify_provider_signature,
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
        request=None,
        responses={
            200: TransferSerializer,
            404: OpenApiResponse(description="Transfer not found."),
        },
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


class ProviderWebhookView(ResponseMixin, APIView):
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
