# coding:utf-8
import os
import sys
import json

if os.path.basename(sys.argv[0]) != 'setup.py':
    import ipaddress

if sys.version_info.major >= 3:
    from urllib.parse import urlparse, parse_qs
    is_char = lambda x: isinstance(x, str)
    PY2 = False
else:
    from urlparse import urlparse, parse_qs
    is_char = lambda x: isinstance(x, (str, unicode))
    PY2 = True

try:
    import flask as _
except ImportError:
    has_flask_request_context = lambda: False
else:
    from flask import (
        g           as flask_g,
        request     as flask_request,
        current_app as flask_current_app,
        has_request_context as has_flask_request_context
    )

try:
    import fastapi as _
except ImportError:
    FastAPITransactionLog = None
    has_fastapi_request_context = lambda: False
else:
    from .transaction_log.x_fastapi import FastAPITransactionLog
    has_fastapi_request_context = lambda: hasattr(FastAPITransactionLog.local, 'request')

CO_QUALNAME = 'co_qualname' if sys.version_info >= (3, 11) else 'co_name'


class OmitLongString(dict):

    def __init__(self, data):
        for name, value in data.items():
            dict.__setitem__(self, name, OmitLongString(value))

    def __new__(cls, data):
        if isinstance(data, dict):
            return dict.__new__(cls)
        if isinstance(data, (list, tuple)):
            return data.__class__(cls(v) for v in data)
        if PY2 and isinstance(data, str):
            data = data.decode('utf8', errors='replace')
        if is_char(data) and len(data) > 1000:
            data = '<Ellipsis>'
        return data


class FuzzyGet(dict):
    v = None

    def __init__(self, data, key, root=None):
        if root is None:
            if isinstance(data, (list, tuple)):
                data = {'data': data}
            self.key = key.replace(' ', '').replace('-', '').replace('_', '').lower()
            root = self
        for k, v in data.items():
            if k.replace(' ', '').replace('-', '').replace('_', '').lower() == root.key:
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


def get_tcode(parsed_url, request_headers, request_payload):
    tcode = FuzzyGet(request_headers, 'T-Code').v
    if tcode is None:
        tcode = parsed_url.hostname.split('.')[0]
        if not is_syscode(tcode):
            tcode = FuzzyGet(request_payload, 'tcode').v
    return tcode and tcode.upper()


def is_syscode(x):
    return len(x) == 10 and x[0].isalpha() and x[1:].isdigit()


def is_valid_ip(ip):
    if PY2 and isinstance(ip, str):
        ip = ip.decode('utf8', errors='replace')
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return False
    return True


def try_json_loads(data):
    try:
        return json.loads(data)
    except (ValueError, TypeError):
        pass


def try_json_dumps(data):
    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(data)


def fuzzy_get_many(data, *keys):
    for k in keys:
        v = FuzzyGet(data, k).v
        if v is not None:
            return v
