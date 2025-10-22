from PySide6.QtCore import Slot, Signal, QRunnable, QObject


class ThreadingSignals(QObject):
    progress = Signal(object)
    result = Signal(tuple)

class ThreadingWorker(QRunnable):
    def __init__(self, func, extra: dict | None = None, *args, **kwargs):
        super(ThreadingWorker, self).__init__()
        self.func = func
        self.extra = extra
        self.args = args
        self.kwargs = kwargs
        self.signals = ThreadingSignals()

    @Slot()
    def run(self):
        result = self.func(*self.args, progress_callback=self.emit_progress, **self.kwargs)
        self.signals.result.emit((result, self.extra))

    def emit_progress(self, data):
        self.signals.progress.emit(data)