import importlib.util
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = BASE_DIR / "pages" / "1_specific_entry_point_analysis.py"


def load_sepa_module():
    spec = importlib.util.spec_from_file_location("sepa_page", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sepa_page"] = module
    spec.loader.exec_module(module)
    return module


class TestSEPAPage(unittest.TestCase):
    """Basic tests for the SEPA page (symbol selection only)."""

    def test_sepa_module_loads(self):
        module = load_sepa_module()
        self.assertTrue(hasattr(module, "_cached_symbol_list"))
        self.assertTrue(callable(module._cached_symbol_list))


if __name__ == "__main__":
    unittest.main()
