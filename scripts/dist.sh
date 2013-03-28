#!/bin/bash

set -efxu

cd "$(dirname "$0")/.."

# remove dist directory if exists
[ -d ./dist ] && rm -Rf dist
mkdir dist

# copy source to dist
cp -Rf deploy build/

# create distribution tarball
cp -Rf build dist/yola.deploy

cd dist && tar -czf yola.deploy.tar.gz yola.deploy
