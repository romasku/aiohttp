# type: ignore
import asyncio
import base64
import hashlib
import os
from typing import Any
from unittest import mock

import pytest

import aiohttp
from aiohttp import client, hdrs
from aiohttp.http import WS_KEY
from aiohttp.streams import EofStream
from aiohttp.test_utils import make_mocked_coro


@pytest.fixture
def key_data():
    return os.urandom(16)


@pytest.fixture
def key(key_data: Any):
    return base64.b64encode(key_data)


@pytest.fixture
def ws_key(key: Any):
    return base64.b64encode(hashlib.sha1(key + WS_KEY).digest()).decode()


async def test_ws_connect(ws_key: Any, loop: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_PROTOCOL: "chat",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            res = await aiohttp.ClientSession().ws_connect(
                "http://test.org", protocols=("t1", "t2", "chat")
            )

    assert isinstance(res, client.ClientWebSocketResponse)
    assert res.protocol == "chat"
    assert hdrs.ORIGIN not in m_req.call_args[1]["headers"]


async def test_try_ws_connect_upgrade(loop: Any, ws_key: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_PROTOCOL: "chat",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            try_res = await aiohttp.ClientSession().try_ws_connect(
                "http://test.org", protocols=("t1", "t2", "chat")
            )
            res = try_res.upgrade()

    assert isinstance(res, client.ClientWebSocketResponse)
    assert res.protocol == "chat"
    assert hdrs.ORIGIN not in m_req.call_args[1]["headers"]


async def test_ws_connect_with_origin(key_data: Any, loop: Any) -> None:
    resp = mock.Mock()
    resp.status = 403
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            origin = "https://example.org/page.html"
            with pytest.raises(client.WSServerHandshakeError):
                await aiohttp.ClientSession().ws_connect(
                    "http://test.org", origin=origin
                )

    assert hdrs.ORIGIN in m_req.call_args[1]["headers"]
    assert m_req.call_args[1]["headers"][hdrs.ORIGIN] == origin


async def test_ws_connect_with_params(ws_key: Any, loop: Any, key_data: Any) -> None:
    params = {"key1": "value1", "key2": "value2"}

    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_PROTOCOL: "chat",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            await aiohttp.ClientSession().ws_connect(
                "http://test.org", protocols=("t1", "t2", "chat"), params=params
            )

    assert m_req.call_args[1]["params"] == params


async def test_ws_connect_custom_response(
    loop: Any, ws_key: Any, key_data: Any
) -> None:
    class CustomResponse(client.ClientWebSocketResponse):
        def read(self, decode=False):
            return "customized!"

    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            res = await aiohttp.ClientSession(
                ws_response_class=CustomResponse
            ).ws_connect("http://test.org")

    assert res.read() == "customized!"


async def test_try_ws_connect_err_access_to_resp(
    loop: Any, ws_key: Any, key_data: Any
) -> None:
    resp = mock.Mock()
    resp.status = 500
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            async with aiohttp.ClientSession().try_ws_connect(
                "http://test.org", protocols=("t1", "t2", "chat")
            ) as ws_handshake:
                assert ws_handshake.error
                assert ws_handshake.error_response is resp


async def test_ws_connect_err_status(loop: Any, ws_key: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 500
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            with pytest.raises(client.WSServerHandshakeError) as ctx:
                await aiohttp.ClientSession().ws_connect(
                    "http://test.org", protocols=("t1", "t2", "chat")
                )

    assert ctx.value.message == "Invalid response status"


async def test_ws_connect_err_upgrade(loop: Any, ws_key: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "test",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            with pytest.raises(client.WSServerHandshakeError) as ctx:
                await aiohttp.ClientSession().ws_connect(
                    "http://test.org", protocols=("t1", "t2", "chat")
                )

    assert ctx.value.message == "Invalid upgrade header"


async def test_ws_connect_err_conn(loop: Any, ws_key: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "close",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            with pytest.raises(client.WSServerHandshakeError) as ctx:
                await aiohttp.ClientSession().ws_connect(
                    "http://test.org", protocols=("t1", "t2", "chat")
                )

    assert ctx.value.message == "Invalid connection header"


async def test_ws_connect_err_challenge(loop: Any, ws_key: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: "asdfasdfasdfasdfasdfasdf",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            with pytest.raises(client.WSServerHandshakeError) as ctx:
                await aiohttp.ClientSession().ws_connect(
                    "http://test.org", protocols=("t1", "t2", "chat")
                )

    assert ctx.value.message == "Invalid challenge response"


async def test_ws_connect_common_headers(ws_key: Any, loop: Any, key_data: Any) -> None:
    # Emulate a headers dict being reused for a second ws_connect.

    # In this scenario, we need to ensure that the newly generated secret key
    # is sent to the server, not the stale key.
    headers = {}

    async def test_connection() -> None:
        async def mock_get(*args, **kwargs):
            resp = mock.Mock()
            resp.status = 101
            key = kwargs.get("headers").get(hdrs.SEC_WEBSOCKET_KEY)
            accept = base64.b64encode(
                hashlib.sha1(base64.b64encode(base64.b64decode(key)) + WS_KEY).digest()
            ).decode()
            resp.headers = {
                hdrs.UPGRADE: "websocket",
                hdrs.CONNECTION: "upgrade",
                hdrs.SEC_WEBSOCKET_ACCEPT: accept,
                hdrs.SEC_WEBSOCKET_PROTOCOL: "chat",
            }
            return resp

        with mock.patch("aiohttp.client.os") as m_os:
            with mock.patch(
                "aiohttp.client.ClientSession.request", side_effect=mock_get
            ) as m_req:
                m_os.urandom.return_value = key_data

                res = await aiohttp.ClientSession().ws_connect(
                    "http://test.org", protocols=("t1", "t2", "chat"), headers=headers
                )

        assert isinstance(res, client.ClientWebSocketResponse)
        assert res.protocol == "chat"
        assert hdrs.ORIGIN not in m_req.call_args[1]["headers"]

    await test_connection()
    # Generate a new ws key
    key_data = os.urandom(16)
    await test_connection()


async def test_close(loop: Any, ws_key: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.WebSocketWriter") as WebSocketWriter:
        with mock.patch("aiohttp.client.os") as m_os:
            with mock.patch("aiohttp.client.ClientSession.request") as m_req:
                m_os.urandom.return_value = key_data
                m_req.return_value = loop.create_future()
                m_req.return_value.set_result(resp)
                writer = mock.Mock()
                WebSocketWriter.return_value = writer
                writer.close = make_mocked_coro()

                session = aiohttp.ClientSession()
                resp = await session.ws_connect("http://test.org")
                assert not resp.closed

                resp._reader.feed_data(
                    aiohttp.WSMessage(aiohttp.WSMsgType.CLOSE, b"", b""), 0
                )

                res = await resp.close()
                writer.close.assert_called_with(1000, b"")
                assert resp.closed
                assert res
                assert resp.exception() is None

                # idempotent
                res = await resp.close()
                assert not res
                assert writer.close.call_count == 1

                await session.close()


async def test_close_eofstream(loop: Any, ws_key: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.WebSocketWriter") as WebSocketWriter:
        with mock.patch("aiohttp.client.os") as m_os:
            with mock.patch("aiohttp.client.ClientSession.request") as m_req:
                m_os.urandom.return_value = key_data
                m_req.return_value = loop.create_future()
                m_req.return_value.set_result(resp)
                writer = WebSocketWriter.return_value = mock.Mock()

                session = aiohttp.ClientSession()
                resp = await session.ws_connect("http://test.org")
                assert not resp.closed

                exc = EofStream()
                resp._reader.set_exception(exc)

                await resp.receive()
                writer.close.assert_called_with(1000, b"")
                assert resp.closed

                await session.close()


async def test_close_exc(loop: Any, ws_key: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.WebSocketWriter") as WebSocketWriter:
        with mock.patch("aiohttp.client.os") as m_os:
            with mock.patch("aiohttp.client.ClientSession.request") as m_req:
                m_os.urandom.return_value = key_data
                m_req.return_value = loop.create_future()
                m_req.return_value.set_result(resp)
                writer = mock.Mock()
                WebSocketWriter.return_value = writer
                writer.close = make_mocked_coro()

                session = aiohttp.ClientSession()
                resp = await session.ws_connect("http://test.org")
                assert not resp.closed

                exc = ValueError()
                resp._reader.set_exception(exc)

                await resp.close()
                assert resp.closed
                assert resp.exception() is exc

                await session.close()


async def test_close_exc2(loop: Any, ws_key: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.WebSocketWriter") as WebSocketWriter:
        with mock.patch("aiohttp.client.os") as m_os:
            with mock.patch("aiohttp.client.ClientSession.request") as m_req:
                m_os.urandom.return_value = key_data
                m_req.return_value = loop.create_future()
                m_req.return_value.set_result(resp)
                writer = WebSocketWriter.return_value = mock.Mock()

                resp = await aiohttp.ClientSession().ws_connect("http://test.org")
                assert not resp.closed

                exc = ValueError()
                writer.close.side_effect = exc

                await resp.close()
                assert resp.closed
                assert resp.exception() is exc

                resp._closed = False
                writer.close.side_effect = asyncio.CancelledError()
                with pytest.raises(asyncio.CancelledError):
                    await resp.close()


async def test_send_data_after_close(ws_key: Any, key_data: Any, loop: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            resp = await aiohttp.ClientSession().ws_connect("http://test.org")
            resp._writer._closing = True

            for meth, args in (
                (resp.ping, ()),
                (resp.pong, ()),
                (resp.send_str, ("s",)),
                (resp.send_bytes, (b"b",)),
                (resp.send_json, ({},)),
            ):
                with pytest.raises(ConnectionResetError):
                    await meth(*args)


async def test_send_data_type_errors(ws_key: Any, key_data: Any, loop: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.WebSocketWriter") as WebSocketWriter:
        with mock.patch("aiohttp.client.os") as m_os:
            with mock.patch("aiohttp.client.ClientSession.request") as m_req:
                m_os.urandom.return_value = key_data
                m_req.return_value = loop.create_future()
                m_req.return_value.set_result(resp)
                WebSocketWriter.return_value = mock.Mock()

                resp = await aiohttp.ClientSession().ws_connect("http://test.org")

                with pytest.raises(TypeError):
                    await resp.send_str(b"s")
                with pytest.raises(TypeError):
                    await resp.send_bytes("b")
                with pytest.raises(TypeError):
                    await resp.send_json(set())


async def test_reader_read_exception(ws_key: Any, key_data: Any, loop: Any) -> None:
    hresp = mock.Mock()
    hresp.status = 101
    hresp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.WebSocketWriter") as WebSocketWriter:
        with mock.patch("aiohttp.client.os") as m_os:
            with mock.patch("aiohttp.client.ClientSession.request") as m_req:
                m_os.urandom.return_value = key_data
                m_req.return_value = loop.create_future()
                m_req.return_value.set_result(hresp)

                writer = mock.Mock()
                WebSocketWriter.return_value = writer
                writer.close = make_mocked_coro()

                session = aiohttp.ClientSession()
                resp = await session.ws_connect("http://test.org")

                exc = ValueError()
                resp._reader.set_exception(exc)

                msg = await resp.receive()
                assert msg.type == aiohttp.WSMsgType.ERROR
                assert resp.exception() is exc

                await session.close()


async def test_receive_runtime_err(loop: Any) -> None:
    resp = client.ClientWebSocketResponse(
        mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock(), 10.0, True, True, loop
    )
    resp._waiting = True

    with pytest.raises(RuntimeError):
        await resp.receive()


async def test_ws_connect_close_resp_on_err(
    loop: Any, ws_key: Any, key_data: Any
) -> None:
    resp = mock.Mock()
    resp.status = 500
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            with pytest.raises(client.WSServerHandshakeError):
                await aiohttp.ClientSession().ws_connect(
                    "http://test.org", protocols=("t1", "t2", "chat")
                )
            resp.close.assert_called_with()


async def test_ws_connect_non_overlapped_protocols(
    ws_key: Any, loop: Any, key_data: Any
) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_PROTOCOL: "other,another",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            res = await aiohttp.ClientSession().ws_connect(
                "http://test.org", protocols=("t1", "t2", "chat")
            )

    assert res.protocol is None


async def test_ws_connect_non_overlapped_protocols_2(
    ws_key: Any, loop: Any, key_data: Any
) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_PROTOCOL: "other,another",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            connector = aiohttp.TCPConnector(force_close=True)
            res = await aiohttp.ClientSession(connector=connector).ws_connect(
                "http://test.org", protocols=("t1", "t2", "chat")
            )

    assert res.protocol is None
    del res


async def test_ws_connect_deflate(loop: Any, ws_key: Any, key_data: Any) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_EXTENSIONS: "permessage-deflate",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            res = await aiohttp.ClientSession().ws_connect(
                "http://test.org", compress=15
            )

    assert res.compress == 15
    assert res.client_notakeover is False


async def test_ws_connect_deflate_per_message(
    loop: Any, ws_key: Any, key_data: Any
) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_EXTENSIONS: "permessage-deflate",
    }
    with mock.patch("aiohttp.client.WebSocketWriter") as WebSocketWriter:
        with mock.patch("aiohttp.client.os") as m_os:
            with mock.patch("aiohttp.client.ClientSession.request") as m_req:
                m_os.urandom.return_value = key_data
                m_req.return_value = loop.create_future()
                m_req.return_value.set_result(resp)
                writer = WebSocketWriter.return_value = mock.Mock()
                send = writer.send = make_mocked_coro()

                session = aiohttp.ClientSession()
                resp = await session.ws_connect("http://test.org")

                await resp.send_str("string", compress=-1)
                send.assert_called_with("string", binary=False, compress=-1)

                await resp.send_bytes(b"bytes", compress=15)
                send.assert_called_with(b"bytes", binary=True, compress=15)

                await resp.send_json([{}], compress=-9)
                send.assert_called_with("[{}]", binary=False, compress=-9)

                await session.close()


async def test_ws_connect_deflate_server_not_support(
    loop: Any, ws_key: Any, key_data: Any
) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            res = await aiohttp.ClientSession().ws_connect(
                "http://test.org", compress=15
            )

    assert res.compress == 0
    assert res.client_notakeover is False


async def test_ws_connect_deflate_notakeover(
    loop: Any, ws_key: Any, key_data: Any
) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_EXTENSIONS: "permessage-deflate; "
        "client_no_context_takeover",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            res = await aiohttp.ClientSession().ws_connect(
                "http://test.org", compress=15
            )

    assert res.compress == 15
    assert res.client_notakeover is True


async def test_ws_connect_deflate_client_wbits(
    loop: Any, ws_key: Any, key_data: Any
) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_EXTENSIONS: "permessage-deflate; "
        "client_max_window_bits=10",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            res = await aiohttp.ClientSession().ws_connect(
                "http://test.org", compress=15
            )

    assert res.compress == 10
    assert res.client_notakeover is False


async def test_ws_connect_deflate_client_wbits_bad(
    loop: Any, ws_key: Any, key_data: Any
) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_EXTENSIONS: "permessage-deflate; "
        "client_max_window_bits=6",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            with pytest.raises(client.WSServerHandshakeError):
                await aiohttp.ClientSession().ws_connect("http://test.org", compress=15)


async def test_ws_connect_deflate_server_ext_bad(
    loop: Any, ws_key: Any, key_data: Any
) -> None:
    resp = mock.Mock()
    resp.status = 101
    resp.headers = {
        hdrs.UPGRADE: "websocket",
        hdrs.CONNECTION: "upgrade",
        hdrs.SEC_WEBSOCKET_ACCEPT: ws_key,
        hdrs.SEC_WEBSOCKET_EXTENSIONS: "permessage-deflate; bad",
    }
    with mock.patch("aiohttp.client.os") as m_os:
        with mock.patch("aiohttp.client.ClientSession.request") as m_req:
            m_os.urandom.return_value = key_data
            m_req.return_value = loop.create_future()
            m_req.return_value.set_result(resp)

            with pytest.raises(client.WSServerHandshakeError):
                await aiohttp.ClientSession().ws_connect("http://test.org", compress=15)
