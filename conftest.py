import sys
from pathlib import Path

# Allow ``from tools.xxx import ...`` in tests.
sys.path.insert(0, str(Path(__file__).resolve().parent))
