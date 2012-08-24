#!/usr/bin/env python

from setuptools import setup, find_packages


def parse_requirements():
    requirements = []
    with open('requirements.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#'):
                continue
            requirements.append(line)
    return requirements


setup(
    name='yola.deploy',
    description='Helpers for Deploy hooks',
    author='Stefano Rivera',
    author_email='stefanor@yola.com',
    url='https://github.com/yola/yola.deploy',
    version="0.2.1",
    namespace_packages=['yola'],
    packages=find_packages(),
    scripts=['bin/test-templates.py'],
    test_suite='nose.collector',
    install_requires=parse_requirements(),
)
