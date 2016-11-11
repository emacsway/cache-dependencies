import time
from collections import OrderedDict
import cProfile, pstats
from django.core.management.base import BaseCommand
from cache_tagging.django_cache_tagging import cache

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


class GetValidCase(object):

    def __init__(self, cache):
        self.cache = cache
        tags1 = ('tag1_1', 'tag1_2', 'tag1_3', 'tag1_4',)
        self.cache.set('name1', 'value1', tags1, 120)

    def cache_tagging_call(self):
        return self.cache.get('name1')

    def native_cache_call(self):
        return self.cache.cache.get('name1')


class GetManyValidCase(object):

    def __init__(self, cache):
        self.cache = cache
        tags1 = ('tag1_1', 'tag1_2', 'tag1_3', 'tag1_4',)
        self.cache.set('name1', 'value1', tags1, 120)
        tags2 = ('tag2_1', 'tag2_2', 'tag2_3', 'tag2_4',)
        self.cache.set('name2', 'value2', tags2, 120)

    def cache_tagging_call(self):
        return self.cache.get_many(('name1', 'name2'))

    def native_cache_call(self):
        return self.cache.cache.get_many(('name1', 'name2'))


class GetInvalidCase(object):

    def __init__(self, cache):
        self.cache = cache
        tags1 = ('tag1_1', 'tag1_2', 'tag1_3', 'tag1_4',)
        self.cache.set('name1', 'value1', tags1, 120)
        self.cache.invalidate_tags('tag1_1')

    def cache_tagging_call(self):
        return self.cache.get('name1')

    def native_cache_call(self):
        return self.cache.cache.get('name1')


class GetManyInvalidCase(object):

    def __init__(self, cache):
        self.cache = cache
        tags1 = ('tag1_1', 'tag1_2', 'tag1_3', 'tag1_4',)
        self.cache.set('name1', 'value1', tags1, 120)
        tags2 = ('tag2_1', 'tag2_2', 'tag2_3', 'tag2_4',)
        self.cache.set('name2', 'value2', tags2, 120)
        self.cache.invalidate_tags('tag1_1')

    def cache_tagging_call(self):
        return self.cache.get_many(('name1', 'name2'))

    def native_cache_call(self):
        return self.cache.cache.get_many(('name1', 'name2'))


class Command(BaseCommand):

    _cases = {
        'get_valid': GetValidCase(cache),
        'get_many_valid':  GetManyValidCase(cache),
        'get_invalid': GetInvalidCase(cache),
        'get_many_invalid':  GetManyInvalidCase(cache),
    }

    def add_arguments(self, parser):
        parser.add_argument('case', nargs='+', choices=tuple(self._cases.keys()))

    def handle(self, *args, **options):
        for case_key in options['case']:
            case = self._cases[case_key]
            case.cache_tagging_call()  # Just prepare
            case.native_cache_call()
            result = self._bench_complex(case.cache_tagging_call, case.native_cache_call)
            self.stdout.write("=" * 50, ending="\n")
            self.stdout.write("Cache-tagging result, sec.: {}".format(result[case.cache_tagging_call]), ending="\n")
            self.stdout.write("Native cache result, sec. : {}".format(result[case.native_cache_call]), ending="\n")
            overhead = (result[case.cache_tagging_call] * 100 / result[case.native_cache_call]) - 100
            self.stdout.write("Overhead, %               : {}".format(overhead), ending="\n")
            self.stdout.write("=" * 50, ending="\n")
            self._prof(case.cache_tagging_call)
            self.stdout.write("=" * 50, ending="\n\n\n")

    def _bench(self, callback):
        s = time.time()
        callback()
        return time.time() - s

    def _bench_complex(self, *args):
        r = OrderedDict()
        for a in args:
            r[a] = []
        for i in range(50):
            for a in args:
                r[a].append(self._bench(a))

        for a in args:
            r[a] = float(sum(r[a])) / len(r[a])

        return r

    def _prof(self, callback, *a, **kw):
        pr = cProfile.Profile()
        pr.enable()
        result = callback(*a, **kw)
        s = StringIO()
        sortby = 'tottime'
        sortby = 'cumulative'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats(30)
        self.stdout.write(s.getvalue())
        pr.disable()
        return result
