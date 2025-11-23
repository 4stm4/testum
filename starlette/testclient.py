import asyncio
from http.cookies import SimpleCookie
from starlette.requests import Request


class ResponseWrapper:
    def __init__(self, response):
        self._response = response
        self.status_code = response.status_code
        self.headers = response.headers
        self.content = response.content

    def json(self):
        return self._response.json()


class TestClient:
    def __init__(self, app):
        self.app = app
        self.cookies = SimpleCookie()
        asyncio.get_event_loop()  # ensure loop

    def _prepare_cookies(self, extra_cookies):
        jar = {k: morsel.value for k, morsel in self.cookies.items()}
        jar.update(extra_cookies or {})
        return jar

    def _request(self, method, path, json=None, headers=None, cookies=None):
        request_cookies = self._prepare_cookies(cookies)
        req = Request(method=method, url=path, headers=headers or {}, cookies=request_cookies, json_body=json)
        response = asyncio.get_event_loop().run_until_complete(self.app.handle_request(req))
        if hasattr(response, "cookies"):
            for key, value in response.cookies.items():
                if value is None:
                    if key in self.cookies:
                        del self.cookies[key]
                else:
                    self.cookies[key] = value
        return ResponseWrapper(response)

    def get(self, path, headers=None, cookies=None):
        return self._request("GET", path, headers=headers, cookies=cookies)

    def post(self, path, json=None, headers=None, cookies=None):
        return self._request("POST", path, json=json, headers=headers, cookies=cookies)

    def put(self, path, json=None, headers=None, cookies=None):
        return self._request("PUT", path, json=json, headers=headers, cookies=cookies)

    def delete(self, path, headers=None, cookies=None):
        return self._request("DELETE", path, headers=headers, cookies=cookies)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
