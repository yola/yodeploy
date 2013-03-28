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

# Ignore the return status of these linters
set +e
pep8 yola > reports/pep8.report
pyflakes yola > reports/pyflakes.report
pylint yola > reports/pylint.report
exit 0
