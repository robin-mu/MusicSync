import logging
from enum import StrEnum


class classproperty:
    def __init__(self, func):
        self.func = func
    def __get__(self, instance, owner):
        return self.func(owner)


class GuiStrEnum(StrEnum):
    def __new__(cls, value, gui_string, gui_status_tip):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._sort_key = len(cls.__members__)
        obj._gui_string = gui_string
        obj._gui_status_tip = gui_status_tip
        return obj

    @property
    def sort_key(self) -> int:
        return self._sort_key

    @property
    def gui_string(self) -> str:
        return self._gui_string

    @property
    def gui_status_tip(self) -> str:
        return self._gui_status_tip

class Logger:
    logger = logging.getLogger('MusicSync')

    def __init__(self, prefix: str=''):
        self.prefix = prefix
        self.indent_tabs = 0

    def format_msg(self, msg: str, *args, **kwargs) -> str:
        return f'{"    " * self.indent_tabs}{msg}'

    def indent(self, by: int=1):
        self.indent_tabs += by

    def reset_indent(self):
        self.indent_tabs = 0

    def debug(self, msg: str, *args, **kwargs):
        if self.prefix == 'yt-dlp':
            if not msg.startswith('[debug] '):
                self.info(msg, *args, **kwargs)
                return
            msg = msg[8:]

        msg = self.format_msg(msg, *args, **kwargs)
        Logger.logger.debug(msg, extra={'prefix': self.prefix})

    def info(self, msg: str, *args, **kwargs):
        msg = self.format_msg(msg, *args, **kwargs)
        Logger.logger.info(msg, extra={'prefix': self.prefix})

    def warning(self, msg: str, *args, **kwargs):
        msg = self.format_msg(msg, *args, **kwargs)
        Logger.logger.warning(msg, extra={'prefix': self.prefix})

    def error(self, msg: str, *args, **kwargs):
        msg = self.format_msg(msg, *args, **kwargs)
        Logger.logger.error(msg, extra={'prefix': self.prefix})

    def critical(self, msg: str, *args, **kwargs):
        msg = self.format_msg(msg, *args, **kwargs)
        Logger.logger.critical(msg, extra={'prefix': self.prefix})