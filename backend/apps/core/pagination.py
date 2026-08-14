from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """Default pagination for list endpoints.

    Wraps paginated results in the standard response envelope so every list
    response has the same ``{success, message, response_code, data,
    pagination}`` shape as the rest of the API.
    """

    page_size = 20
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        return Response(
            {
                "success": True,
                "message": "",
                "response_code": 200,
                "data": data,
                "pagination": {
                    "count": self.page.paginator.count,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                },
            },
            status=200,
        )
