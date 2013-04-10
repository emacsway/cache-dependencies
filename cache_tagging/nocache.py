# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import re

try:
    from io import StringIO
except ImportError:  # Python 2.* compatible
    from StringIO import StringIO

try:
    str = unicode  # Python 2.* compatible
    string_types = (basestring,)
    integer_types = (int, long)
except NameError:
    string_types = (str,)
    integer_types = (int,)


class NoCache(object):
    """No cache class"""

    def __init__(self, secret, tag_name='nocache:py'):
        """constructor"""
        self.secret = secret
        self.tag_name = tag_name
        # nocache.nocache can be used for nested cache handling.
        # Similar like Django {% openblock %} for "{%".
        self.nocache = '<{0} secret="{1}">'.format(self.tag_name, self.secret)
        self.endnocache = '<{0}>'.format(self.tag_name)
        self.nocache_pattern = r'{0}(.+?){1}'.format(
            self.nocache, self.endnocache
        )
        self.nocache_re = re.compile(self.nocache_pattern, re.U|re.S)

    def handle(self, tpl, data):
        """eval nocache"""

        def repl(match):
            lines = match.group(1).split('\n')
            lines = [l.rstrip() for l in lines]
            lines_stripped = []
            start = None
            result = ''
            for l in lines:
                if not l:
                    continue
                if start is None:
                    start = len(l) - len(l.lstrip())
                lines_stripped.append(l[start:])
            lines_stripped.append('')
            stdout = StringIO()

            def echo(*args):
                for arg in args:
                    stdout.write(str(arg))

            _globals = {}
            _globals.update(globals())
            _globals['echo'] = echo
            code = compile("\n".join(lines_stripped), '<string>', 'exec')
            eval(code, _globals, data)
            result = stdout.getvalue()
            stdout.close()
            return result

        return self.nocache_re.sub(repl, tpl)
