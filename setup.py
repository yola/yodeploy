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
    name='yodeploy',
    description='Helpers for Deploy hooks',
    author='Stefano Rivera',
    author_email='stefano.rivera@yola.com',
    url='https://github.com/yola/yodeploy',
    version='0.3.3',
    packages=find_packages(),
    scripts=['bin/test-templates.py'],
    test_suite='nose.collector',
    install_requires=parse_requirements(),
)
