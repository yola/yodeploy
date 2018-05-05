#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

rm -rf dist
mkdir dist
tar -czf dist/uwsgi-app.tar.gz build
