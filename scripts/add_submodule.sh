#!/usr/bin/env bash
set -euo pipefail
if [ -d "AimIO" ]; then
  echo "AimIO directory already exists"
  exit 0
fi
git submodule add https://github.com/Numerics88/AimIO AimIO
git submodule update --init --recursive
echo "Added AimIO submodule. Run: pip install -e ." 
