#!/bin/bash

set -efx

cd "$(dirname "$0")/.."

# Setup our test environment
scripts/build.sh test_build

cp setup.py test_build/
cp -R bin test_build/

mkdir -p test_build/reports

# Activate the venv
. virtualenv/bin/activate
cd test_build/

./setup.py nosetests --with-xunit \
                     --with-specplugin \
                     --xunit-file=reports/xunit.xml \
                     --cover-html \
                     --cover-html-dir=reports \
                     --cover-package=yodeploy \
                     --with-xcoverage \
                     --xcoverage-file=reports/coverage.xml

# Ignore the return status of these linters
set +e
flake8 --output-file reports/flake8.report yodeploy
set -e
