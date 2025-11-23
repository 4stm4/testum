from starlette.responses import Response


class Jinja2Templates:
    def __init__(self, directory: str):
        self.directory = directory

    def TemplateResponse(self, name: str, context: dict):
        content = f"<html><body><h1>Testum</h1></body></html>"
        return Response(content=content, status_code=200, media_type="text/html")
