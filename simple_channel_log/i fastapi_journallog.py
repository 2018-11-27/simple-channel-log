import os
import sys
import json
import uuid
import socket
import traceback
import threading

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


class JournallogMiddleware(BaseHTTPMiddleware):
    appname: ClassVar[str]
    syscode: ClassVar[str]

    request_time:    datetime
    request_headers: Dict[str, Any]
    request_data:    Dict[str, Any]
    transaction_id:  UUID

    async def dispatch(
            self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in ('/healthcheck', '/metrics') \
                or not hasattr(self, 'appname'):
            return await call_next(request)

        glog.fastapi_request = request

        try:
            await self.before(request)
        except Exception:
            sys.stderr.write(
                traceback.format_exc() + '\nAn exception occurred while '
                'recording the internal transaction log.'
            )

        response = await call_next(request)

        response_body = b''
        async for chunk in response.body_iterator:
            response_body += chunk
        try:
            response_data = json.loads(response_body)
        except json.JSONDecodeError:
            response_data = None

        try:
            await self.after(request, response, response_data)
        except Exception:
            sys.stderr.write(
                traceback.format_exc() + '\nAn exception occurred while '
                'recording the internal transaction log.'
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

        if not hasattr(request.state, '__request_data__'):
            try:
                form_data = await request.form()
            except AssertionError:
                form_data = None
            if form_data:
                request_data = dict(form_data)
            elif request.query_params:
                request_data = dict(request.query_params)
            else:
                try:
                    request_data = await request.json()
                except json.JSONDecodeError:
                    request_data = None
            request.state.__request_data__ = request_data

        self.request_time    = request.state.__request_time__
        self.request_headers = request.state.__request_headers__
        self.request_data    = request.state.__request_data__
        self.transaction_id  = request.state.__transaction_id__ = (
            FuzzyGet(self.request_headers, 'Transaction-ID').v or
            FuzzyGet(self.request_data, 'transaction_id').v or
            uuid.uuid4().hex
        )

    async def after(
            self,
            request: Request,
            response: Response,
            response_data: Dict[str, Any]
    ) -> None:
        url = request.url
        address = f'{url.scheme}://{url.netloc}{url.path}'

        fcode: Str = FuzzyGet(self.request_headers, 'User-Agent').v
        if not (fcode is None or is_syscode(fcode)):
            fcode = None

        method_code: str = (
            getattr(request.state, 'method_code', None) or
            FuzzyGet(self.request_headers, 'Method-Code').v or
            FuzzyGet(self.request_data, 'method_code').v
        )

        try:
            method_name: Str = request.scope['route'].endpoint.__name__
        except (KeyError, AttributeError):
            method_name = None

        response_code = FuzzyGet(response_data, 'code').v
        order_id      = FuzzyGet(response_data, 'order_id').v
        province_code = FuzzyGet(response_data, 'province_code').v
        city_code     = FuzzyGet(response_data, 'city_code').v
        account_type  = FuzzyGet(response_data, 'account_type').v
        account_num   = FuzzyGet(response_data, 'account_num').v
        response_account_type = \
            FuzzyGet(response_data, 'response_account_type').v
        response_account_num = \
            FuzzyGet(response_data, 'response_account_num').v

        if response_code is not None:
            response_code = str(response_code)

        request_headers_str = \
            json.dumps(self.request_headers, ensure_ascii=False)
        request_payload_str = \
            json.dumps(OmitLongString(self.request_data), ensure_ascii=False)
        response_headers_str = \
            json.dumps(dict(response.headers), ensure_ascii=False)
        response_payload_str = \
            json.dumps(OmitLongString(response_data), ensure_ascii=False)

        request_time_str = \
            self.request_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        response_time = datetime.now()
        response_time_str = response_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        total_time = int(round(
            (response_time - self.request_time).total_seconds() * 1000
        ))

        glog.info(json.dumps({
            'app_name': self.appname + '_info',
            'level': 'INFO',
            'log_time': response_time_str,
            'logger': __package__,
            'thread': str(threading.current_thread().ident),
            'transaction_id': self.transaction_id,
            'dialog_type': 'in',
            'address': address,
            'fcode': fcode,
            'tcode': self.syscode,
            'method_code': method_code,
            'method_name': method_name,
            'http_method': request.method,
            'request_time': request_time_str,
            'request_headers': request_headers_str,
            'request_payload': request_payload_str,
            'response_time': response_time_str,
            'response_headers': response_headers_str,
            'response_payload': response_payload_str,
            'response_code': response_code,
            'response_remark': None,
            'http_status_code': str(response.status_code),
            'order_id': order_id,
            'province_code': province_code,
            'city_code': city_code,
            'total_time': total_time,
            'error_code': response_code,
            'request_ip': request.client.host,
            'host_ip': url.hostname,
            'host_name': socket.gethostname(),
            'account_type': account_type,
            'account_num': account_num,
            'response_account_type': response_account_type,
            'response_account_num': response_account_num,
            'user': None,
            'tag': None,
            'service_line': None
        }, ensure_ascii=False), gname='info_')


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


def is_syscode(x):
    return len(x) == 10 and x[0].isalpha() and x[1:].isdigit()
