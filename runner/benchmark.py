"""Benchmark runner skeleton.

Provider adapters are added incrementally after their current API contracts
are verified. This runner deliberately does not guess provider endpoints.
"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "test_case.json"


def load_test_case() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def main() -> None:
    test_case = load_test_case()
    print("AutoZone benchmark")
    print(f"URL: {test_case['url']}")
    print(f"ZIP: {test_case['location']['zip']}")
    print(f"Expected store: #{test_case['expected_store']['store_id']}")
    print("Provider adapters will be executed here once configured.")


if __name__ == "__main__":
    main()
