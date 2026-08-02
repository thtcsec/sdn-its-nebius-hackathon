#!/usr/bin/env bash
set +e
cd /mnt/d/tu_projects/sdn-its-resilience-ai
pkill -f 'pip install' 2>/dev/null
rm -rf .venv-lab
python3.12 -m venv .venv-lab
source .venv-lab/bin/activate
pip install -q 'setuptools==57.5.0' wheel
pip install -q 'os-ken==2.8.1'
python -c "from os_ken.base import app_manager; print('os_ken_ok')"
which mn
mn -h 2>&1 | head -3
free -h | head -2
echo DONE
