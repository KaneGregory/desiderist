from desiderist.daemon.protocol import Request, Response, decode_request, decode_response, encode


def test_request_round_trip():
    request = Request(id="r1", command="chat.send", params={"message": "hi"})
    decoded = decode_request(encode(request))
    assert decoded == request


def test_request_defaults_to_empty_params():
    request = Request(id="r1", command="desires.list")
    assert request.params == {}


def test_response_round_trip():
    response = Response(id="r1", ok=True, result={"messages": ["hello"]})
    decoded = decode_response(encode(response))
    assert decoded == response


def test_response_error_round_trip():
    response = Response(id="r1", ok=False, error="boom")
    decoded = decode_response(encode(response))
    assert decoded.ok is False
    assert decoded.error == "boom"
