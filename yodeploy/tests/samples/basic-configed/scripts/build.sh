#!/bin/bash
set -eu
cd "$(dirname "$0")/.."

rm -Rf build
mkdir build
cp -R deploy build
touch build/i-should-be-configured.txt
