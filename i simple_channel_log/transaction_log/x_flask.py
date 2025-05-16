# coding:utf-8

from .base import TransactionLogBase


class FlaskTransactionLog(TransactionLogBase):

    def __init__(self, app):
        self.app = app  # 原始 WSGI 应用

    def dispatch(self, environ, start_response):
        self.before()
        # 调用下层应用（例如 Flask 的 wsgi_app）
        response = self.app(environ, start_response)
        self.after()
        return response

    def before(self):
        pass

    def after(self):
        pass
