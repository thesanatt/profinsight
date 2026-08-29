"""Keep test imports offline: api.py fetches the data release at import when
data/ is empty, which a fresh CI checkout always is."""
import os

os.environ.setdefault("PROFINSIGHT_SKIP_FETCH", "1")
