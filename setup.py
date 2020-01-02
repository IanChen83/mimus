"""
setup.py for the project
"""

import re
from pkg_resources import parse_version
from setuptools import setup, find_packages


import mimus as package


# Verify versions between package version and CHANGELOG.md
def _verify_version():
    package_version = parse_version(package.__version__)

    with open('CHANGELOG.md') as f:
        for line in f:
            result = re.search(r'(?<=### Version ).+', line)
            if result is not None:
                changelog_version = parse_version(result.group())
                break
        else:
            raise ValueError("Failed to find version in CHANGELOG.md")


    if (package_version != changelog_version and
            package_version.base_version != changelog_version.base_version):
        raise ValueError(
            "Mismatched version between package version {0} and CHANGELOG.md {1}".format(
                package_version, changelog_version,
            ))


_verify_version()


setup(
    name=package.__title__,
    version=package.__version__,
    packages=find_packages(),

    description=package.__summary__,
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',

    author=package.__author__,
    author_email=package.__email__,

    url=package.__url__,
    # Additional URLs
    # project_urls={
    #     'Documentation': package.__url__,
    # }

    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Software Development :: Testing :: Mocking',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    license='License :: OSI Approved :: MIT License',
)
