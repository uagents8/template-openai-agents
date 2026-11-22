import os
import sys
from pathlib import Path

# The smoke tests cover the offline, no-key mode: no key, no network.
os.environ.pop("OPENAI_API_KEY", None)

# Let the tests import main.py from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
