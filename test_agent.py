import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import yield_app

print("App loaded.")
print("Available methods on App:", [m for m in dir(yield_app) if not m.startswith("_")])
