from typing import Any

from PySide6.QtCore import Signal, QRunnable, QObject


class ThreadingSignals(QObject):
    progress = Signal(float, str)
    """
    Argument 1: progress as float from 0 to 1
    Argument 2: progress text
    """
    result = Signal(Any, Any)
    """
    Argument 1: return value of the function
    Argument 2: any extra information given to the worker
    """

class ThreadingWorker(QRunnable):
    def __init__(self, func, extra: dict | None = None, *args, **kwargs):
        super(ThreadingWorker, self).__init__()
        self.func = func
        self.extra = extra
        self.args = args
        self.kwargs = kwargs
        self.signals = ThreadingSignals()
        self.setAutoDelete(True)

    def run(self):
        result = self.func(*self.args, progress_callback=self.emit_progress, **self.kwargs)
        self.signals.result.emit(result, self.extra)

    def emit_progress(self, progress: float=0, text: str=''):
        self.signals.progress.emit(progress, text)