python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,window-qt]"
python -m cleftune --browser