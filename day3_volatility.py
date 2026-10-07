"""Archived simulated-data example; use research.py for historical research."""
from pathlib import Path
import runpy
print("SIMULATED DATA ONLY. Historical research: python research.py all")
runpy.run_path(str(Path(__file__).resolve().parent / "original" / Path(__file__).name), run_name="__main__")
