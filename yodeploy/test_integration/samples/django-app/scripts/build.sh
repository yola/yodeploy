#!/bin/bash
set -eu
cd "$(dirname "$0")/.."

rm -Rf build
mkdir build
cp -R deploy build
cp -R app build
