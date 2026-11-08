"""Verify the built wheel and sdist ship the client's PEP 561 marker and modules."""
from pathlib import Path
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "custom_components/solem_woobee/woobee_api"


def main() -> None:
    expected = {f"woobee_api/{path.name}" for path in CLIENT.glob("*.py")}
    expected.add("woobee_api/py.typed")
    wheels = list((ROOT / "dist").glob("*.whl"))
    sdists = list((ROOT / "dist").glob("*.tar.gz"))
    assert len(wheels) == len(sdists) == 1, "Build into a clean dist directory"
    with zipfile.ZipFile(wheels[0]) as wheel:
        assert expected <= set(wheel.namelist()), "Wheel omits typed client files"
        assert wheel.read("woobee_api/py.typed") == b"", "Expected a fully typed package"
    with tarfile.open(sdists[0]) as sdist:
        names = {name.split("/", 1)[1] for name in sdist.getnames() if "/" in name}
        assert {f"custom_components/solem_woobee/{name}" for name in expected} <= names
    print("Wheel and sdist include every client module and py.typed")


if __name__ == "__main__":
    main()
