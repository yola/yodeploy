#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

rm -rf build
mkdir build
cp -r src build
cp -r deploy build
