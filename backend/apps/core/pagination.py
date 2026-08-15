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

    def get_paginated_response_schema(self, schema):
        """Describe the actual envelope shape to drf-spectacular.

        Without this override, drf-spectacular assumes the stock DRF
        ``{count, next, previous, results}`` pagination shape, which doesn't
        match what :meth:`get_paginated_response` returns above and produces
        a schema/example mismatch in the generated docs.
        """
        return {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "message": {"type": "string", "example": ""},
                "response_code": {"type": "integer", "example": 200},
                "data": schema,
                "pagination": {
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "example": 123,
                        },
                        "next": {
                            "type": "string",
                            "format": "uri",
                            "nullable": True,
                            "example": "http://api.example.org/transfers/?page=4",
                        },
                        "previous": {
                            "type": "string",
                            "format": "uri",
                            "nullable": True,
                            "example": "http://api.example.org/transfers/?page=2",
                        },
                    },
                },
            },
        }
