"""The gate must reject missing, unexecuted and insufficiently measured modules."""
import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('coverage_gate', Path(__file__).parents[1] / 'scripts/check_ha_coverage.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class CoverageGateTests(unittest.TestCase):
    def test_inventory_and_separate_line_branch_thresholds(self):
        with TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory).relative_to(Path.cwd())
            module = root / 'unimported.py'
            module.touch()
            summary = dict(num_statements=100, covered_lines=100, num_branches=100, covered_branches=100)
            report = {'meta': {'branch_coverage': True}, 'files': {str(module): {'summary': summary}}}
            with patch.object(GATE, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                GATE.check(report)
                for changes in ({'covered_lines': 95}, {'covered_branches': 95},
                                {'covered_lines': 0}, {'covered_branches': 0}):
                    report['files'][str(module)]['summary'] = {**summary, **changes}
                    with self.subTest(changes=changes), self.assertRaises(ValueError):
                        GATE.check(report)
                report['files'].clear()
                with self.assertRaisesRegex(ValueError, 'absent'):
                    GATE.check(report)
                report['meta']['branch_coverage'] = False
                with self.assertRaisesRegex(ValueError, 'Branch coverage'):
                    GATE.check(report)
                module.unlink()
                report['meta']['branch_coverage'] = True
                with self.assertRaisesRegex(ValueError, 'No shipped modules'):
                    GATE.check(report)

    def test_config_flow_requires_full_coverage_including_handler(self):
        with TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory).relative_to(Path.cwd())
            (root / 'config_flow.py').touch()
            handler = root / 'config_flow_handler'
            handler.mkdir()
            (handler / '__init__.py').touch()
            summary = dict(num_statements=100, covered_lines=100, num_branches=100, covered_branches=100)
            for path in root.rglob('*.py'):
                files = {str(p): {'summary': dict(summary)} for p in root.rglob('*.py')}
                files[str(path)]['summary']['covered_lines'] = 99
                report = {'meta': {'branch_coverage': True}, 'files': files}
                with patch.object(GATE, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                    with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'config flow requires 100%'):
                        GATE.check(report)
