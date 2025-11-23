import json

class Response:
    def __init__(self, content=b"", status_code=200, media_type="text/plain", headers=None):
        self.status_code = status_code
        self.media_type = media_type
        self.headers = headers or {}
        if isinstance(content, str):
            content = content.encode()
        self.content = content

    def json(self):
        try:
            return json.loads(self.content.decode())
        except Exception:
            return self.content

    def delete_cookie(self, key):
        if not hasattr(self, "cookies"):
            self.cookies = {}
        self.cookies[key] = None


class JSONResponse(Response):
    def __init__(self, content, status_code=200, headers=None):
        self._json_content = content
        super().__init__(
            content=json.dumps(content), status_code=status_code, media_type="application/json", headers=headers
        )

    def json(self):
        return self._json_content


class RedirectResponse(Response):
    def __init__(self, url, status_code=307):
        super().__init__(b"", status_code=status_code, media_type="text/plain")
        self.headers["Location"] = url
