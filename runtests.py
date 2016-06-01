# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import os
import sys

urlpatterns = []


def main():
    import django
    from django.conf import settings
    settings.configure(
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:'
            }
        },
        CACHE_TAGGING = {
            'default': {
                'ISOLATION_LEVEL': 'REPEATABLE READS',
                'DELAY': 5,
            }
        },
        INSTALLED_APPS = [
            'django.contrib.sessions',
            'django.contrib.messages',
            'cache_tagging.django_cache_tagging',
        ],
        MIDDLEWARE_CLASSES = [
            'django.middleware.common.CommonMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
            'cache_tagging.django_cache_tagging.middleware.TransactionMiddleware',
        ],
        TEST_RUNNER = 'django.test.runner.DiscoverRunner',
        TEMPLATE_DIRS = [],
        DEBUG = True,
        TEMPLATE_DEBUG = True,
        ROOT_URLCONF = 'runtests',
    )

    try:
        django.setup()
    except AttributeError:
        pass

    from cache_tagging.django_cache_tagging import autodiscover
    autodiscover()

    # Run the test suite, including the extra validation tests.
    from django.test.utils import get_runner
    TestRunner = get_runner(settings)

    test_runner = TestRunner(verbosity=1, interactive=False, failfast=False)
    failures = test_runner.run_tests([
        'cache_tagging.tests.test_helpers',
        'cache_tagging.tests.test_relations',
        'cache_tagging.tests.test_locks',
        'cache_tagging.tests.test_transaction',
        'cache_tagging.tests.test_tagging',
        'cache_tagging.django_cache_tagging.tests',
    ])
    sys.exit(failures)


if __name__ == "__main__":
    main()
