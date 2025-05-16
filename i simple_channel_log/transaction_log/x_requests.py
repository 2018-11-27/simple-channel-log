# coding:utf-8

from .base import TransactionLogBase


class RequestsTransactionLog(TransactionLogBase):

    def dispatch(self, *a, **kw):
        pass

    def before(self):
        pass

    def after(self):
        pass
