from rest_framework.renderers import BaseRenderer


class AnyRenderer(BaseRenderer):
    """A permissive renderer that matches any Accept header.

    This renderer does not actually render response content because the
    view returns a Django `HttpResponse`/file response directly. It's only
    used to satisfy DRF's content negotiation step so the view isn't
    rejected with 406 when the client sends e.g. `Accept: application/pdf`.
    """

    media_type = "*/*"
    format = "bin"

    def render(self, data, media_type=None, renderer_context=None):
        return b""
