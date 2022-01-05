#!/bin/bash
# This script must be in `forecaster/coverage` to work
cd "$(dirname "$0")"  # Start in script location
cd ..  # Move to containing folder (i.e. the forecaster project root)
# Output coverage reports to: terminal, coverage/cov_html, and coverage/cov.xml
pytest --cov=. ./tests/ --cov-config=coverage/.coveragerc --profile --profile-svg --cov-report html:coverage/cov_html --cov-report xml:coverage/cov.xml --cov-report term
# Move profiling data files to `coverage` dir (there's no option for this)
rsync -a --delete prof/ coverage/prof
rm -R prof