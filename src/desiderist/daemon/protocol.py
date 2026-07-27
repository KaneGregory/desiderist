import json

from pydantic import BaseModel


class Request(BaseModel):
    id: str
    command: str
    params: dict = {}


class Response(BaseModel):
    id: str
    ok: bool
    result: dict | list | None = None
    error: str | None = None


def encode(message: BaseModel) -> bytes:
    return (message.model_dump_json() + "\n").encode("utf-8")


def decode_request(line: bytes) -> Request:
    return Request.model_validate(json.loads(line))


def decode_response(line: bytes) -> Response:
    return Response.model_validate(json.loads(line))
