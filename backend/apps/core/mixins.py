from rest_framework.response import Response


class ResponseMixin:
    """Provide a consistent response envelope for API views.

    The envelope shape is:

        {"success", "message", "response_code", "data"[, "pagination"]}

    Views that use this mixin wrap every response with :meth:`get_response`;
    the list endpoint keeps the envelope produced by the default pagination
    class.
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

    def method_not_allowed(self, request, *args, **kwargs):
        return self.get_response(
            data=None,
            message="Method not allowed.",
            success=False,
            response_code=405,
        )
