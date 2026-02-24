"""Tests for turtle_rpm.symbols loader."""

import csv
import tempfile
import unittest
from pathlib import Path

from turtle_rpm.symbols import get_default_symbols_path, load_symbols_from_file


class TestLoadSymbolsFromFile(unittest.TestCase):
    def test_returns_empty_list_when_file_missing(self):
        result = load_symbols_from_file(Path("/nonexistent/symbols.csv"))
        self.assertEqual(result, [])

    def test_parses_csv_with_symbol_and_name(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
        ) as f:
            w = csv.writer(f)
            w.writerow(["symbol", "name", "exchange"])
            w.writerow(["AAPL", "Apple Inc. - Common Stock", "Q"])
            w.writerow(["GOOGL", "Alphabet Inc. Class A", "Q"])
            path = Path(f.name)
        try:
            result = load_symbols_from_file(path)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["symbol"], "AAPL")
            self.assertEqual(result[0]["name"], "Apple Inc. - Common Stock")
            self.assertEqual(result[0]["exchange"], "Q")
            self.assertEqual(result[1]["symbol"], "GOOGL")
            self.assertEqual(result[1]["name"], "Alphabet Inc. Class A")
        finally:
            path.unlink()

    def test_skips_empty_symbol_rows(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
        ) as f:
            w = csv.writer(f)
            w.writerow(["symbol", "name"])
            w.writerow(["A", "Alpha"])
            w.writerow(["", "No symbol"])
            w.writerow(["B", "Beta"])
            path = Path(f.name)
        try:
            result = load_symbols_from_file(path)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["symbol"], "A")
            self.assertEqual(result[1]["symbol"], "B")
        finally:
            path.unlink()

    def test_get_default_symbols_path_returns_data_symbols_csv(self):
        p = get_default_symbols_path()
        self.assertEqual(p.name, "symbols.csv")
        self.assertEqual(p.parent.name, "data")


if __name__ == "__main__":
    unittest.main()
