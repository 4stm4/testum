import asyncio
from starlette.routing import Mount, Router, Route
from starlette.responses import JSONResponse
from starlette.requests import Request


class Starlette:
    def __init__(self, routes=None, middleware=None, debug=False):
        self.routes = routes or []
        self.debug = debug
        self.router = Router([r for r in self.routes if isinstance(r, Route)])
        self.mounts = [r for r in self.routes if isinstance(r, Mount)]
        self.events = {"startup": []}

    def on_event(self, event_type):
        def decorator(func):
            self.events.setdefault(event_type, []).append(func)
            return func
        return decorator

    async def handle_request(self, request: Request):
        # Check mounts first
        for mount in self.mounts:
            if request.url.path.startswith(mount.path):
                sub_path = request.url.path[len(mount.path):] or "/"
                sub_request = Request(
                    method=request.method,
                    url=sub_path if sub_path.startswith("/") else f"/{sub_path}",
                    headers=request.headers,
                    cookies=request.cookies,
                    json_body=request._json_body,
                )
                handler = getattr(mount.app, "handle_request", None)
                if handler:
                    return await handler(sub_request)
        # Fallback to router
        return await self.router.handle_request(request, app=self)

    async def startup(self):
        for func in self.events.get("startup", []):
            result = func()
            if asyncio.iscoroutine(result):
                await result

    async def __call__(self, scope, receive, send):
        # ASGI compatibility placeholder
        response = await self.handle_request(Request(scope.get("method", "GET"), scope.get("path", "/")))
        await send(response)
