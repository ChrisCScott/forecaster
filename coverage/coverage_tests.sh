#!/bin/bash
# This script must be in `forecaster/coverage` to work
cd "$(dirname "$0")"
cd ..
pytest --cov=. ./tests/ --cov-config=coverage/.coveragerc --profile --profile-svg
# Move profiling data files to `coverage` dir (there's no option for this)
rsync -a --delete prof/ coverage/prof
rm -R prof