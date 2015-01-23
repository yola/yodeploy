#!/bin/bash
set -eu
cd "$(dirname "$0")/.."

rm -rf dist
mkdir dist
tar -czf dist/apache-missingconfs.tar.gz build
