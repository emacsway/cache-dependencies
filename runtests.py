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
                'ISOLATION_LEVEL': 'REPEATABLE READ',
                'DELAY': 5,
            }
        },
        INSTALLED_APPS = [
            'django.contrib.sessions',
            'django.contrib.messages',
            'django_cache_dependencies',
        ],
        MIDDLEWARE_CLASSES = [
            'django.middleware.common.CommonMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
            'django_cache_dependencies.middleware.TransactionMiddleware',
        ],
        MIDDLEWARE = [
            'django.middleware.common.CommonMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
            'django_cache_dependencies.middleware.TransactionMiddleware',
        ],
        TEST_RUNNER = 'django.test.runner.DiscoverRunner',
        TEMPLATE_DIRS = [],
        TEMPLATES = [
            {
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [],
                'APP_DIRS': True,
                'OPTIONS': {
                    'context_processors': [],
                },
            },
        ],
        DEBUG = True,
        TEMPLATE_DEBUG = True,
        ROOT_URLCONF = 'runtests',
    )

    try:
        django.setup()
    except AttributeError:
        pass

    from django_cache_dependencies import autodiscover
    autodiscover()

    # Run the test suite, including the extra validation tests.
    from django.test.utils import get_runner
    TestRunner = get_runner(settings)

    test_runner = TestRunner(verbosity=1, interactive=False, failfast=False)
    failures = test_runner.run_tests([
        'cache_dependencies.tests.test_cache',
        'cache_dependencies.tests.test_defer',
        'cache_dependencies.tests.test_dependencies',
        'cache_dependencies.tests.test_helpers',
        'cache_dependencies.tests.test_relations',
        'cache_dependencies.tests.test_locks',
        'cache_dependencies.tests.test_transaction',
        'cache_dependencies.tests.test_tagging',
        'django_cache_dependencies.tests',
    ])
    sys.exit(failures)


if __name__ == "__main__":
    main()
