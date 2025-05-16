# coding:utf-8
import functools

try:
    from flask import Flask
except ImportError:
    pass
else:
    from .x_flask import FlaskTransactionLog

    def wrap_flask_init_method(func):
        @functools.wraps(func)
        def inner(self, *a, **kw):
            func(self, *a, **kw)
            self.wsgi_app = FlaskTransactionLog(self.wsgi_app)
        inner.__wrapped__ = func
        return inner

    Flask.wsgi_app = wrap_flask_init_method(Flask.__init__)

try:
    from fastapi import FastAPI
except ImportError:
    pass
else:
    from .x_fastapi import FastAPITransactionLog

    def wrap_fastapi_init_method(func):
        @functools.wraps(func)
        def inner(self, *a, **kw):
            func(self, *a, **kw)
            self.add_middleware(FastAPITransactionLog)
        inner.__wrapped__ = func
        return inner

    FastAPI.__init__ = wrap_fastapi_init_method(FastAPI.__init__)

try:
    import requests
except ImportError:
    pass
else:
    from .x_requests import RequestsTransactionLog
    requests.Session.request = RequestsTransactionLog(requests.Session.request)

try:
    import unirest
except ImportError:
    pass
else:
    from .x_unirest import UnirestTransactionLog
    unirest.__request = UnirestTransactionLog(unirest.__request)

try:
    from ctec_consumer.dummy.ctec_consumer import Consumer
except ImportError:
    pass
else:
    from .x_ctec_consumer import CTECConsumerTransactionLog

    def wrap_register_worker(func):
        @functools.wraps(func)
        def inner(self, worker):
            func(self, CTECConsumerTransactionLog(worker, topic=self.queue))
        inner.__wrapped__ = func
        return inner

    Consumer.register_worker = wrap_register_worker(Consumer.register_worker)
