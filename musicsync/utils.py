import logging
from enum import StrEnum
import yt_dlp
import yt_dlp.options


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

    def format_msg(self, msg: str, *_, **__) -> str:
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


create_parser = yt_dlp.options.create_parser


def parse_patched_options(opts):
    patched_parser = create_parser()
    patched_parser.defaults.update({
        'ignoreerrors': False,
        'retries': 0,
        'fragment_retries': 0,
        'extract_flat': False,
        'concat_playlist': 'never',
        'update_self': False,
    })
    yt_dlp.options.create_parser = lambda: patched_parser
    try:
        return yt_dlp.parse_options(opts)
    finally:
        yt_dlp.options.create_parser = create_parser


default_opts = parse_patched_options([]).ydl_opts


def cli_to_api(opts, cli_defaults=False):
    opts = (yt_dlp.parse_options if cli_defaults else parse_patched_options)(opts).ydl_opts

    diff = {k: v for k, v in opts.items() if default_opts[k] != v}
    if 'postprocessors' in diff:
        diff['postprocessors'] = [pp for pp in diff['postprocessors']
                                  if pp not in default_opts['postprocessors']]
    return diff