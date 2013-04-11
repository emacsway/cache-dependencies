from __future__ import absolute_import, unicode_literals
from uuid import uuid4
from django.http import HttpResponse

from ..decorators import cache_page


@cache_page(3600, tags=lambda request: ('tests.firsttestmodel', ))
def test_decorator(request):
    now = uuid4()
    html = "<html><body>It is now {0}.</body></html>".format(now)
    return HttpResponse(html)
