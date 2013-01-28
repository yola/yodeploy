#!/bin/bash

set -efxu

cd "$(dirname "$0")/.."

# remove dist directory if exists
[ -d ./build ] && rm -Rf build
mkdir build

# copy source to dist
cp requirements.txt build
cp -R yola build
find build -name '*.pyc' -delete
