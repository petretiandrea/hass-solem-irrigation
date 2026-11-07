"""Validate the HACS source tree without importing Home Assistant or BLE code."""
import ast
import json
import os
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "solem_woobee"


def main():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert manifest["domain"] == COMPONENT.name
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]), "Expected SemVer"
    tag = os.environ.get("GITHUB_REF", "")
    if tag.startswith("refs/tags/"):
        assert tag == f"refs/tags/v{manifest["version"]}", "Tag must match manifest version"
    assert hacs["homeassistant"] == "2026.8.0"
    assert (ROOT / ".python-version").read_text().strip() == "3.14"
    assert manifest["requirements"] == [], "Client must remain embedded"
    assert not hacs.get("content_in_root", False)
    assert not hacs.get("zip_release", False), "HACS uses the tagged source tree"
    for name in ("__init__.py", "config_flow.py", "strings.json", "translations/en.json", "translations/it.json"):
        assert (COMPONENT / name).is_file(), name
    for name in ("strings.json", "translations/en.json", "translations/it.json", "icons.json"):
        json.loads((COMPONENT / name).read_text())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "version" in project["project"]["dynamic"]
    assert "version" not in project["project"]
    assert project["tool"]["hatch"]["version"]["path"] == "custom_components/solem_woobee/manifest.json"
    client = COMPONENT / "woobee_api"
    assert (client / "__init__.py").is_file()
    for path in client.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
            assert not any(name.split(".")[0] in {"homeassistant", "custom_components"} for name in imports), path
    workflows = list((ROOT / ".github/workflows").glob("*.yml"))
    for path in workflows:
        assert "pypa/gh-action-pypi-publish" not in path.read_text(), path
    print(f"HACS source layout and embedded client validated; version {manifest['version']}")


if __name__ == "__main__":
    main()
