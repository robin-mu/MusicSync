from typing import Any

from PySide6.QtCore import Signal, QRunnable, QObject, Slot


class ThreadingWorker(QObject):
    progress = Signal(float, str)
    result = Signal(Any, Any)

    def __init__(self, func, extra: dict | None = None, *args, **kwargs):
        super(ThreadingWorker, self).__init__()
        self.func = func
        self.extra = extra
        self.args = args
        self.kwargs = kwargs

    @Slot()
    def run(self):
        result = self.func(*self.args, progress_callback=self.emit_progress, **self.kwargs)
        self.result.emit(result, self.extra)

    def emit_progress(self, progress: float=0, text: str=''):
        self.progress.emit(progress, text)