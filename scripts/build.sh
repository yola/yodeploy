#!/bin/bash

set -efxu

cd "$(dirname "$0")/.."

# Allow overriding default of "build" for the directory name.
dirname=${1:-build}

# remove dist directory if exists
rm -Rf $dirname
mkdir $dirname

# copy source to dist
cp requirements.txt $dirname
cp -R yodeploy $dirname
find $dirname -name '*.pyc' -delete
