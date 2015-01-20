#!/bin/bash
set -eu
cd "$(dirname "$0")/.."

rm -rf dist
mkdir dist
cp -Rf build dist/basic_app
cd dist && tar -czf basic_app.tar.gz basic_app
