from rest_framework.routers import SimpleRouter

from transfers.views import TransferViewSet

router = SimpleRouter()
router.register(r"transfers", TransferViewSet, basename="transfer")

urlpatterns = router.urls
