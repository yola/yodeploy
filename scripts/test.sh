#!/bin/bash

set -efx

cd "$(dirname "$0")/.."

# Setup our test environment
scripts/build.sh test_build

cp setup.py test_build/
cp -R bin test_build/

# Activate the venv
. virtualenv/bin/activate
cd test_build/

python -m pytest
