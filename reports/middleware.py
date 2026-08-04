from typing import Callable


class RenameFormatQueryMiddleware:
    """Middleware to rename `format` query param for known export values.

    Django REST Framework treats `format` specially for content-negotiation and
    will return 404 for unknown formats. This middleware renames `format`
    to `file` when the value looks like an export type (pdf, excel, xlsx, xls),
    leaving other values untouched.
    """

    EXPORT_FORMATS = {"pdf", "excel", "xlsx", "xls"}

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request):
        try:
            fmt = request.GET.get("format")
            if fmt and fmt.lower() in self.EXPORT_FORMATS:
                # QueryDict is immutable by default; copy and replace
                q = request.GET.copy()
                q.pop("format", None)
                q["file"] = fmt
                request.GET = q
        except Exception:
            # Best-effort: do not break requests if anything goes wrong
            pass

        return self.get_response(request)
