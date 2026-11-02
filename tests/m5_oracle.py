"""Read-only frozen M5 expectations, independent of mapping implementation."""
import json
from pathlib import Path


EXPECTED_FILE = Path(__file__).parent / 'fixtures/m5_expectations.json'


def load_expected():
    return json.loads(EXPECTED_FILE.read_text())
