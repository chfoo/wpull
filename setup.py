#!/usr/bin/env python

from setuptools import setup

from distutils.version import StrictVersion
import os.path
import re
import os
import sys
import platform


def get_version():
    path = os.path.join('wpull', 'version.py')

    with open(path, 'r') as version_file:
        content = version_file.read()
        return re.search(r"__version__ = u?'(.+)'", content).group(1)


version = get_version()

StrictVersion(version)


PROJECT_PACKAGES = [
    'wpull',
    'wpull.application',
    'wpull.application.plugins',
    'wpull.application.tasks',
    'wpull.backport',
    'wpull.database',
    'wpull.document',
    'wpull.document.htmlparse',
    'wpull.driver',
    'wpull.network',
    'wpull.pipeline',
    'wpull.processor',
    'wpull.processor.coprocessor',
    'wpull.protocol.abstract',
    'wpull.protocol.ftp',
    'wpull.protocol.ftp.ls',
    'wpull.protocol.http',
    'wpull.proxy',
    'wpull.scraper',
    'wpull.testing',
    'wpull.testing.integration',
    'wpull.thirdparty',
    'wpull.warc',
]
PROJECT_PACKAGE_DIR = {}


setup_kwargs = dict(
    name='wpull',
    version=version,
    description='Wget-compatible web downloader and crawler.',
    author='Christopher Foo',
    author_email='chris.foo@gmail.com',
    url='https://github.com/chfoo/wpull',
    package_data={'': [
        'cert/ca-bundle.pem',
        'testing/integration/sample_user_scripts/*.py',
        'testing/*/*.css',
        'testing/*/*.htm',
        'testing/*/*.html',
        'testing/*/*.txt',
        'testing/*/*.lua',
        'testing/*/*.rst',
        'testing/*/*.js',
        'testing/*/*.png',
        'testing/*/*.xml',
        'testing/*.pem',
        'driver/*.js',
        'proxy/proxy.crt',
        'proxy/proxy.key',
    ]},
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: File Transfer Protocol (FTP)',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: System :: Archiving',
    ],
    packages=PROJECT_PACKAGES,
    package_dir=PROJECT_PACKAGE_DIR,
    entry_points={
        'console_scripts': [
            'wpull=wpull.application.main:main',
            'wpull3=wpull.application.main:main',
        ],
    },
    extras_require={
        'resmon': ['psutil>=2.0,<=4.2'],
        },
    setup_requires=['nose>=1.0'],
    # XXX: for some odd reason this specific coverage version is required
    tests_require=['coverage==4.0.3', 'python-coveralls'],
    python_requires='>=3.4,<3.7',
)


setup_kwargs['install_requires'] = [
    'chardet>=2.0.1',
    'dnspython3==1.12',
    'html5lib>=0.999,<=0.9999999',
    'lxml>=3.1.0,<=3.5',
    'namedlist>=1.3',
    'sqlalchemy>=0.9',
    'tornado>=3.2.2,<4.5.3',
    'yapsy>=1.11.223',
]

if sys.version_info < (3, 5):
    setup_kwargs['install_requires'].append('typing>=3.5,<=3.5.1')


if __name__ == '__main__':
    # this check is for old versions of pip/setuptools
    if sys.version_info[0] < 3:
        raise Exception('Sorry, Python 2 is not supported.')

    setup(**setup_kwargs)
