from django.urls import path
from rest_framework.routers import SimpleRouter

from transfers.views import ProviderWebhookView, TransferViewSet

router = SimpleRouter()
router.register(r"transfers", TransferViewSet, basename="transfer")

urlpatterns = [
    path("webhooks/provider/", ProviderWebhookView.as_view(), name="provider-webhook"),
]

urlpatterns += router.urls
