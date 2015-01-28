#!/bin/bash
set -eu
cd "$(dirname "$0")/.."

rm -rf dist
mkdir dist
tar -czf dist/config-template-token.tar.gz build
