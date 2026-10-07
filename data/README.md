# Data access

Raw Yahoo Finance data are not redistributed in this public repository. Run `python research.py download` from the project root to obtain adjusted closes and an integrity manifest, then `python research.py run` to reproduce the research.

`reference_manifest.json` records the eight-symbol snapshot used in the published October 2026 results. A fresh download may differ because of vendor revisions; it will generate its own `manifest.json`. The downloader never substitutes simulated data for a failed request.
