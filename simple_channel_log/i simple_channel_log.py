# coding:utf-8
import os
import re
import sys
import uuid
import json as jsonx
import socket
import inspect
import warnings
import functools
import traceback
import threading

from datetime import datetime

if os.path.basename(sys.argv[0]) != 'setup.py':
    import ipaddress
    import gqylpy_log as glog

try:
    from flask import Flask
except ImportError:
    Flask = None
else:
    from flask import g, request, current_app, has_request_context

    def wrap_flask_init_method(func):
        @functools.wraps(func)
        def inner(self, *a, **kw):
            func(self, *a, **kw)
            self.before_request(journallog_flask_before)
            self.after_request(journallog_flask)
        inner.__wrapped__ = func
        return inner

    Flask.__init__ = wrap_flask_init_method(Flask.__init__)

try:
    from fastapi import FastAPI
except ImportError:
    FastAPI = None
else:
    FastAPIJournallogMiddleware = __import__(__package__ + '.i fastapi_journallog', fromlist=os).JournallogMiddleware

    def wrap_fastapi_init_method(func):
        @functools.wraps(func)
        def inner(self, *a, **kw):
            func(self, *a, **kw)
            self.add_middleware(FastAPIJournallogMiddleware)
        inner.__wrapped__ = func
        return inner

    FastAPI.__init__ = wrap_fastapi_init_method(FastAPI.__init__)

try:
    import requests
except ImportError:
    requests = None

try:
    import unirest
except ImportError:
    unirest = None

try:
    from ctec_consumer.dummy.ctec_consumer import Consumer as CTECConsumer
except ImportError:
    CTECConsumer = None
else:
    def wrap_register_worker(func):
        @functools.wraps(func)
        def inner(self, worker):
            func(self, JournallogCectConsumer(worker, topic=self.queue))
        inner.__wrapped__ = func
        return inner
    CTECConsumer.register_worker = wrap_register_worker(CTECConsumer.register_worker)

if sys.version_info.major < 3:
    from urlparse import urlparse, parse_qs
    is_char = lambda x: isinstance(x, (str, unicode))
else:
    from urllib.parse import urlparse, parse_qs
    is_char = lambda x: isinstance(x, str)

from typing import TypeVar, Union

Str = TypeVar('Str', bound=Union[str, None])
Int = TypeVar('Int', bound=Union[int, None])
Dict = TypeVar('Dict', bound=Union[dict, None])

co_qualname = 'co_qualname' if sys.version_info >= (3, 11) else 'co_name'

that = sys.modules[__package__]
this = sys.modules[__name__]

that.external_log = lambda *a, **kw: None

deprecated = object()


def __init__(
        appname,
        syscode=deprecated,
        logdir=r'C:\BllLogs' if sys.platform == 'win32' else '/app/logs',
        when='D',
        interval=1,
        backup_count=7,
        stream=deprecated,
        output_to_terminal=None,
        enable_journallog_in=deprecated,
        enable_journallog_out=deprecated
):
    if hasattr(this, 'appname'):
        return

    prefix = re.match(r'[a-zA-Z]\d{9}[_-]', appname)
    if prefix is None:
        raise ValueError('parameter appname "%s" is illegal.' % appname)

    if syscode is not deprecated:
        warnings.warn('parameter "syscode" is deprecated.', category=DeprecationWarning, stacklevel=2)
    if enable_journallog_in is not deprecated:
        warnings.warn('parameter "enable_journallog_in" is deprecated.', category=DeprecationWarning, stacklevel=2)
    if enable_journallog_out is not deprecated:
        warnings.warn('parameter "enable_journallog_out" is deprecated.', category=DeprecationWarning, stacklevel=2)
    if stream is not deprecated:
        warnings.warn(
            'parameter "stream" will be deprecated soon, replaced to "output_to_terminal".',
            category=DeprecationWarning, stacklevel=2
        )
        if output_to_terminal is None:
            output_to_terminal = stream

    appname = appname[0].lower() + appname[1:].replace('-', '_')
    syscode = prefix.group()[:-1].upper()

    that.appname = this.appname = appname
    that.syscode = this.syscode = syscode
    this.output_to_terminal = output_to_terminal

    if sys.platform == 'win32' and logdir == r'C:\BllLogs':
        logdir = os.path.join(logdir, appname)

    handlers = [{
        'name': 'TimedRotatingFileHandler',
        'level': 'DEBUG',
        'filename': '%s/debug/%s_code-debug.log' % (logdir, appname),
        'encoding': 'UTF-8',
        'when': when,
        'interval': interval,
        'backupCount': backup_count,
        'options': {'onlyRecordCurrentLevel': True}
    }]

    for level in 'info', 'warning', 'error', 'critical':
        handlers.append({
            'name': 'TimedRotatingFileHandler',
            'level': level.upper(),
            'filename': '%s/%s_code-%s.log' % (logdir, appname, level),
            'encoding': 'UTF-8',
            'when': when,
            'interval': interval,
            'backupCount': backup_count,
            'options': {'onlyRecordCurrentLevel': True}
        })

    glog.__init__('code', handlers=handlers, gname='code')

    if output_to_terminal:
        glog.__init__(
            'stream',
            formatter={
                'fmt': '[%(asctime)s] [%(levelname)s] %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            handlers=[{'name': 'StreamHandler'}],
            gname='stream'
        )

    if FastAPI is not None:
        FastAPIJournallogMiddleware.appname = appname
        FastAPIJournallogMiddleware.syscode = syscode

    if requests is not None:
        requests.Session.request = journallog_request(requests.Session.request)

    if unirest is not None:
        unirest.__request = JournallogUnirest(unirest.__request)
        unirest.USER_AGENT = syscode
        threading.Timer(15, JournallogUnirest.reset_unirest_user_agent)

    if Flask or FastAPI or requests or unirest:
        glog.__init__(
            'info',
            handlers=[{
                'name': 'TimedRotatingFileHandler',
                'level': 'INFO',
                'filename': '%s/%s_info-info.log' % (logdir, appname),
                'encoding': 'UTF-8',
                'when': when,
                'interval': interval,
                'backupCount': backup_count,
            }],
            gname='info_'
        )

    glog.__init__(
        'trace',
        handlers=[{
            'name': 'TimedRotatingFileHandler',
            'level': 'DEBUG',
            'filename': '%s/trace/%s_trace-trace.log' % (logdir, appname),
            'encoding': 'UTF-8',
            'when': when,
            'interval': interval,
            'backupCount': backup_count,
        }],
        gname='trace'
    )


def logger(msg, *args, **extra):
    try:
        try:
            app_name = this.appname + '_code'
        except AttributeError:
            raise RuntimeError('uninitialized.')

        args, extra = OmitLongString(args), OmitLongString(extra)

        if sys.version_info.major < 3 and isinstance(msg, str):
            msg = msg.decode('UTF-8')

        if is_char(msg):
            try:
                msg = msg % args
            except (TypeError, ValueError):
                pass
            msg = msg[:3000]
        elif isinstance(msg, (dict, list, tuple)):
            msg = OmitLongString(msg)

        if has_flask_request_context():
            transaction_id = getattr(g, '__transaction_id__', None)
            method_code = (
                getattr(request, 'method_code', None) or
                FuzzyGet(getattr(g, '__request_headers__', {}), 'Method-Code').v or
                FuzzyGet(getattr(g, '__request_payload__', {}), 'method_code').v
            )
        elif has_fastapi_request_context():
            state = FastAPIJournallogMiddleware.local.request.state
            transaction_id = getattr(state, '__transaction_id__', None)
            method_code = (
                getattr(state, 'method_code', None) or
                FuzzyGet(getattr(state, '__request_headers__', {}), 'Method-Code').v or
                FuzzyGet(getattr(state, '__request_payload__', {}), 'method_code').v
            )
        else:
            transaction_id = uuid.uuid4().hex
            method_code = None

        f_back = inspect.currentframe().f_back
        level  = f_back.f_code.co_name

        f_back = f_back.f_back
        module = f_back.f_globals['__name__']
        name   = getattr(f_back.f_code, co_qualname)
        line   = f_back.f_lineno

        logger_ = '%s.%s.line%d' % (module, name, line)

        data = {
            'app_name': app_name,
            'level': level.upper(),
            'log_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'logger': logger_,
            'thread': str(threading.current_thread().ident),
            'code_message': msg,
            'transaction_id': transaction_id,
            'method_code': method_code,
            'method_name': getattr(f_back.f_code, co_qualname),
            'error_code': None,
            'tag': None,
            'host_name': socket.gethostname()
        }

        for k, v in extra.items():
            if data.get(k) is None:
                data[k] = try_json_dumps(v) if isinstance(v, (dict, list, tuple)) else str(v)

        getattr(glog, level)(try_json_dumps(data), gname='code')

        if this.output_to_terminal:
            getattr(glog, level)('[%s] %s' % (logger_, msg), gname='stream')
    except Exception:
        sys.stderr.write(traceback.format_exc() + '\nAn exception occurred while recording the log.\n')


def debug(msg, *args, **extra):
    logger(msg, *args, **extra)


def info(msg, *args, **extra):
    logger(msg, *args, **extra)


def warning(msg, *args, **extra):
    logger(msg, *args, **extra)


warn = warning


def error(msg, *args, **extra):
    logger(msg, *args, **extra)


exception = error


def critical(msg, *args, **extra):
    logger(msg, *args, **extra)


fatal = critical


def trace(**extra):
    extra = OmitLongString(extra)
    extra.update({'app_name': this.appname + '_trace', 'level': 'TRACE'})
    glog.debug(try_json_dumps(extra), gname='trace')


def journallog_flask_before():
    try:
        if request.path in ('/healthcheck', '/metrics') or not hasattr(this, 'appname'):
            return

        if not hasattr(g, '__request_time__'):
            g.__request_time__ = datetime.now()

        if not hasattr(g, '__request_headers__'):
            g.__request_headers__ = dict(request.headers)

        if not hasattr(g, '__request_payload__'):
            request_payload = request.args.to_dict()
            if request.form:
                request_payload.update(request.form.to_dict())
            elif request.data:
                data = try_json_loads(request.data)
                if is_char(data):
                    data = try_json_loads(data)
                if isinstance(data, dict):
                    request_payload.update(data)
                elif isinstance(data, list):
                    request_payload['data'] = data
            g.__request_payload__ = request_payload

        g.__transaction_id__ = (
            FuzzyGet(g.__request_headers__, 'Transaction-ID').v or
            FuzzyGet(g.__request_payload__, 'transaction_id').v or
            uuid.uuid4().hex
        )
    except Exception:
        sys.stderr.write(
            traceback.format_exc() +
            '\nAn exception occurred while recording the internal transaction log.\n'
        )


def journallog_flask(response):
    try:
        if request.path in ('/healthcheck', '/metrics') or not hasattr(this, 'appname'):
            return response

        parsed_url = urlparse(request.url)
        address = parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path

        fcode = FuzzyGet(g.__request_headers__, 'User-Agent').v

        method_code = (
            getattr(request, 'method_code', None) or
            FuzzyGet(g.__request_headers__, 'Method-Code').v or
            FuzzyGet(g.__request_payload__, 'method_code').v
        )

        view_func = current_app.view_functions.get(request.endpoint)
        method_name = view_func.__name__ if view_func else None

        journallog_logger(
            transaction_id=g.__transaction_id__,
            dialog_type='in',
            address=address,
            fcode=fcode,
            tcode=this.syscode,
            method_code=method_code,
            method_name=method_name,
            http_method=request.method,
            request_time=g.__request_time__,
            request_headers=g.__request_headers__,
            request_payload=g.__request_payload__,
            response_headers=dict(response.headers),
            response_payload=try_json_loads(response.get_data()) or {},
            http_status_code=response.status_code,
            request_ip=request.remote_addr
        )

    except Exception:
        sys.stderr.write(
            traceback.format_exc() +
            '\nAn exception occurred while recording the internal transaction log.\n'
        )

    return response


def journallog_request(func):

    @functools.wraps(func)
    def inner(self, method, url, headers=None, params=None, data=None, json=None, **kw):
        try:
            parsed_url = urlparse(url)
            request_payload = {k: v[0] for k, v in parse_qs(parsed_url.query).items()}

            if isinstance(params, dict):
                request_payload.update(params)

            datax = data or json

            if is_char(datax):
                datax = try_json_loads(datax)
            if isinstance(datax, dict):
                request_payload.update(datax)
            elif isinstance(datax, (list, tuple)):
                request_payload['data'] = datax

            if has_flask_request_context():
                transaction_id = getattr(g, '__transaction_id__', None)
            elif has_fastapi_request_context():
                transaction_id = getattr(FastAPIJournallogMiddleware.local.request.state, '__transaction_id__', None)
            else:
                transaction_id = (
                    FuzzyGet(headers, 'Transaction-ID').v or
                    FuzzyGet(request_payload, 'transaction_id').v or
                    uuid.uuid4().hex
                )

            if headers is None:
                headers = {'User-Agent': this.syscode, 'Transaction-ID': transaction_id}
            elif isinstance(headers, dict):
                headers.setdefault('User-Agent', this.syscode)
                headers.setdefault('Transaction-ID', transaction_id)

            request_time = datetime.now()
        except Exception:
            sys.stderr.write(
                traceback.format_exc() +
                '\nAn exception occurred while recording the external transaction log.\n'
            )

        response = func(self, method, url, headers=headers, params=params, data=data, json=json, **kw)

        try:
            method_name = FuzzyGet(headers, 'Method-Name').v
            if method_name is None:
                f_back = inspect.currentframe().f_back.f_back
                if f_back.f_back is not None:
                    f_back = f_back.f_back
                method_name = getattr(f_back.f_code, co_qualname)

            try:
                response_payload = response.json()
            except ValueError:
                response_payload = {}

            request_ip = parsed_url.hostname
            if not is_valid_ip(request_ip):
                request_ip = None

            journallog_logger(
                transaction_id=transaction_id,
                dialog_type='out',
                address=parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path,
                fcode=this.syscode,
                tcode=FuzzyGet(headers, 'T-Code').v or FuzzyGet(request_payload, 'tcode').v,
                method_code=FuzzyGet(headers, 'Method-Code').v or FuzzyGet(request_payload, 'method_code').v,
                method_name=method_name,
                http_method=method,
                request_time=request_time,
                request_headers=dict(response.request.headers),
                request_payload=request_payload,
                response_headers=dict(response.headers),
                response_payload=response_payload,
                http_status_code=response.status_code,
                request_ip=request_ip
            )
        except Exception:
            sys.stderr.write(
                traceback.format_exc() +
                '\nAn exception occurred while recording the external transaction log.\n'
            )

        return response

    inner.__wrapped__ = func
    return inner


class JournallogUnirest(object):

    def __init__(self, func):
        self.__wrapped__ = func
        functools.update_wrapper(self, func)

    def __call__(self, method, url, params={}, headers=None, *a, **kw):
        try:
            parsed_url = urlparse(url)
            request_headers, request_payload = self.before(parsed_url.query, params, headers)
            request_time = datetime.now()
        except Exception:
            sys.stderr.write(
                traceback.format_exc() +
                '\nAn exception occurred while recording the external transaction log.\n'
            )

        response = self.__wrapped__(method, url, params, headers, *a, **kw)

        try:
            self.after(method, parsed_url, request_time, request_headers, request_payload, response)
        except Exception:
            sys.stderr.write(
                traceback.format_exc() +
                '\nAn exception occurred while recording the external transaction log.\n'
            )

        return response

    @staticmethod
    def before(query_params, request_params, request_headers):
        request_payload = {k: v[0] for k, v in parse_qs(query_params).items()}

        if is_char(request_params):
            request_params = try_json_loads(request_params)
        if isinstance(request_params, dict):
            request_payload.update(request_params)
        elif isinstance(request_params, (list, tuple)):
            request_payload['data'] = request_params

        if has_flask_request_context():
            transaction_id = getattr(g, '__transaction_id__', None)
        elif has_fastapi_request_context():
            transaction_id = getattr(FastAPIJournallogMiddleware.local.request.state, '__transaction_id__', None)
        else:
            transaction_id = (
                FuzzyGet(request_headers, 'Transaction-ID').v or
                FuzzyGet(request_payload, 'transaction_id').v or
                uuid.uuid4().hex
            )
        if request_headers is None:
            request_headers = {'User-Agent': this.syscode, 'Transaction-ID': transaction_id}
        elif isinstance(request_headers, dict):
            request_headers.setdefault('User-Agent', this.syscode)
            request_headers.setdefault('Transaction-ID', transaction_id)

        return request_headers, request_payload

    @staticmethod
    def after(method, parsed_url, request_time, request_headers, request_payload, response):
        method_name = FuzzyGet(request_headers, 'Method-Name').v
        if method_name is None:
            f_back = inspect.currentframe().f_back.f_back.f_back.f_back
            method_name = getattr(f_back.f_code, co_qualname)

        request_ip = parsed_url.hostname
        if not is_valid_ip(request_ip):
            request_ip = None

        journallog_logger(
            transaction_id=request_headers['Transaction-ID'],
            dialog_type='out',
            address=parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path,
            fcode=this.syscode,
            tcode=FuzzyGet(request_headers, 'T-Code').v or FuzzyGet(request_payload, 'tcode').v,
            method_code=FuzzyGet(request_headers, 'Method-Code').v or FuzzyGet(request_payload, 'method_code').v,
            method_name=method_name,
            http_method=method,
            request_time=request_time,
            request_headers=request_headers,
            request_payload=request_payload,
            response_headers=dict(response.headers),
            response_payload=try_json_loads(response.raw_body) or {},
            http_status_code=response.code,
            request_ip=request_ip
        )

    @staticmethod
    def reset_unirest_user_agent():
        unirest.USER_AGENT = this.syscode


class JournallogCectConsumer(object):

    def __init__(self, func, topic):
        self.__wrapped__ = func
        self.topic = topic

    def __call__(self, message, *a, **kw):
        request_time = datetime.now()
        code = self.__wrapped__(message, *a, **kw)
        try:
            self.after(request_time, try_json_loads(message.body) or message.body, code)
        except Exception:
            sys.stderr.write(
                traceback.format_exc() +
                '\nAn exception occurred while recording the internal transaction log.\n'
            )
        return code

    def after(self, request_time, message, code):
        journallog_logger(
            transaction_id=FuzzyGet(message, 'transaction_id').v or uuid.uuid4().hex,
            dialog_type='in',
            address=None,
            fcode=FuzzyGet(message, 'fcode').v,
            tcode=this.syscode,
            method_code=None,
            method_name=self.__wrapped__.__name__,
            http_method=None,
            request_time=request_time,
            request_headers=None,
            request_payload=message,
            response_headers=None,
            response_payload=None,
            http_status_code=None,
            request_ip=None,
            topic=self.topic,
            response_code=code
        )


def journallog_logger(
        transaction_id,    # type: Str
        dialog_type,       # type: Str
        address,           # type: Str
        fcode,             # type: Str
        tcode,             # type: Str
        method_code,       # type: Str
        method_name,       # type: Str
        http_method,       # type: Str
        request_time,      # type: datetime
        request_headers,   # type: Dict
        request_payload,   # type: Dict
        response_headers,  # type: Dict
        response_payload,  # type: Dict
        http_status_code,  # type: Int
        request_ip,        # type: Str
        **extra
):
    account_num           = fuzzy_get_many(request_payload, 'phone', 'phone_num', 'number', 'accnbr')
    response_account_num  = fuzzy_get_many(response_payload, 'phone', 'phone_num', 'accnbr', 'receive_phone')
    account_type          = None if account_num is None else '11'
    response_account_type = None if response_account_num is None else '11'

    response_time = datetime.now()
    response_time_str = response_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    total_time = (response_time - request_time).total_seconds()
    total_time = int(round(total_time * 1000))

    data = {
        'app_name': this.appname + '_info',
        'level': 'INFO',
        'log_time': response_time_str,
        'logger': __package__,
        'thread': str(threading.current_thread().ident),
        'transaction_id': transaction_id,
        'dialog_type': dialog_type,
        'address': address,
        'fcode': fcode,
        'tcode': tcode,
        'method_code': method_code,
        'method_name': method_name,
        'http_method': http_method,
        'request_time': request_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
        'request_headers': try_json_dumps(request_headers),
        'request_payload': try_json_dumps(OmitLongString(request_payload)),
        'response_time': response_time_str,
        'response_headers': try_json_dumps(response_headers),
        'response_payload': try_json_dumps(OmitLongString(response_payload)),
        'response_code': FuzzyGet(response_payload, 'code').v,
        'response_remark': None,
        'http_status_code': http_status_code,
        'order_id': fuzzy_get_many((request_payload, response_payload), 'order_id', 'ht_id'),
        'province_code': FuzzyGet(request_payload, 'province_code').v or FuzzyGet(response_payload, 'province_code').v,
        'city_code': FuzzyGet(request_payload, 'city_code').v or FuzzyGet(response_payload, 'city_code').v,
        'error_code': None,
        'request_ip': request_ip,
        'host_ip': socket.gethostbyname(socket.gethostname()),
        'host_name': socket.gethostname(),
        'account_type': account_type,
        'account_num': account_num,
        'response_account_type': response_account_type,
        'response_account_num': response_account_num,
        'user': None,
        'tag': None,
        'service_line': None
    }
    data.update(extra)

    for k, v in data.items():
        if not (v is None or is_char(v)):
            data[k] = str(v)

    data['total_time'] = total_time

    glog.info(try_json_dumps(data), gname='info_')


class OmitLongString(dict):

    def __init__(self, data):
        for name, value in data.items():
            dict.__setitem__(self, name, OmitLongString(value))

    def __new__(cls, data):
        if isinstance(data, dict):
            return dict.__new__(cls)
        if isinstance(data, (list, tuple)):
            return data.__class__(cls(v) for v in data)
        if sys.version_info.major < 3 and isinstance(data, str):
            data = data.decode('UTF-8')
        if is_char(data) and len(data) > 1000:
            data = '<Ellipsis>'
        return data


class FuzzyGet(dict):
    v = None

    def __init__(self, data, key, root=None):
        if root is None:
            if isinstance(data, (list, tuple)):
                data = {'data': data}
            self.key = key.replace('-', '').replace('_', '').lower()
            root = self
        for k, v in data.items():
            if k.replace('-', '').replace('_', '').lower() == root.key:
                root.v = data[k]
                break
            dict.__setitem__(self, k, FuzzyGet(v, key=key, root=root))

    def __new__(cls, data, key, root=None):
        if root is None and isinstance(data, (list, tuple)):
            data = {'data': data}
        if isinstance(data, dict):
            return dict.__new__(cls)
        if isinstance(data, (list, tuple)):
            return data.__class__(cls(v, key, root) for v in data)
        return cls


def has_flask_request_context():
    return Flask is not None and has_request_context()


def has_fastapi_request_context():
    return FastAPI is not None and hasattr(FastAPIJournallogMiddleware.local, 'request')


def is_valid_ip(ip):
    if sys.version_info.major < 3 and isinstance(ip, str):
        ip = ip.decode('UTF-8')
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return False
    return True


def try_json_loads(data):
    try:
        return jsonx.loads(data)
    except (ValueError, TypeError):
        pass


def try_json_dumps(data):
    try:
        return jsonx.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(data)


def fuzzy_get_many(data, *keys):
    for k in keys:
        v = FuzzyGet(data, k).v
        if v is not None:
            return v
