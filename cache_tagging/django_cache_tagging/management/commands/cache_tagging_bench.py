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


class Bench(object):

    @staticmethod
    def _bench(callback):
        s = time.time()
        callback()
        return time.time() - s

    def __call__(self, *args):
        r = OrderedDict()
        for a in args:
            r[a] = []
        for i in range(50):
            for a in args:
                r[a].append(self._bench(a))

        for a in args:
            r[a] = float(sum(r[a])) / len(r[a])

        return r


class Profile(object):

    def __init__(self, stdout, sort_keys=('cumulative',), stats_restrictions=(30,)):
        self._prof = cProfile.Profile()
        self._stdout = stdout
        self._sort_keys = sort_keys
        self._stats_restrictions = stats_restrictions

    def __call__(self, callback, *a, **kw):
        self._prof.enable()
        result = callback(*a, **kw)
        s = StringIO()
        ps = pstats.Stats(self._prof, stream=s).sort_stats(*self._sort_keys)
        ps.print_stats(*self._stats_restrictions)
        self._stdout.write(s.getvalue())
        self._prof.disable()
        return result


class Command(BaseCommand):

    bench_factory = Bench
    profile_factory = Profile

    _cases = {
        'get_valid': GetValidCase(cache),
        'get_many_valid':  GetManyValidCase(cache),
        'get_invalid': GetInvalidCase(cache),
        'get_many_invalid':  GetManyInvalidCase(cache),
    }

    def add_arguments(self, parser):
        parser.add_argument(
            'case',
            nargs='+',
            choices=tuple(self._cases.keys())
        )
        parser.add_argument(
            '--sort-key',
            dest='sort_keys',
            nargs='+',
            choices=('tottime', 'cumulative',),
            default=('cumulative',),
            help="See https://docs.python.org/3/library/profile.html#pstats.Stats.sort_stats"
        )
        parser.add_argument(
            '--limit-lines',
            nargs='?',
            type=int,
            default=30,
            help="See https://docs.python.org/3/library/profile.html#pstats.Stats.print_stats"
        )

    def handle(self, *args, **options):
        bench = self.bench_factory()
        prof = self.profile_factory(
            self.stdout,
            sort_keys=options['sort_keys'],
            stats_restrictions=(options['limit_lines'],),
        )
        for case_key in options['case']:
            case = self._cases[case_key]
            case.cache_tagging_call()  # Just prepare
            case.native_cache_call()
            result = bench(case.cache_tagging_call, case.native_cache_call)
            self.stdout.write("=" * 50, ending="\n")
            self.stdout.write("Cache-tagging result, sec.: {}".format(result[case.cache_tagging_call]), ending="\n")
            self.stdout.write("Native cache result, sec. : {}".format(result[case.native_cache_call]), ending="\n")
            overhead = (result[case.cache_tagging_call] * 100 / result[case.native_cache_call]) - 100
            self.stdout.write("Overhead, %               : {}".format(overhead), ending="\n")
            self.stdout.write("=" * 50, ending="\n")
            prof(case.cache_tagging_call)
            self.stdout.write("=" * 50, ending="\n\n\n")
