# yield_agent/__init__.py
import sys
import os

# Add the package directory to sys.path to allow absolute imports without package prefix
package_dir = os.path.dirname(os.path.abspath(__file__))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

from . import core
