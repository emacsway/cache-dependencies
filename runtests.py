# -*- coding: utf-8 -*-
import warnings
import os
import sys

urlpatterns = []

TEMPLATE_DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:'
    }
}


INSTALLED_APPS = [
    'cache_tagging.django_cache_tagging',
]

TEMPLATE_DIRS = [
]

MIDDLEWARE_CLASSES = (
    'cache_tagging.django_cache_tagging.middleware.TransactionMiddleware',
)

ROOT_URLCONF = 'runtests'

def main():
    from django.conf import settings
    settings.configure(
        INSTALLED_APPS = INSTALLED_APPS,
        ROOT_URLCONF = ROOT_URLCONF,
        DATABASES = DATABASES,
        TEST_RUNNER = 'django.test.simple.DjangoTestSuiteRunner',
        TEMPLATE_DIRS = TEMPLATE_DIRS,
        TEMPLATE_DEBUG = TEMPLATE_DEBUG
    )
    
    from cache_tagging.django_cache_tagging import autodiscover
    autodiscover()

    # Run the test suite, including the extra validation tests.
    from django.test.utils import get_runner
    TestRunner = get_runner(settings)

    test_runner = TestRunner(verbosity=1, interactive=False, failfast=False)
    warnings.simplefilter("ignore")
    failures = test_runner.run_tests(['django_cache_tagging'])
    sys.exit(failures)


if __name__ == "__main__":
    main()
