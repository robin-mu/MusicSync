import gettext as module_gettext
import re
import unicodedata

def N_(message: str) -> str:
    """No-op marker for translatable strings"""
    return message

_null_translations = module_gettext.NullTranslations()
_translation = {
    'main': _null_translations,
    'attributes': _null_translations,
    'constants': _null_translations,
    'countries': _null_translations,
}

def gettext(message: str) -> str:
    """Translate the messsage using the current translator."""
    # Calling gettext("") by default returns the header of the PO file for the
    # current locale. This is unexpected. Return an empty string instead.
    if message == "":
        return message
    return _translation['main'].gettext(message)

def gettext_countries(message: str) -> str:
    return _translation['countries'].gettext(message)


def wildcards_to_regex_pattern(pattern):
    """Converts a pattern with shell like wildcards into a regular expression string.

    The following syntax is supported:
    - `*`: Matches an arbitrary number of characters or none, e.g. `fo*` matches "foo" or "foot".
    - `?`: Matches exactly one character, e.g. `fo?` matches "foo" or "for".
    - `[...]`
    - `?`, `*` and `\\` can be escaped with a backslash \\ to match the literal character, e.g. `fo\\?` matches "fo?".

    Args:
        pattern: The pattern as a string

    Returns: A string with a valid regular expression.
    """
    regex = []
    group = None
    escape = False
    for c in pattern:
        if group is not None:
            if escape:
                if c in {'\\', '[', ']'}:
                    c = '\\' + c
                else:
                    group.append('\\\\')
                escape = False
            if c == ']':
                group.append(c)
                part = ''.join(group)
                group = None
            elif c == '\\':
                escape = True
                continue
            else:
                group.append(c)
                continue
        elif escape:
            if c in {'*', '?', '\\', '[', ']'}:
                part = '\\' + c
            else:
                part = re.escape('\\' + c)
            escape = False
        elif c == '\\':
            escape = True
            continue
        elif c == '[':
            group = ['[']
            continue
        elif c == '*':
            part = '.*'
        elif c == '?':
            part = '.'
        else:
            part = re.escape(c)
        regex.append(part)

    # There might be an unclosed character group. Interpret the starting
    # bracket of the group as a literal bracket and re-evaluate the rest.
    if group is not None:
        regex.append('\\[')
        regex.append(wildcards_to_regex_pattern(''.join(group[1:])))
    return ''.join(regex)

def pattern_as_regex(pattern, allow_wildcards=False, flags=0):
    """Parses a string and interprets it as a matching pattern.

    - If pattern is of the form /pattern/flags it is interpreted as a regular expression (e.g. `/foo.*/`).
      The flags are optional and in addition to the flags passed in the `flags` function parameter. Supported
      flags in the expression are "i" (ignore case) and "m" (multiline)
    - Otherwise if `allow_wildcards` is True, it is interpreted as a pattern that allows wildcard matching (see below)
    - If `allow_wildcards` is False a regex matching the literal string is returned

    Wildcard matching currently supports these characters:
    - `*`: Matches an arbitrary number of characters or none, e.g. `fo*` matches "foo" or "foot".
    - `?`: Matches exactly one character, e.g. `fo?` matches "foo" or "for".
    - `[...]`: Matches any character in the set, e.g. `[fo?]` matches all of "f", "o" and "?".
    - `?`, `*`, `[`, `]` and `\\` can be escaped with a backslash \\ to match the literal
      character, e.g. `fo\\?` matches "fo?".

    Args:
        pattern: The pattern as a string
        allow_wildcards: If true and if the the pattern is not interpreted as a regex wildard matching is allowed.
        flags: Additional regex flags to set (e.g. `re.I`)

    Returns: An re.Pattern instance

    Raises: `re.error` if the regular expression could not be parsed
    """
    plain_pattern = pattern.rstrip('im')
    if len(plain_pattern) > 2 and plain_pattern[0] == '/' and plain_pattern[-1] == '/':
        extra_flags = pattern[len(plain_pattern) :]
        if 'i' in extra_flags:
            flags |= re.IGNORECASE
        if 'm' in extra_flags:
            flags |= re.MULTILINE
        regex = plain_pattern[1:-1]
    elif allow_wildcards:
        regex = '^' + wildcards_to_regex_pattern(pattern) + '$'
    else:
        regex = re.escape(pattern)
    return re.compile(regex, flags)


def iswbound(char):
    # GPL 2.0 licensed code by Javier Kohen, Sambhav Kothari
    # from https://github.com/metabrainz/picard-plugins/blob/2.0/plugins/titlecase/titlecase.py
    """Checks whether the given character is a word boundary"""
    category = unicodedata.category(char)
    return 'Zs' == category or 'Sk' == category or 'P' == category[0]

def titlecase(text):
    # GPL 2.0 licensed code by Javier Kohen, Sambhav Kothari
    # from https://github.com/metabrainz/picard-plugins/blob/2.0/plugins/titlecase/titlecase.py
    """Converts text to title case following word boundary rules.

    Capitalizes the first character of each word in the input text, where words
    are determined by Unicode word boundaries. Preserves existing capitalization
    after the first character of each word.

    Args:
        text (str): The input text to convert to title case.

    Returns:
        str: The text converted to title case. Returns empty string if input is empty.

    Examples:
        >>> titlecase("hello world")
        'Hello World'
        >>> titlecase("children's music")
        'Children's Music'
    """
    if not text:
        return text
    capitalized = text[0].capitalize()
    capital = False
    for i in range(1, len(text)):
        t = text[i]
        if t in "’'" and text[i - 1].isalpha():
            capital = False
        elif iswbound(t):
            capital = True
        elif capital and t.isalpha():
            capital = False
            t = t.capitalize()
        else:
            capital = False
        capitalized += t
    return capitalized


def iter_unique(seq):
    """Creates an iterator only returning unique values from seq"""
    seen = set()
    return (x for x in seq if x not in seen and not seen.add(x))

def uniqify(seq):
    """Uniqify a list, preserving order"""
    return list(iter_unique(seq))