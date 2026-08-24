"""Asegura que los imports del launcher resuelvan al ejecutar pytest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
