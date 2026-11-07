"""Enforce >95% line/branch coverage per HA adapter module (not the BLE library)."""
import json
from pathlib import Path

report = json.loads(Path("coverage.json").read_text())
prefix = "custom_components/solem_woobee/"
modules = {
    name: data["summary"]["percent_covered"]
    for name, data in report["files"].items()
    if name.startswith(prefix) and not name.startswith(prefix + "woobee_api/")
}
if not modules:
    raise SystemExit("No Home Assistant adapter coverage found")
failures = [f"{name}: {coverage:.2f}%" for name, coverage in modules.items() if coverage <= 95]
if failures:
    raise SystemExit("Expected >95% per adapter module:\n" + "\n".join(failures))
print(f"Coverage >95% in each of {len(modules)} Home Assistant adapter modules")
