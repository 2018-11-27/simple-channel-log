# coding:utf-8

from .base import TransactionLogBase


class CTECConsumerTransactionLog(TransactionLogBase):

    def __init__(self, func, topic):
        TransactionLogBase.__init__(self, func)
        self.topic = topic

    def dispatch(self, *a, **kw):
        pass

    def before(self):
        pass

    def after(self):
        pass
