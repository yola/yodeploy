#!/bin/bash
set -eu
cd "$(dirname "$0")/.."

rm -Rf build
mkdir build
cp hello-world.txt build
