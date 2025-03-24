import os
import sys
import json
import uuid
import traceback

from datetime import datetime

if os.path.basename(sys.argv[0]) != 'setup.py':
    import gqylpy_log as glog

try:
    from fastapi import FastAPI
except ImportError:
    fastapi = None
else:
    from fastapi import Request
    from fastapi import Response
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.middleware.base import RequestResponseEndpoint

from types import ModuleType
from typing import Type, TypeVar, ClassVar, Union, Dict, Any

if sys.version_info >= (3, 9):
    from typing import Annotated
else:
    class Annotated(metaclass=type('', (type,), {
        '__new__': lambda *a: type.__new__(*a)()
    })):
        def __getitem__(self, *a): ...

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    TypeAlias = TypeVar('TypeAlias')

UUID: TypeAlias = TypeVar('UUID', bound=str)
Str: TypeAlias = Annotated[Union[str, None], 'Compatible with None type.']

simple_channel_log: ModuleType = __import__(__package__ + '.i ' + __package__, fromlist=...)


class JournallogMiddleware(BaseHTTPMiddleware):
    appname: ClassVar[str]
    syscode: ClassVar[str]

    request_time:    datetime
    request_headers: Dict[str, Any]
    request_payload: Dict[str, Any]
    transaction_id:  UUID

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in ('/healthcheck', '/metrics') or not hasattr(self, 'appname'):
            return await call_next(request)

        glog.fastapi_request = request

        try:
            await self.before(request)
        except Exception:
            sys.stderr.write(
                traceback.format_exc() +
                '\nAn exception occurred while recording the internal transaction log.\n'
            )

        response = await call_next(request)

        response_body = b''
        try:
            body_iterator = getattr(response, 'body_iterator', None)
            if body_iterator is None:
                return response

            async for chunk in body_iterator:
                response_body += chunk

            await self.after(request, response, response_payload=try_json_loads(response_body) or {})
        except Exception:
            sys.stderr.write(
                traceback.format_exc() +
                '\nAn exception occurred while recording the internal transaction log.\n'
            )

        try:
            del glog.fastapi_request
        except AttributeError:
            pass

        return Response(
            content=response_body,
            status_code=response.status_code,
            media_type=response.media_type,
            headers=response.headers
        )

    async def before(self, request: Request) -> None:
        if not hasattr(request.state, '__request_time__'):
            request.state.__request_time__ = datetime.now()

        if not hasattr(request.state, '__request_headers__'):
            request.state.__request_headers__ = dict(request.headers)

        if not hasattr(request.state, '__request_payload__'):
            request_payload = dict(request.query_params)
            try:
                form_data = await request.form()
            except AssertionError:
                pass
            else:
                if form_data:
                    request_payload.update(dict(form_data))
                else:
                    try:
                        json_data = await request.json()
                    except (json.JSONDecodeError, RuntimeError):
                        pass
                    else:
                        if isinstance(json_data, str):
                            json_data = try_json_loads(json_data)
                        if isinstance(json_data, dict):
                            request_payload.update(json_data)
                        elif isinstance(json_data, list):
                            request_payload['data'] = json_data
            request.state.__request_payload__ = request_payload

        self.request_time    = request.state.__request_time__
        self.request_headers = request.state.__request_headers__
        self.request_payload = request.state.__request_payload__
        self.transaction_id  = request.state.__transaction_id__ = (
            FuzzyGet(self.request_headers, 'Transaction-ID').v or
            FuzzyGet(self.request_payload, 'transaction_id').v or
            uuid.uuid4().hex
        )

    async def after(self, request: Request, response: Response, *, response_payload: Dict[str, Any]) -> None:
        address = f'{request.url.scheme}://{request.url.netloc}{request.url.path}'

        fcode: Str = FuzzyGet(self.request_headers, 'User-Agent').v

        method_code: str = (
            getattr(request.state, 'method_code', None) or
            FuzzyGet(self.request_headers, 'Method-Code').v or
            FuzzyGet(self.request_payload, 'method_code').v
        )

        try:
            method_name: Str = request.scope['route'].endpoint.__name__
        except (KeyError, AttributeError):
            method_name = None

        simple_channel_log.journallog_logger(
            transaction_id=self.transaction_id,
            dialog_type='in',
            address=address,
            fcode=fcode,
            tcode=self.syscode,
            method_code=method_code,
            method_name=method_name,
            http_method=request.method,
            request_time=self.request_time,
            request_headers=self.request_headers,
            request_payload=self.request_payload,
            response_headers=dict(response.headers),
            response_payload=response_payload,
            http_status_code=response.status_code,
            request_ip=request.client.host,
            host_ip=request.url.hostname,
        )


class OmitLongString(dict):

    def __init__(self, data) -> None:
        for name, value in data.items():
            dict.__setitem__(self, name, OmitLongString(value))

    def __new__(cls, data) -> Type[dict]:
        if isinstance(data, dict):
            return dict.__new__(cls)
        if isinstance(data, (list, tuple)):
            return data.__class__(cls(v) for v in data)
        if isinstance(data, str) and len(data) > 1000:
            data = '<Ellipsis>'
        return data


class FuzzyGet(dict):
    v: Any = None

    def __init__(self, data, key, root=None) -> None:
        if root is None:
            self.key = key.replace('-', '').replace('_', '').lower()
            root = self
        for k, v in data.items():
            if k.replace('-', '').replace('_', '').lower() == root.key:
                root.v = data[k]
                break
            dict.__setitem__(self, k, FuzzyGet(v, key=key, root=root))

    def __new__(cls, data, *a, **kw) -> Type[dict]:
        if isinstance(data, dict):
            return dict.__new__(cls)
        if isinstance(data, (list, tuple)):
            return data.__class__(cls(v, *a, **kw) for v in data)
        return cls


def try_json_loads(data):
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return
