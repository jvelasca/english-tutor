"""Asegura que los imports del backend resuelvan al ejecutar pytest desde cualquier
cwd."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
