#!/bin/bash

set -efxu

cd "$(dirname "$0")/.."

rm -rf reports
mkdir reports

virtualenv/bin/python setup.py nosetests --with-xunit \
                                         --xunit-file=reports/TEST-nose.xml \
                                         --cover-html \
                                         --cover-html-dir=reports \
                                         --cover-package=yola.deploy \
                                         --with-xcoverage \
                                         --xcoverage-file=reports/coverage.xml
