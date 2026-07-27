import os

# Must be set before any PySide6 import (this sandbox has no real display).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
