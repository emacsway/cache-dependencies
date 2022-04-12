#!/usr/bin/env python
#
# Copyright (c) 2011-2013 Ivan Zakrevsky
# Licensed under the terms of the BSD License (see LICENSE.txt)
import os.path
from io import open
from setuptools import setup, find_packages

app_name = os.path.basename(os.path.dirname(os.path.abspath(__file__)))

setup(
    name='cache-dependencies',
    version='0.7.7.52',

    packages=find_packages(),
    include_package_data=True,

    author="Ivan Zakrevsky",
    author_email="ivzak@yandex.ru",
    description="Cache-dependencies (former Cache-tagging) allows you easily invalidate all cache records tagged with a given tag(s). Supports Django.",
    long_description=open(os.path.join(os.path.dirname(__file__), 'README.rst'), encoding='utf-8').read(),
    license="BSD License",
    keywords="django cache dependencies tagging",
    tests_require=[
        'Django>=1.3',
        'mock',
    ],
    test_suite='runtests.main',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    url="https://bitbucket.org/emacsway/{0}".format(app_name),
)
