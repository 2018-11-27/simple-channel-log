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
import threading

from datetime import datetime

if os.path.basename(sys.argv[0]) != 'setup.py':
    import gqylpy_log as glog

try:
    from flask import Flask
except ImportError:
    Flask = None
else:
    from flask import g
    from flask import request
    from flask import current_app
    from flask import has_request_context

    if not hasattr(Flask, '__apps__'):
        def wrap_flask_init_method(func):
            @functools.wraps(func)
            def inner(self, *a, **kw):
                func(self, *a, **kw)
                Flask.__apps__.append(self)
            return inner

        Flask.__apps__ = []
        Flask.__init__ = wrap_flask_init_method(Flask.__init__)

try:
    import requests
except ImportError:
    requests = None

if sys.version_info.major < 3:
    from urlparse import urlparse
    from urlparse import parse_qs
else:
    from urllib.parse import urlparse
    from urllib.parse import parse_qs

    unicode = str

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
        raise RuntimeError('repeat initialization.')

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
            'parameter "stream" will be deprecated soon, replaced to '
            '"output_to_terminal".', category=DeprecationWarning,
            stacklevel=2
        )
        if output_to_terminal is None:
            output_to_terminal = stream

    that.appname = this.appname = appname = \
        appname[0].lower() + appname[1:].replace('-', '_')
    that.syscode = this.syscode = prefix.group()[:-1].upper()
    this.output_to_terminal = output_to_terminal

    if sys.platform == 'win32':
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

    if Flask is not None:
        thread = threading.Thread(target=register_flask_journallog)
        thread.name = 'RegisterFlaskJournallog'
        thread.daemon = True
        thread.start()

    if requests is not None:
        requests.Session.request = journallog_out(requests.Session.request)

    if not (Flask is None and requests is None):
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


def register_flask_journallog():
    start = time.time()
    while not Flask.__apps__ and time.time() - start < 300:
        time.sleep(.01)

    for app in Flask.__apps__:
        app.before_request(journallog_in_before)
        app.after_request(journallog_in)


def logger(msg, *args, **extra):
    try:
        app_name = this.appname + '_code'
    except AttributeError:
        raise RuntimeError('uninitialized.')

    args = tuple(OmitLongString(v) for v in args)
    extra = OmitLongString(extra)

    if sys.version_info.major < 3 and isinstance(msg, str):
        msg = msg.decode('utf8')

    if isinstance(msg, unicode):
        msg = (msg % args)[:1000]
    elif isinstance(msg, (dict, list, tuple)):
        msg = OmitLongString(msg)

    if Flask is not None and has_request_context():
        transaction_id = g.__transaction_id__
        method_code = (
            getattr(request, 'method_code', None) or
            DictGet(g.__request_headers__, 'Method-Code').result or
            DictGet(g.__request_data__, 'method_code').result
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
        'logger': __package__,
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
                    v[kk.decode('utf8')] = v.pop(kk)
        try:
            data[k] = jsonx.dumps(v, ensure_ascii=False)
        except ValueError:
            data[k] = str(v)

    getattr(glog, level)(jsonx.dumps(data, ensure_ascii=False), gname='code')

    if this.output_to_terminal:
        getattr(glog, level)(msg, gname='stream')


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
    glog.debug(jsonx.dumps(extra, ensure_ascii=False), gname='trace')


def journallog_in_before():
    if request.path == '/healthcheck':
        return

    if not hasattr(g, '__request_time__'):
        g.__request_time__ = datetime.now()

    if not hasattr(g, '__request_headers__'):
        g.__request_headers__ = dict(request.headers)

    if not hasattr(g, '__request_data__'):
        if request.args:
            request_data = request.args.to_dict()
        elif request.form:
            request_data = request.form.to_dict()
        else:
            request_body = request.data
            try:
                request_data = jsonx.loads(request_body) \
                    if request_body else None
            except ValueError:
                request_data = None
        g.__request_data__ = request_data

    g.__transaction_id__ = (
        DictGet(g.__request_headers__, 'Transaction-ID').result or
        DictGet(g.__request_data__, 'transaction_id').result or
        uuid.uuid4().hex
    )


def journallog_in(response):
    if request.path == '/healthcheck':
        return response

    parsed_url = urlparse(request.url)
    address = parsed_url.scheme + '://' + parsed_url.netloc + parsed_url.path
    method_code = (
        getattr(request, 'method_code', None) or
        DictGet(g.__request_headers__, 'Method-Code').result or
        DictGet(g.__request_data__, 'method_code').result
    )

    view_func = current_app.view_functions.get(request.endpoint)
    method_name = view_func.__name__ if view_func else None

    try:
        response_data = jsonx.loads(response.get_data())
    except ValueError:
        response_data = response_code = order_id = \
            province_code = city_code = \
            account_type = account_num = \
            response_account_type = response_account_num = None
    else:
        if isinstance(response_data, dict):
            head = response_data.get('head')
            x = head if isinstance(head, dict) else response_data
            response_code = x.get('code')
            order_id = x.get('order_id')
            province_code = x.get('province_code')
            city_code = x.get('city_code')
            account_type = x.get('account_type')
            account_num = x.get('account_num')
            response_account_type = x.get('response_account_type')
            response_account_num = x.get('response_account_num')
            if response_code is not None:
                response_code = str(response_code)
        else:
            response_code = order_id = \
                province_code = city_code = \
                account_type = account_num = \
                response_account_type = response_account_num = None

    request_headers_str = jsonx.dumps(g.__request_headers__, ensure_ascii=False)
    request_payload_str = \
        jsonx.dumps(OmitLongString(g.__request_data__), ensure_ascii=False)
    response_headers_str = \
        jsonx.dumps(dict(response.headers), ensure_ascii=False)
    response_payload_str = \
        jsonx.dumps(OmitLongString(response_data), ensure_ascii=False)

    request_time_str = g.__request_time__.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    response_time = datetime.now()
    response_time_str = response_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    total_time = \
        int(round((response_time - g.__request_time__).total_seconds() * 1000))

    glog.info(jsonx.dumps({
        'app_name': this.appname + '_info',
        'level': 'INFO',
        'log_time': response_time_str,
        'logger': __package__,
        'thread': str(threading.current_thread().ident),
        'transaction_id': g.__transaction_id__,
        'dialog_type': 'in',
        'address': address,
        'fcode': DictGet(g.__request_headers__, 'User-Agent').result,
        'tcode': this.syscode,
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
        'request_ip': request.remote_addr,
        'host_ip': parsed_url.hostname,
        'host_name': socket.gethostname(),
        'account_type': account_type,
        'account_num': account_num,
        'response_account_type': response_account_type,
        'response_account_num': response_account_num,
        'user': None,
        'tag': None,
        'service_line': None
    }, ensure_ascii=False), gname='info_')

    return response


def journallog_out(func):

    @functools.wraps(func)
    def inner(
            self, method, url,
            headers=None, params=None, data=None, json=None,
            **kw
    ):
        if headers is None:
            headers = {'User-Agent': this.syscode}
        else:
            DictDelete(headers, 'User-Agent')
            headers['User-Agent'] = this.syscode

        parse_url = urlparse(url)
        address = parse_url.scheme + '://' + parse_url.netloc + parse_url.path
        query_string = {k: v[0] for k, v in parse_qs(parse_url.query).items()}

        if params is not None:
            params.update(query_string)
            request_data = params
        elif query_string:
            request_data = query_string
        elif data:
            request_data = data
            if isinstance(request_data, (str, unicode)):
                try:
                    request_data = jsonx.loads(request_data)
                except ValueError:
                    pass
        elif json:
            request_data = json
        else:
            request_data = None

        if Flask is not None and has_request_context():
            transaction_id = g.__transaction_id__
        else:
            transaction_id = (
                DictGet(headers, 'Transaction-ID').result or
                DictGet(request_data, 'transaction_id').result or
                uuid.uuid4().hex
            )
        DictDelete(headers, 'Transaction-ID')
        headers['Transaction-ID'] = transaction_id

        method_code = (
            DictGet(headers, 'Method-Code').result or
            DictGet(request_data, 'method_code').result
        )

        method_name = DictGet(headers, 'Method-Code').result
        if method_name is None:
            f_back = inspect.currentframe().f_back.f_back
            if f_back.f_back is not None:
                f_back = f_back.f_back
            method_name = getattr(f_back.f_code, co_qualname)

        request_time = datetime.now()
        response = func(
            self, method, url,
            headers=headers, params=params, data=data, json=json,
            **kw
        )
        response_time = datetime.now()
        response_time_str = response_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        try:
            response_data = response.json()
        except ValueError:
            response_data = response_code = order_id = \
                province_code = city_code = \
                account_type = account_num = \
                response_account_type = response_account_num = None
        else:
            if isinstance(response_data, dict):
                head = response_data.get('head')
                x = head if isinstance(head, dict) else response_data
                response_code = x.get('code')
                order_id = x.get('order_id')
                province_code = x.get('province_code')
                city_code = x.get('city_code')
                account_type = x.get('account_type')
                account_num = x.get('account_num')
                response_account_type = x.get('response_account_type')
                response_account_num = x.get('response_account_num')
                if response_code is not None:
                    response_code = str(response_code)
            else:
                response_code = order_id = \
                    province_code = city_code = \
                    account_type = account_num = \
                    response_account_type = response_account_num = None

        request_headers_str = \
            jsonx.dumps(dict(response.request.headers), ensure_ascii=False)
        request_payload_str = \
            jsonx.dumps(OmitLongString(request_data), ensure_ascii=False)
        response_headers_str = \
            jsonx.dumps(dict(response.headers), ensure_ascii=False)
        response_payload_str = \
            jsonx.dumps(OmitLongString(response_data), ensure_ascii=False)

        total_time = \
            int(round((response_time - request_time).total_seconds() * 1000))

        glog.info(jsonx.dumps({
            'app_name': this.appname + '_info',
            'level': 'INFO',
            'log_time': response_time_str,
            'logger': __package__,
            'thread': str(threading.current_thread().ident),
            'transaction_id': transaction_id,
            'dialog_type': 'out',
            'address': address,
            'fcode': this.syscode,
            'tcode': this.syscode,
            'method_code': method_code,
            'method_name': method_name,
            'http_method': response.request.method,
            'request_time': request_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
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
            'request_ip': parse_url.hostname,
            'host_ip': socket.gethostbyname(socket.gethostname()),
            'host_name': socket.gethostname(),
            'account_type': account_type,
            'account_num': account_num,
            'response_account_type': response_account_type,
            'response_account_num': response_account_num,
            'user': None,
            'tag': None,
            'service_line': None
        }, ensure_ascii=False), gname='info_')

        return response

    inner.__wrapped__ = func
    return inner


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
            data = data.decode('utf8')
        if isinstance(data, (unicode, str)) and len(data) > 1000:
            data = '<Ellipsis>'
        return data


class DictGet(dict):
    result = None

    def __init__(self, data, key, root=None):
        if root is None:
            self.key = key.replace('-', '').replace('_', '').lower()
            root = self
        for k, v in data.items():
            if k.replace('-', '').replace('_', '').lower() == root.key:
                root.result = data[k]
                break
            dict.__setitem__(self, k, DictGet(v, key=key, root=root))

    def __new__(cls, data, *a, **kw):
        if isinstance(data, dict):
            return dict.__new__(cls)
        if isinstance(data, (list, tuple)):
            return data.__class__(cls(v, *a, **kw) for v in data)
        return cls


class DictDelete(dict):

    def __init__(self, data, key, root=None):
        if root is None:
            self.key = key.replace('-', '').replace('_', '').lower()
            root = self
        result = []
        for k, v in data.items():
            if k.replace('-', '').replace('_', '').lower() == root.key:
                result.append(k)
                continue
            dict.__setitem__(self, k, DictDelete(v, key=key, root=root))
        for k in result:
            del data[k]

    def __new__(cls, data, *a, **kw):
        if isinstance(data, dict):
            return dict.__new__(cls)
        if isinstance(data, (list, tuple)):
            return data.__class__(cls(v, *a, **kw) for v in data)
        return cls
