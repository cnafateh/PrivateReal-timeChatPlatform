from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.http import JsonResponse

from .services import MAX_FILE_SIZE


class LimitedUploadHandler(FileUploadHandler):
    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.received = 0

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        if self.received > MAX_FILE_SIZE:
            self.request.upload_too_large = True
            raise StopUpload(connection_reset=False)
        return raw_data

    def file_complete(self, file_size):
        return None


class UploadLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path.startswith("/api/chats/"):
            try:
                length = int(request.META.get("CONTENT_LENGTH") or 0)
            except ValueError:
                return JsonResponse({"error": "Invalid request length."}, status=400)
            if length > 6 * 1024 * 1024:
                return JsonResponse({"error": "Files may not exceed 5 MB."}, status=413)
            request.upload_handlers.insert(0, LimitedUploadHandler(request))
        response = self.get_response(request)
        if getattr(request, "upload_too_large", False):
            return JsonResponse({"error": "Files may not exceed 5 MB."}, status=400)
        return response
