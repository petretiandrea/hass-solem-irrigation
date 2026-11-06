import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "inspect_woobee", Path(__file__).parents[1] / "scripts" / "inspect_woobee.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InspectScriptTests(unittest.TestCase):
    def test_single_device_needs_no_prompt(self):
        device = object()

        self.assertIs(device, MODULE.select_device([device]))
