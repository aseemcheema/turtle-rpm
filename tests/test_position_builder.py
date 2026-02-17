import importlib.util
import sys
import types
import unittest
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = BASE_DIR / "pages" / "1_position_builder.py"


def load_position_builder_module():
    spec = importlib.util.spec_from_file_location("position_builder", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["position_builder"] = module
    spec.loader.exec_module(module)
    return module


class TestLoadPriceData(unittest.TestCase):
    def setUp(self):
        self.module = load_position_builder_module()
        if hasattr(self.module, "st") and hasattr(self.module.st, "cache_data"):
            self.module.st.cache_data.clear()

    def test_load_price_data_formats_dates_from_index(self):
        self.module.yf = types.SimpleNamespace(
            download=lambda *args, **kwargs: pd.DataFrame(
                {
                    "Open": [1, 2],
                    "High": [1.5, 2.5],
                    "Low": [0.5, 1.5],
                    "Close": [1.2, 2.2],
                },
                index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
            )
        )

        price_data = self.module.load_price_data("TEST_INDEX", "1d")

        self.assertEqual(price_data[0]["time"], "2024-01-02")
        self.assertEqual(price_data[1]["time"], "2024-01-03")

    def test_load_price_data_handles_nonstandard_datetime_column(self):
        self.module.yf = types.SimpleNamespace(
            download=lambda *args, **kwargs: pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(["2024-02-01", "2024-02-02"]),
                    "Open": [10, 11],
                    "High": [12, 13],
                    "Low": [9, 10],
                    "Close": [11, 12],
                }
            )
        )

        price_data = self.module.load_price_data("TEST_COLUMN", "1d")

        self.assertEqual(price_data[0]["time"], "2024-02-01")
        self.assertEqual(price_data[1]["time"], "2024-02-02")

    def test_load_price_data_returns_empty_when_dates_invalid(self):
        self.module.yf = types.SimpleNamespace(
            download=lambda *args, **kwargs: pd.DataFrame(
                {
                    "Open": [1],
                    "High": [1],
                    "Low": [1],
                    "Close": [1],
                },
                index=pd.to_datetime([pd.NaT]),
            )
        )

        price_data = self.module.load_price_data("TEST_EMPTY", "1d")

        self.assertEqual(price_data, [])


if __name__ == "__main__":
    unittest.main()
