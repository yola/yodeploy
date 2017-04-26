"""
Tools for ensuring a processes's stdout buffer is able to output unicode.

In certain environments, attempting to output unicode data via stdout will
fail (either by raising an exception or outputting corrupt data). To accomodate
processes that require the ability to output such data,
`ensure_unicode_compatible()` will detect incompatible environments, and,
if necessary, replace stdout with a buffer that is capable of outputting
unicode data.
"""
import codecs
import sys


def ensure_unicode_compatible():
    """Ensure sys.stdout is unicode compatible."""
    encoding = getattr(sys.stdout, 'encoding', None)

    if encoding in (None, 'ANSI_X3.4-1968', 'ascii', 'US-ASCII'):
        UTF8Writer = codecs.getwriter('utf8')
        sys.stdout = UTF8Writer(getattr(sys.stdout, 'buffer', sys.stdout))
