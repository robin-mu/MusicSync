# Copied from https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py
# at commit https://github.com/yt-dlp/yt-dlp/commit/5bf91072bcfbb26e6618d668a0b3379a3a862f8c
# modified so that output template evaluation is possible without a YoutubeDL-object

import time
import re
import sys
import string
import json
import unicodedata

from yt_dlp.utils import (
    formatSeconds,
    number_of_digits,
    STR_FORMAT_RE_TMPL,
    STR_FORMAT_TYPES,
    NUMBER_RE,
    int_or_none,
    traverse_obj,
    float_or_none,
    strftime_or_none,
    sanitize_filename,
    NO_DEFAULT,
    LazyList,
    variadic,
    escapeHTML,
    shell_quote,
    format_decimal_suffix
)

def _copy_infodict(info_dict):
    info_dict = dict(info_dict)
    info_dict.pop('__postprocessors', None)
    info_dict.pop('__pending_error', None)
    return info_dict

def format_resolution(format, default='unknown'):
    if format.get('vcodec') == 'none' and format.get('acodec') != 'none':
        return 'audio only'
    if format.get('resolution') is not None:
        return format['resolution']
    if format.get('width') and format.get('height'):
        return '%dx%d' % (format['width'], format['height'])
    elif format.get('height'):
        return '{}p'.format(format['height'])
    elif format.get('width'):
        return '%dx?' % format['width']
    return default

def prepare_outtmpl(outtmpl, info_dict, params=None, sanitize=False):
    """ Make the outtmpl and info_dict suitable for substitution: ydl.escape_outtmpl(outtmpl) % info_dict
    @param sanitize    Whether to sanitize the output as a filename
    """

    if params is None:
        params = {}

    info_dict.setdefault('epoch', int(time.time()))  # keep epoch consistent once set

    info_dict = _copy_infodict(info_dict)
    info_dict['duration_string'] = (  # %(duration>%H-%M-%S)s is wrong if duration > 24hrs
        formatSeconds(info_dict['duration'], '-' if sanitize else ':')
        if info_dict.get('duration', None) is not None
        else None)

    # TODO write _num_downloads and _num_videos into info dict
    info_dict['autonumber'] = int(params.get('autonumber_start', 1) - 1 + info_dict.get('_num_downloads', 0))
    info_dict['video_autonumber'] = info_dict.get('_num_videos', 0)
    if info_dict.get('resolution') is None:
        info_dict['resolution'] = format_resolution(info_dict, default=None)

    # For fields playlist_index, playlist_autonumber and autonumber convert all occurrences
    # of %(field)s to %(field)0Nd for backward compatibility
    field_size_compat_map = {
        'playlist_index': number_of_digits(info_dict.get('__last_playlist_index') or 0),
        'playlist_autonumber': number_of_digits(info_dict.get('n_entries') or 0),
        'autonumber': params.get('autonumber_size') or 5,
    }

    TMPL_DICT = {}
    EXTERNAL_FORMAT_RE = re.compile(STR_FORMAT_RE_TMPL.format('[^)]*', f'[{STR_FORMAT_TYPES}ljhqBUDS]'))
    MATH_FUNCTIONS = {
        '+': float.__add__,
        '-': float.__sub__,
        '*': float.__mul__,
    }
    # Field is of the form key1.key2...
    # where keys (except first) can be string, int, slice or "{field, ...}"
    FIELD_INNER_RE = r'(?:\w+|%(num)s|%(num)s?(?::%(num)s?){1,2})' % {'num': r'(?:-?\d+)'}  # noqa: UP031
    FIELD_RE = r'\w*(?:\.(?:%(inner)s|{%(field)s(?:,%(field)s)*}))*' % {  # noqa: UP031
        'inner': FIELD_INNER_RE,
        'field': rf'\w*(?:\.{FIELD_INNER_RE})*',
    }
    MATH_FIELD_RE = rf'(?:{FIELD_RE}|-?{NUMBER_RE})'
    MATH_OPERATORS_RE = r'(?:{})'.format('|'.join(map(re.escape, MATH_FUNCTIONS.keys())))
    INTERNAL_FORMAT_RE = re.compile(rf'''(?xs)
        (?P<negate>-)?
        (?P<fields>{FIELD_RE})
        (?P<maths>(?:{MATH_OPERATORS_RE}{MATH_FIELD_RE})*)
        (?:>(?P<strf_format>.+?))?
        (?P<remaining>
            (?P<alternate>(?<!\\),[^|&)]+)?
            (?:&(?P<replacement>.*?))?
            (?:\|(?P<default>.*?))?
        )$''')

    def _from_user_input(field):
        if field == ':':
            return ...
        elif ':' in field:
            return slice(*map(int_or_none, field.split(':')))
        elif int_or_none(field) is not None:
            return int(field)
        return field

    def _traverse_infodict(fields):
        fields = [f for x in re.split(r'\.({.+?})\.?', fields)
                  for f in ([x] if x.startswith('{') else x.split('.'))]
        for i in (0, -1):
            if fields and not fields[i]:
                fields.pop(i)

        for i, f in enumerate(fields):
            if not f.startswith('{'):
                fields[i] = _from_user_input(f)
                continue
            assert f.endswith('}'), f'No closing brace for {f} in {fields}'
            fields[i] = {k: list(map(_from_user_input, k.split('.'))) for k in f[1:-1].split(',')}

        return traverse_obj(info_dict, fields, traverse_string=True)

    def get_value(mdict):
        # Object traversal
        value = _traverse_infodict(mdict['fields'])
        # Negative
        if mdict['negate']:
            value = float_or_none(value)
            if value is not None:
                value *= -1
        # Do maths
        offset_key = mdict['maths']
        if offset_key:
            value = float_or_none(value)
            operator = None
            while offset_key:
                item = re.match(
                    MATH_FIELD_RE if operator else MATH_OPERATORS_RE,
                    offset_key).group(0)
                offset_key = offset_key[len(item):]
                if operator is None:
                    operator = MATH_FUNCTIONS[item]
                    continue
                item, multiplier = (item[1:], -1) if item[0] == '-' else (item, 1)
                offset = float_or_none(item)
                if offset is None:
                    offset = float_or_none(_traverse_infodict(item))
                try:
                    value = operator(value, multiplier * offset)
                except (TypeError, ZeroDivisionError):
                    return None
                operator = None
        # Datetime formatting
        if mdict['strf_format']:
            value = strftime_or_none(value, mdict['strf_format'].replace('\\,', ','))

        # XXX: Workaround for https://github.com/yt-dlp/yt-dlp/issues/4485
        if sanitize and value == '':
            value = None
        return value

    na = params.get('outtmpl_na_placeholder', 'NA')

    def filename_sanitizer(key, value, restricted):
        return sanitize_filename(str(value), restricted=restricted, is_id=(
            bool(re.search(r'(^|[_.])id(\.|$)', key))
            if 'filename-sanitization' in params.get('compat_opts', [])
            else NO_DEFAULT))

    #if callable(sanitize):
    #    self.deprecation_warning('Passing a callable "sanitize" to YoutubeDL.prepare_outtmpl is deprecated')
    if not sanitize:
        pass
    elif (sys.platform != 'win32' and not params.get('restrictfilenames')
          and params.get('windowsfilenames') is False):
        def sanitize(key, value):
            return str(value).replace('/', '\u29F8').replace('\0', '')
    else:
        def sanitize(key, value):
            return filename_sanitizer(key, value, restricted=params.get('restrictfilenames'))

    def _dumpjson_default(obj):
        if isinstance(obj, (set, LazyList)):
            return list(obj)
        return repr(obj)

    class _ReplacementFormatter(string.Formatter):
        def get_field(self, field_name, args, kwargs):
            if field_name.isdigit():
                return args[0], -1
            raise ValueError('Unsupported field')

    replacement_formatter = _ReplacementFormatter()

    def create_key(outer_mobj):
        if not outer_mobj.group('has_key'):
            return outer_mobj.group(0)
        key = outer_mobj.group('key')
        mobj = re.match(INTERNAL_FORMAT_RE, key)
        value, replacement, default, last_field = None, None, na, ''
        while mobj:
            mobj = mobj.groupdict()
            default = mobj['default'] if mobj['default'] is not None else default
            value = get_value(mobj)
            last_field, replacement = mobj['fields'], mobj['replacement']
            if value is None and mobj['alternate']:
                mobj = re.match(INTERNAL_FORMAT_RE, mobj['remaining'][1:])
            else:
                break

        if None not in (value, replacement):
            try:
                value = replacement_formatter.format(replacement, value)
            except ValueError:
                value, default = None, na

        fmt = outer_mobj.group('format')
        if fmt == 's' and last_field in field_size_compat_map and isinstance(value, int):
            fmt = f'0{field_size_compat_map[last_field]:d}d'

        flags = outer_mobj.group('conversion') or ''
        str_fmt = f'{fmt[:-1]}s'
        if value is None:
            value, fmt = default, 's'
        elif fmt[-1] == 'l':  # list
            delim = '\n' if '#' in flags else ', '
            value, fmt = delim.join(map(str, variadic(value, allowed_types=(str, bytes)))), str_fmt
        elif fmt[-1] == 'j':  # json
            value, fmt = json.dumps(
                value, default=_dumpjson_default,
                indent=4 if '#' in flags else None, ensure_ascii='+' not in flags), str_fmt
        elif fmt[-1] == 'h':  # html
            value, fmt = escapeHTML(str(value)), str_fmt
        elif fmt[-1] == 'q':  # quoted
            value = map(str, variadic(value) if '#' in flags else [value])
            value, fmt = shell_quote(value, shell=True), str_fmt
        elif fmt[-1] == 'B':  # bytes
            value = f'%{str_fmt}'.encode() % str(value).encode()
            value, fmt = value.decode('utf-8', 'ignore'), 's'
        elif fmt[-1] == 'U':  # unicode normalized
            value, fmt = unicodedata.normalize(
                # "+" = compatibility equivalence, "#" = NFD
                'NF{}{}'.format('K' if '+' in flags else '', 'D' if '#' in flags else 'C'),
                value), str_fmt
        elif fmt[-1] == 'D':  # decimal suffix
            num_fmt, fmt = fmt[:-1].replace('#', ''), 's'
            value = format_decimal_suffix(value, f'%{num_fmt}f%s' if num_fmt else '%d%s',
                                          factor=1024 if '#' in flags else 1000)
        elif fmt[-1] == 'S':  # filename sanitization
            value, fmt = filename_sanitizer(last_field, value, restricted='#' in flags), str_fmt
        elif fmt[-1] == 'c':
            if value:
                value = str(value)[0]
            else:
                fmt = str_fmt
        elif fmt[-1] not in 'rsa':  # numeric
            value = float_or_none(value)
            if value is None:
                value, fmt = default, 's'

        if sanitize:
            # If value is an object, sanitize might convert it to a string
            # So we manually convert it before sanitizing
            if fmt[-1] == 'r':
                value, fmt = repr(value), str_fmt
            elif fmt[-1] == 'a':
                value, fmt = ascii(value), str_fmt
            if fmt[-1] in 'csra':
                value = sanitize(last_field, value)

        key = '{}\0{}'.format(key.replace('%', '%\0'), outer_mobj.group('format'))
        TMPL_DICT[key] = value
        return '{prefix}%({key}){fmt}'.format(key=key, fmt=fmt, prefix=outer_mobj.group('prefix'))

    return EXTERNAL_FORMAT_RE.sub(create_key, outtmpl), TMPL_DICT

def escape_outtmpl(outtmpl):
    """ Escape any remaining strings like %s, %abc% etc. """
    return re.sub(
        STR_FORMAT_RE_TMPL.format('', '(?![%(\0])'),
        lambda mobj: ('' if mobj.group('has_key') else '%') + mobj.group(0),
        outtmpl)

def evaluate_outtmpl(outtmpl, info_dict, *args, **kwargs):
    outtmpl, info_dict = prepare_outtmpl(outtmpl, info_dict, *args, **kwargs)
    return escape_outtmpl(outtmpl) % info_dict