class BaseHTTPMiddleware:
    def __init__(self, app=None):
        self.app = app

    async def dispatch(self, request, call_next):
        return await call_next(request)
