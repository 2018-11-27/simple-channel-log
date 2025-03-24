# coding:utf-8
import os
import re
import sys
import time
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
            self.before_request(journallog_inner_before)
            self.after_request(journallog_inner)
        inner.__wrapped__ = func
        return inner

    Flask.__init__ = wrap_flask_init_method(Flask.__init__)

try:
    from fastapi import FastAPI
except ImportError:
    FastAPI = None
else:
    fastapi_journallog_middleware = __import__(__package__ + '.i fastapi_journallog', fromlist=os).JournallogMiddleware

    def wrap_fastapi_init_method(func):
        @functools.wraps(func)
        def inner(self, *a, **kw):
            func(self, *a, **kw)
            self.add_middleware(fastapi_journallog_middleware)
        inner.__wrapped__ = func
        return inner

    FastAPI.__init__ = wrap_fastapi_init_method(FastAPI.__init__)

try:
    import requests
except ImportError:
    requests = None

if sys.version_info.major < 3:
    from urlparse import urlparse, parse_qs
    is_char = lambda x: isinstance(x, (str, unicode))
else:
    from urllib.parse import urlparse, parse_qs
    is_char = lambda x: isinstance(x, str)

co_qualname = 'co_qualname' if sys.version_info >= (3, 11) else 'co_name'

that = sys.modules[__package__]
this = sys.modules[__name__]

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
        warnings.warn(
            'parameter "syscode" is deprecated.',
            category=DeprecationWarning, stacklevel=2
        )
    if enable_journallog_in is not deprecated:
        warnings.warn(
            'parameter "enable_journallog_in" is deprecated.',
            category=DeprecationWarning, stacklevel=2
        )
    if enable_journallog_out is not deprecated:
        warnings.warn(
            'parameter "enable_journallog_out" is deprecated.',
            category=DeprecationWarning, stacklevel=2
        )
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
        fastapi_journallog_middleware.appname = appname
        fastapi_journallog_middleware.syscode = syscode

    if requests is not None:
        requests.Session.request = journallog_output(requests.Session.request)

    if Flask or FastAPI or requests:
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

        args = tuple(OmitLongString(v) for v in args)
        extra = OmitLongString(extra)

        if sys.version_info.major < 3 and isinstance(msg, str):
            msg = msg.decode('UTF-8')

        if is_char(msg):
            msg = msg[:1000]
            try:
                msg = msg % args
            except (TypeError, ValueError):
                pass
        elif isinstance(msg, (dict, list, tuple)):
            msg = OmitLongString(msg)

        if has_flask_request_context():
            transaction_id = getattr(g, '__transaction_id__', None)
            method_code = (
                getattr(request, 'method_code', None) or
                FuzzyGet(getattr(g, '__request_headers__', {}), 'Method-Code').v or
                FuzzyGet(getattr(g, '__request_payload__', {}), 'method_code').v
            )
        elif has_fastapi_request_context() and hasattr(glog, 'fastapi_request'):
            state = glog.fastapi_request.state
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
        level = f_back.f_code.co_name
        f_back = f_back.f_back

        data = {
            'app_name': app_name,
            'level': level.upper(),
            'log_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'logger': 'SimpleChannelLog',
            'thread': threading.current_thread().ident,
            'code_message': msg,
            'transaction_id': transaction_id,
            'method_code': method_code,
            'method_name': getattr(f_back.f_code, co_qualname),
            'error_code': None,
            'tag': None,
            'host_name': socket.gethostname(),
            'filename': f_back.f_code.co_filename,
            'line': f_back.f_lineno
        }

        for k, v in extra.items():
            if data.get(k) is not None:
                continue
            if sys.version_info.major < 3 and isinstance(v, dict):
                for kk in v.copy():
                    if isinstance(kk, str):
                        v[kk.decode('UTF-8')] = v.pop(kk)
            data[k] = try_json_dumps(v)

        getattr(glog, level)(try_json_dumps(data), gname='code')

        if this.output_to_terminal:
            getattr(glog, level)(msg, gname='stream')
    except Exception:
        sys.stderr.write(traceback.format_exc() + '\nAn exception occurred while recording the log.')


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


def journallog_inner_before():
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


def journallog_inner(response):
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
            request_ip=request.remote_addr,
            host_ip=parsed_url.hostname
        )

    except Exception:
        sys.stderr.write(
            traceback.format_exc() +
            '\nAn exception occurred while recording the internal transaction log.\n'
        )
    finally:
        return response


def journallog_output(func):

    @functools.wraps(func)
    def inner(self, method, url, headers=None, params=None, data=None, json=None, **kw):
        try:
            if headers is None:
                headers = {'User-Agent': this.syscode}
            else:
                FullDelete(headers, 'User-Agent')
                headers['User-Agent'] = this.syscode
            request_time = datetime.now()
        except Exception:
            sys.stderr.write(
                traceback.format_exc() +
                '\nAn exception occurred while recording the internal transaction log.\n'
            )
        response = func(self, method, url, headers=headers, params=params, data=data, json=json, **kw)
        try:
            parse_url = urlparse(url)
            address = parse_url.scheme + '://' + parse_url.netloc + parse_url.path

            request_payload = {k: v[0] for k, v in parse_qs(parse_url.query).items()}

            if isinstance(params, dict):
                request_payload.update(params)

            if data is not None:
                if is_char(data):
                    data = try_json_loads(data)
                if isinstance(data, dict):
                    request_payload.update(data)
                elif isinstance(data, (list, tuple)):
                    request_payload['data'] = data
            elif json is not None:
                if is_char(json):
                    json = try_json_loads(json)
                if isinstance(json, dict):
                    request_payload.update(json)
                elif isinstance(json, (list, tuple)):
                    request_payload['data'] = json

            if has_flask_request_context():
                transaction_id = getattr(g, '__transaction_id__', None)
            elif has_fastapi_request_context():
                try:
                    transaction_id = glog.fastapi_request.state.__transaction_id__
                except AttributeError:
                    transaction_id = None
            else:
                transaction_id = (
                    FuzzyGet(headers, 'Transaction-ID').v or
                    FuzzyGet(request_payload, 'transaction_id').v or
                    uuid.uuid4().hex
                )
            FullDelete(headers, 'Transaction-ID')
            headers['Transaction-ID'] = transaction_id

            method_code = FuzzyGet(headers, 'Method-Code').v or FuzzyGet(request_payload, 'method_code').v
            tcode = FuzzyGet(headers, 'T-Code').v or FuzzyGet(request_payload, 'tcode').v

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

            journallog_logger(
                transaction_id=transaction_id,
                dialog_type='out',
                address=address,
                fcode=this.syscode,
                tcode=tcode,
                method_code=method_code,
                method_name=method_name,
                http_method=response.request.method,
                request_time=request_time,
                request_headers=dict(response.request.headers),
                request_payload=request_payload,
                response_headers=dict(response.headers),
                response_payload=response_payload,
                http_status_code=response.status_code,
                request_ip=parse_url.hostname,
                host_ip=socket.gethostbyname(socket.gethostname())
            )
        except Exception:
            sys.stderr.write(
                traceback.format_exc() +
                '\nAn exception occurred while recording the internal transaction log.\n'
            )
        finally:
            return response

    inner.__wrapped__ = func
    return inner


def journallog_logger(
        transaction_id,    # type: str
        dialog_type,       # type: str
        address,           # type: str
        fcode,             # type: str
        tcode,             # type: str
        method_code,       # type: str
        method_name,       # type: str
        http_method,       # type: str
        request_time,      # type: datetime
        request_headers,   # type: dict
        request_payload,   # type: dict
        response_headers,  # type: dict
        response_payload,  # type: dict
        http_status_code,  # type: int
        request_ip,        # type: str
        host_ip,           # type: str
):
    response_code = FuzzyGet(response_payload, 'code').v
    # order_id      = FuzzyGet(request_payload, 'order_id').v or FuzzyGet(response_payload, 'order_id').v
    # province_code = FuzzyGet(request_payload, 'province_code').v or FuzzyGet(response_payload, 'order_id').v
    # city_code     = FuzzyGet(request_payload, 'city_code').v or FuzzyGet(response_payload, 'order_id').v
    # account_type  = FuzzyGet(request_payload, 'account_type').v or FuzzyGet(response_payload, 'order_id').v
    # account_num   = FuzzyGet(request_payload, 'account_num').v or FuzzyGet(response_payload, 'order_id').v
    # response_account_type = \
    #     FuzzyGet(request_payload, 'response_account_type').v or FuzzyGet(response_payload, 'order_id').v
    # response_account_num = \
    #     FuzzyGet(request_payload, 'response_account_num').v or FuzzyGet(response_payload, 'order_id').v

    if isinstance(response_code, int):
        response_code = str(response_code)
    # if isinstance(province_code, int):
    #     province_code = str(province_code)
    # if isinstance(city_code, int):
    #     city_code = str(city_code)
    # if isinstance(account_type, int):
    #     account_type = str(account_type)
    # if isinstance(account_num, int):
    #     account_num = str(account_num)
    # if isinstance(response_account_type, int):
    #     response_account_type = str(response_account_type)
    # if isinstance(response_account_num, int):
    #     response_account_num = str(response_account_num)

    order_id              = None
    province_code         = None
    city_code             = None
    account_type          = None
    account_num           = None
    response_account_type = None
    response_account_num  = None

    request_headers_str  = try_json_dumps(request_headers)
    request_payload_str  = try_json_dumps(OmitLongString(request_payload))
    response_headers_str = try_json_dumps(response_headers)
    response_payload_str = try_json_dumps(OmitLongString(response_payload))

    response_time = datetime.now()
    response_time_str = response_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    total_time = (response_time - request_time).total_seconds()
    total_time = int(round(total_time * 1000))

    glog.info(try_json_dumps({
        'app_name': this.appname + '_info',
        'level': 'INFO',
        'log_time': response_time_str,
        'logger': 'SimpleChannelLog',
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
        'request_headers': request_headers_str,
        'request_payload': request_payload_str,
        'response_time': response_time_str,
        'response_headers': response_headers_str,
        'response_payload': response_payload_str,
        'response_code': response_code,
        'response_remark': None,
        'http_status_code': str(http_status_code),
        'order_id': order_id,
        'province_code': province_code,
        'city_code': city_code,
        'total_time': total_time,
        'error_code': response_code,
        'request_ip': request_ip,
        'host_ip': host_ip,
        'host_name': socket.gethostname(),
        'account_type': account_type,
        'account_num': account_num,
        'response_account_type': response_account_type,
        'response_account_num': response_account_num,
        'user': None,
        'tag': None,
        'service_line': None
    }), gname='info_')


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
            self.key = key.replace('-', '').replace('_', '').lower()
            root = self
        for k, v in data.items():
            if k.replace('-', '').replace('_', '').lower() == root.key:
                root.v = data[k]
                break
            dict.__setitem__(self, k, FuzzyGet(v, key=key, root=root))

    def __new__(cls, data, *a, **kw):
        if isinstance(data, dict):
            return dict.__new__(cls)
        if isinstance(data, (list, tuple)):
            return data.__class__(cls(v, *a, **kw) for v in data)
        return cls


class FullDelete(dict):

    def __init__(self, data, key, root=None):
        if root is None:
            self.key = key.replace('-', '').replace('_', '').lower()
            root = self
        result = []
        for k, v in data.items():
            if k.replace('-', '').replace('_', '').lower() == root.key:
                result.append(k)
                continue
            dict.__setitem__(self, k, FullDelete(v, key=key, root=root))
        for k in result:
            try:
                del data[k]
            except (KeyError, RuntimeError):
                pass

    def __new__(cls, data, *a, **kw):
        if isinstance(data, dict):
            return dict.__new__(cls)
        if isinstance(data, (list, tuple)):
            return data.__class__(cls(v, *a, **kw) for v in data)
        return cls


def has_flask_request_context():
    return Flask is not None and has_request_context()


def has_fastapi_request_context():
    return FastAPI is not None and hasattr(glog, 'fastapi_request')


def try_json_loads(data):
    try:
        return jsonx.loads(data)
    except (ValueError, TypeError):
        return


def try_json_dumps(data):
    try:
        return jsonx.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(data)
