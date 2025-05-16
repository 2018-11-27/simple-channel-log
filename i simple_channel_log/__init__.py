# coding:utf-8
import re
import os
import sys
import threading

if os.path.basename(sys.argv[0]) != 'setup.py':
    import gqylpy_log as glog

from .program_log import logger as program_logger
from .transaction_log.base import TransactionLogBase as Config
from .tools import PY2, OmitLongString, try_json_dumps

try:
    from flask import Flask
except ImportError:
    Flask = None

try:
    from fastapi import FastAPI
except ImportError:
    FastAPI = None

try:
    import requests
except ImportError:
    pass

try:
    import unirest
except ImportError:
    pass
else:
    from .transaction_log.x_unirest import UnirestTransactionLog

try:
    import ctec_consumer
except ImportError:
    pass


def __init__(
        appname,
        logdir            =r'C:\BllLogs' if sys.platform == 'win32' else '/app/logs',
        when              ='D',
        interval          =1,
        backup_count      =7,
        output_to_terminal=None,
):
    if Config.appname is not None:
        return

    prefix = re.match(r'[a-zA-Z]\d{9}[_-]', appname)
    if prefix is None:
        raise ValueError('parameter appname "%s" is illegal.' % appname)

    appname = appname[0].lower() + appname[1:].replace('-', '_')
    syscode = prefix.group()[:-1].upper()

    Config.appname = appname
    Config.syscode = syscode
    Config.output_to_terminal = output_to_terminal

    if sys.platform == 'win32' and logdir == r'C:\BllLogs':
        logdir = os.path.join(logdir, appname)

    handlers = [{
        'name': 'TimedRotatingFileHandler',
        'level': 'DEBUG',
        'filename': '%s/debug/%s_code-debug.log' % (logdir, appname),
        'encoding': 'utf8',
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
            'encoding': 'utf8',
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

    if unirest is not None:
        unirest.USER_AGENT = syscode
        threading.Timer(15, UnirestTransactionLog.reset_unirest_user_agent)

    if Flask or FastAPI or requests or unirest or ctec_consumer:
        glog.__init__(
            'info',
            handlers=[{
                'name': 'TimedRotatingFileHandler',
                'level': 'INFO',
                'filename': '%s/%s_info-info.log' % (logdir, appname),
                'encoding': 'utf8',
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
            'encoding': 'utf8',
            'when': when,
            'interval': interval,
            'backupCount': backup_count,
        }],
        gname='trace'
    )


def debug(msg, *args, **extra):
    program_logger(msg, *args, **extra)


def info(msg, *args, **extra):
    program_logger(msg, *args, **extra)


def warning(msg, *args, **extra):
    program_logger(msg, *args, **extra)


warn = warning


def error(msg, *args, **extra):
    program_logger(msg, *args, **extra)


exception = error


def critical(msg, *args, **extra):
    program_logger(msg, *args, **extra)


fatal = critical


def trace(**extra):
    extra = OmitLongString(extra)
    extra.update({'app_name': Config.appname + '_trace', 'level': 'TRACE'})
    glog.debug(try_json_dumps(extra), gname='trace')


def set_method_code(method_code):
    def inner(func):
        try:
            func.__method_code__ = method_code
        except Exception as e:
            funcname = getattr(func, '__name__', func)
            emsg = 'Set method code "%s" to api handler "%s" error: %s' % (method_code, funcname, repr(e))
            sys.stderr.write('\n' + emsg + '\n') if PY2 else warning(emsg)
        return func
    return inner
