from rest_framework.response import Response


class ResponseMixin:
    """Provide a consistent response envelope for API views.

    The envelope shape is:

        {"success", "message", "response_code", "data"[, "pagination"]}

    This mixin is a shared building block; views are wired to it in a
    later task.
    """

    def get_response(
        self,
        data=None,
        message="",
        success=True,
        response_code=200,
        pagination=None,
    ):
        payload = {
            "success": success,
            "message": message,
            "response_code": response_code,
            "data": data,
        }
        if pagination is not None:
            payload["pagination"] = pagination
        return Response(payload, status=response_code)
