# coding:utf-8
import os
import sys
import abc
import socket
import functools
import threading

from datetime import datetime

if os.path.basename(sys.argv[0]) != 'setup.py':
    import gqylpy_log as glog
    from exceptionx import TryExcept, TryContext

from ..tools import FuzzyGet, OmitLongString, is_char, fuzzy_get_many, try_json_dumps

from typing import TypeVar, Union

Str = TypeVar('Str', bound=Union[str, None])
Int = TypeVar('Int', bound=Union[int, None])
Dict = TypeVar('Dict', bound=Union[dict, None])


def exc_callback(e, *a, **kw):
    if sys.version_info >= (3, 6):
        trace = e.__traceback__.tb_next
    else:
        trace = sys.exc_info()[2].tb_next

    while trace.tb_next:
        trace = trace.tb_next

    exc_module_name = trace.tb_frame.f_globals.get('__name__')

    if exc_module_name is None:
        raise

    if exc_module_name.split('.')[0] != __package__.split('.')[0]:
        raise


def exc_callback_for_before(_, __, self, *a, **kw):
    self.after = lambda *a, **kw: None


class TransactionLogBase(object):
    __metaclass__ = abc.ABCMeta

    appname = None
    syscode = None
    output_to_terminal = False

    def __init__(self, func):
        self.__wrapped__ = func
        functools.update_wrapper(self, func)

    @TryExcept(Exception, last_tb=True, logger=None, ecallback=exc_callback)
    def __call__(self, *a, **kw):
        return self.dispatch(*a, **kw)

    def __getattribute__(self, name):
        # TODO
        bound_method = object.__getattribute__(self, name)
        if name == 'before':
            bound_method = TryExcept(
                Exception, last_tb=True, logger=None, ecallback=exc_callback_for_before
            )(bound_method)
        return bound_method

    def dispatch_v2(self, *a, **kw):
        # TODO
        self.before()
        response = self.__wrapped__(*a, **kw)
        self.after()
        return response

    @abc.abstractmethod
    def dispatch(self, *a, **kw):
        self.before()
        response = self.__wrapped__(*a, **kw)
        self.after()
        return response

    @abc.abstractmethod
    def before(self, *a, **kw):
        raise NotImplementedError

    @abc.abstractmethod
    def after(self, *a, **kw):
        raise NotImplementedError

    @staticmethod
    def logger(
            transaction_id,    # type: Str
            dialog_type,       # type: Str
            address,           # type: Str
            fcode,             # type: Str
            tcode,             # type: Str
            method_code,       # type: Str
            method_name,       # type: Str
            http_method,       # type: Str
            request_time,      # type: datetime
            response_time,     # type: datetime
            request_headers,   # type: Dict
            request_payload,   # type: Dict
            response_headers,  # type: Dict
            response_payload,  # type: Dict
            http_status_code,  # type: Int
            request_ip,        # type: Str
            **extra
    ):
        order_id      = fuzzy_get_many((request_payload, response_payload), 'order_id', 'ht_id')
        province_code = FuzzyGet(request_payload, 'province_code').v or FuzzyGet(response_payload, 'province_code').v
        city_code     = FuzzyGet(request_payload, 'city_code').v or FuzzyGet(response_payload, 'city_code').v

        account_num           = fuzzy_get_many(request_payload, 'phone', 'phone_num', 'number', 'accnbr')
        response_account_num  = fuzzy_get_many(response_payload, 'phone', 'phone_num', 'accnbr', 'receive_phone')
        account_type          = None if account_num is None else '11'
        response_account_type = None if response_account_num is None else '11'

        response_time_str = response_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        total_time = (response_time - request_time).total_seconds()
        total_time = int(round(total_time * 1000))

        data = {
            'app_name': TransactionLogBase.appname + '_info',
            'level': 'INFO',
            'log_time': response_time_str,
            'logger': 'simple_channel_log',
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
            'order_id': order_id,
            'province_code': province_code,
            'city_code': city_code,
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
