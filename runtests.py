# -*- coding: utf-8 -*-
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
        CACHE_TAGGING_ = {
            'default': {
                'NONREPEATABLE_READS': True,
                'DELAY': 5,
            }
        },
        INSTALLED_APPS = [
            'cache_tagging.django_cache_tagging',
        ],
        MIDDLEWARE_CLASSES = [
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
    failures = test_runner.run_tests(['cache_tagging.django_cache_tagging.tests'])
    sys.exit(failures)


if __name__ == "__main__":
    main()
