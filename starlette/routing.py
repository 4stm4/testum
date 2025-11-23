import re
import asyncio
from starlette.responses import JSONResponse


def compile_path(path: str):
    segments = path.split("/")
    pattern_parts = []
    for segment in segments:
        if not segment:
            continue
        if segment.startswith("{") and segment.endswith("}"):
            inner = segment[1:-1]
            if ":uuid" in inner:
                name = inner.split(":", 1)[0]
                pattern_parts.append(rf"(?P<{name}>[0-9a-fA-F-]{{36}})")
            else:
                name = inner
                pattern_parts.append(rf"(?P<{name}>[^/]+)")
        else:
            pattern_parts.append(re.escape(segment))
    pattern = "/" + "/".join(pattern_parts)
    return re.compile(f"^{pattern}$")


class Route:
    def __init__(self, path: str, endpoint, methods=None):
        self.path = path
        self.endpoint = endpoint
        self.methods = [m.upper() for m in (methods or ["GET"])]
        self.pattern = compile_path(path)


class Router:
    def __init__(self, routes=None):
        self.routes = routes or []

    def add_route(self, path, endpoint, methods=None):
        self.routes.append(Route(path, endpoint, methods=methods))

    async def handle_request(self, request, app=None):
        for route in self.routes:
            if request.method not in route.methods:
                continue
            match = route.pattern.match(request.url.path)
            if match:
                request.path_params = match.groupdict()
                result = route.endpoint(request)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
        return JSONResponse({"error": "Not found"}, status_code=404)


class Mount:
    def __init__(self, path: str, app):
        self.path = path.rstrip("/") or "/"
        self.app = app


class WebSocketRoute:
    def __init__(self, path, endpoint):
        self.path = path
        self.endpoint = endpoint
