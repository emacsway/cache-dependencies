from uuid import uuid4
from django.http import HttpResponse

from cache_tags.decorators import cache_page


@cache_page(3600, tags=lambda request: ('FirstTestModel', ))
def test_decorator(request):
    now = uuid4()
    html = "<html><body>It is now {0}.</body></html>".format(now)
    return HttpResponse(html)
