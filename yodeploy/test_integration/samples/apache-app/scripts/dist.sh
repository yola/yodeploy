#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

rm -rf dist
mkdir dist
tar -czf dist/apache-app.tar.gz build
