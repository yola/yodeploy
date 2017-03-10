#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."

rm -rf dist
mkdir dist
tar -czf dist/requirements-downgrade.tar.gz build
