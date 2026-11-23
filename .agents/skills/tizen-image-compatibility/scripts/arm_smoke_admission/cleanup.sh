#!/bin/sh
set -eu
exec /usr/bin/python3 -B "$(dirname -- "$0")/manage.py" cleanup "$@"
