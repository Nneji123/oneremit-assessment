from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Default pagination for list endpoints. Not wired into views yet."""

    page_size = 20
