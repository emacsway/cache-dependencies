# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import re
import base64

try:
    import cPickle as pickle
except ImportError:
    import pickle

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
        self._start = '<{0} secret="{1}" data="{{0}}">'.format(
            self.tag_name, self.secret
        )
        self._end = '</{0}>'.format(self.tag_name)
        # Usind lookahead assertion in case nested nocaches.
        self.nocache_pattern = r'{0}(.+?)(?!<{1}){2}'.format(
            self._start.format('([^"]+)'),
            self.tag_name,
            self._end
        )
        self.nocache_re = re.compile(self.nocache_pattern, re.U|re.S)

    def start(self, **data):
        return self._start.format(self.pickle(data))

    def end(self):
        return self._end

    def pickle(self, data):
        return base64.standard_b64encode(
            pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        ).decode('ascii')

    def unpickle(self, value):
        return pickle.loads(base64.standard_b64decode(value.encode('ascii')))

    def handle(self, tpl, **data):
        """eval nocache"""

        def repl(match):
            lines = match.group(2).split('\n')
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

            _locals = {}
            _locals.update(data)
            _locals.update(self.unpickle(match.group(1)))

            code = compile("\n".join(lines_stripped), '<string>', 'exec')
            eval(code, _globals, _locals)
            result = stdout.getvalue()
            stdout.close()
            # After eval() nocache.start() will be converted to "<nocache:py ..."
            # and nocache.end() - to "</nocache>"
            # So, check again.
            if self._end in result:
                result = self.handle(result, **data)
            return result

        result = self.nocache_re.sub(repl, tpl)
        return result
