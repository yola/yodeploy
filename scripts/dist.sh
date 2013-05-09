#!/bin/bash

set -efxu

cd "$(dirname "$0")/.."

# remove dist directory if exists
[ -d ./dist ] && rm -Rf dist
mkdir dist

# copy source to dist
cp -Rf deploy build/

# create distribution tarball
cp -Rf build dist/yodeploy

cd dist && tar -czf yodeploy.tar.gz yodeploy
