# coding:utf-8
import uuid
import inspect

import unirest

from .base import TransactionLogBase
from ..tools import (
    CO_QUALNAME, urlparse, parse_qs, is_char, try_json_loads, FuzzyGet, is_valid_ip, get_tcode,
    flask_g, flask_request, flask_current_app, has_flask_request_context,
    has_fastapi_request_context, FastAPITransactionLog,
)


class UnirestTransactionLog(TransactionLogBase):

    def before(self, method, url, params={}, headers=None, *a, **kw):
        request_params, request_headers = params, headers

        parsed_url = urlparse(url)
        request_payload = {k: v[0] for k, v in parse_qs(parsed_url.query).items()}

        if is_char(request_params):
            request_params = try_json_loads(request_params)
        if isinstance(request_params, dict):
            request_payload.update(request_params)
        elif isinstance(request_params, (list, tuple)):
            request_payload['data'] = request_params

        if has_flask_request_context():
            transaction_id = getattr(flask_g, '__transaction_id__', None)
            view_func = flask_current_app.view_functions.get(flask_request.endpoint)
            method_code = (
                getattr(view_func, '__method_code__', None) or
                getattr(flask_request, 'method_code', None) or
                getattr(flask_g, 'method_code', None) or
                FuzzyGet(getattr(flask_g, '__request_headers__', None), 'Method-Code').v or
                FuzzyGet(getattr(flask_g, '__request_payload__', None), 'method_code').v
            )
        elif has_fastapi_request_context():
            fastapi_request = FastAPITransactionLog.local.request
            transaction_id = getattr(fastapi_request.state, '__transaction_id__', None)
            try:
                view_func = fastapi_request.scope['route'].endpoint
            except (KeyError, AttributeError):
                view_func = None
            method_code = (
                getattr(view_func, '__method_code__', None) or
                getattr(fastapi_request.state, 'method_code', None) or
                FuzzyGet(getattr(fastapi_request.state, '__request_headers__', None), 'Method-Code').v or
                FuzzyGet(getattr(fastapi_request.state, '__request_payload__', None), 'method_code').v
            )
        else:
            transaction_id = (
                FuzzyGet(request_headers, 'Transaction-ID').v or
                FuzzyGet(request_payload, 'transaction_id').v or
                uuid.uuid4().hex
            )
            method_code = FuzzyGet(request_headers, 'Method-Code').v or FuzzyGet(request_payload, 'method_code').v

        if request_headers is None:
            request_headers = {'User-Agent': self.svccode, 'Transaction-ID': transaction_id}
        elif isinstance(request_headers, dict):
            request_headers.setdefault('User-Agent', self.svccode)
            request_headers.setdefault('Transaction-ID', transaction_id)

        return request_headers, request_payload, transaction_id, method_code

    def after(
            self, before_return, request_time, response, response_time,
            method, url, params={}, headers=None, *a, **kw
    ):
        request_headers, request_payload, transaction_id, method_code = before_return

        parsed_url = urlparse(url)

        method_name = FuzzyGet(request_headers, 'Method-Name').v
        if method_name is None:
            f_back = inspect.currentframe().f_back
            for _ in range(6):
                if f_back.f_back is not None:
                    f_back = f_back.f_back
            method_name = getattr(f_back.f_code, CO_QUALNAME)

        request_ip = parsed_url.hostname
        if not is_valid_ip(request_ip):
            request_ip = None

        self.logger(
            transaction_id=transaction_id,
            dialog_type='out',
            address=parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path,
            fcode=self.svccode,
            tcode=get_tcode(parsed_url, request_headers, request_payload),
            method_code=method_code,
            method_name=method_name,
            http_method=method.upper(),
            request_time=request_time,
            response_time=response_time,
            request_headers=request_headers,
            request_payload=request_payload,
            response_headers=dict(response.headers),
            response_payload=try_json_loads(response.raw_body) or {},
            http_status_code=response.code,
            request_ip=request_ip
        )

    @classmethod
    def reset_unirest_user_agent(cls):
        unirest.USER_AGENT = cls.syscode
