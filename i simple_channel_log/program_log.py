# coding:utf-8
import os
import sys
import uuid
import socket
import inspect
import threading
import traceback

from datetime import datetime

if os.path.basename(sys.argv[0]) != 'setup.py':
    import gqylpy_log as glog

from .tools import (
    PY2, CO_QUALNAME, is_char, OmitLongString, FuzzyGet, try_json_dumps,
    flask_g, flask_request, flask_current_app, has_flask_request_context,
    has_fastapi_request_context, FastAPITransactionLog
)

from .transaction_log.base import TransactionLogBase as Config


def logger(msg, *args, **extra):
    if Config.appname is None:
        raise RuntimeError('uninitialized.')

    try:
        app_name = Config.appname + '_code'

        args, extra = OmitLongString(args), OmitLongString(extra)

        if PY2 and isinstance(msg, str):
            msg = msg.decode('utf8', errors='replace')

        if is_char(msg):
            try:
                msg = msg % args
            except (TypeError, ValueError):
                pass
            msg = msg[:3000]
        elif isinstance(msg, (dict, list, tuple)):
            msg = OmitLongString(msg)

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
            transaction_id = uuid.uuid4().hex
            method_code = None

        f_back = inspect.currentframe().f_back
        level  = f_back.f_code.co_name

        f_back = f_back.f_back
        module = f_back.f_globals.get('__name__', '<NotFound>')
        name   = getattr(f_back.f_code, CO_QUALNAME)
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
            'method_name': getattr(f_back.f_code, CO_QUALNAME),
            'error_code': None,
            'tag': None,
            'host_name': socket.gethostname()
        }

        for k, v in extra.items():
            if data.get(k) is None:
                data[k] = try_json_dumps(v) if isinstance(v, (dict, list, tuple)) else str(v)

        getattr(glog, level)(try_json_dumps(data), gname='code')

        if Config.output_to_terminal:
            if module != Config.__module__:
                msg = '[%s] %s' % (logger_, msg)
            getattr(glog, level)(msg, gname='stream')
    except Exception:
        sys.stderr.write(traceback.format_exc() + '\nAn exception occurred while recording the log.\n')
