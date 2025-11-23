class URL:
    def __init__(self, path: str):
        self.path = path


class Request:
    def __init__(self, method: str, url: str, headers=None, cookies=None, json_body=None, path_params=None):
        self.method = method.upper()
        self.url = URL(url)
        self.headers = headers or {}
        self.cookies = cookies or {}
        self._json_body = json_body
        self.path_params = path_params or {}

    async def json(self):
        return self._json_body or {}
