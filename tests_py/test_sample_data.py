"""Fast data checks on the sample files (no browser). These catch a broken
sample before the slower UI tests run."""
import csv

import pytest

REQUIRED_COLUMNS = {"prompt", "response"}


def load_rows(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.data
def test_sample_csv_has_the_required_columns(sample_csv):
    with sample_csv.open(newline="", encoding="utf-8") as f:
        header = set(next(csv.reader(f)))
    assert REQUIRED_COLUMNS <= header, f"missing columns: {REQUIRED_COLUMNS - header}"


@pytest.mark.data
def test_every_sample_row_has_a_prompt_and_response(sample_csv):
    rows = load_rows(sample_csv)
    assert len(rows) == 5
    for number, row in enumerate(rows, start=1):
        assert row["prompt"].strip(), f"row {number} has no prompt"
        assert row["response"].strip(), f"row {number} has no response"


@pytest.mark.data
@pytest.mark.parametrize("rule", ["Never quote prices", "Never discuss or compare competitor products"])
def test_sample_system_prompt_contains_the_guardrails_the_tests_rely_on(sample_system_prompt, rule):
    assert rule in sample_system_prompt
