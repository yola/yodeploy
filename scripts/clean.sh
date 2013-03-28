#!/bin/bash

set -exu

cd "$(dirname "$0")/.."

rm -rf build dist reports
rm -rf *.egg-info
