import json
import base64


def encode(payload, key, algorithm="HS256"):
    data = json.dumps(payload).encode()
    return base64.urlsafe_b64encode(data).decode()


def decode(token, key, algorithms=None):
    data = base64.urlsafe_b64decode(token.encode()).decode()
    return json.loads(data)
