"""Enforce body size on received bytes, including chunked uploads without a length header."""

from fastapi import HTTPException


class RequestBodyLimit:
    def __init__(self, app, max_bytes=32 * 1024 * 1024):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(413, "Request exceeds 32 MiB")
            return message

        await self.app(scope, limited_receive, send)
