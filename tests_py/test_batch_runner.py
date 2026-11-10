"""Batch Runner: pytest port of tests/batch-runner.spec.js, plus boundary tests
for the pass/warn/fail score bands (86-100 pass, 76-85 warn, 0-75 fail)."""
import csv
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from conftest import make_judge_result, page_url

ROWS = "#resultsBody > tr:not(.row-detail)"


def score_for(content: str) -> dict:
    """Score each sample row differently so the summary counts can be checked."""
    if "reset my password" in content:
        return make_judge_result(overall_score=92)  # pass
    if "export my data" in content:
        return make_judge_result(overall_score=80)  # warn
    return make_judge_result(overall_score=40, verdict="Fail",
                             system_prompt_violations=["Quoted a price"])  # fail


def run_batch(page: Page, csv_path: Path, system_prompt: str = ""):
    """Walk the three setup steps and start the run."""
    page.goto(page_url("batch-runner.html"))

    # Step 1: evaluator setup
    page.locator("#providerSelect").select_option("anthropic")
    page.locator("#apiKey").fill("sk-ant-test")
    page.locator("#delaySlider").fill("1")
    page.get_by_role("button", name="Next →").first.click()

    # Step 2: system prompt applied to every row
    page.locator("#systemPromptText").fill(system_prompt)
    page.locator("#step2").get_by_role("button", name="Next →").click()

    # Step 3: upload, auto-map columns, run
    page.locator("#fileInput").set_input_files(str(csv_path))
    expect(page.locator("#runBtn")).to_be_enabled()
    page.locator("#runBtn").click()


@pytest.mark.batch
def test_full_batch_from_sample_csv(page: Page, mock_anthropic, sample_csv, sample_system_prompt):
    mock_anthropic.reply_with(score_for)
    run_batch(page, sample_csv, sample_system_prompt)

    expect(page.locator("#fileInfo")).to_contain_text("5 rows")
    expect(page.locator("#summarySection")).to_be_visible(timeout=45_000)
    expect(page.locator(ROWS)).to_have_count(5)
    expect(page.locator("#resultsBody > tr.row-error")).to_have_count(0)

    cards = page.locator("#summaryGrid .stat-card")
    for index, expected in enumerate(["5", "1", "1", "3"]):  # total, passed, warned, failed
        expect(cards.nth(index)).to_contain_text(expected)

    # The shared system prompt reached the judge on every call
    assert len(mock_anthropic.calls) == 5
    for call in mock_anthropic.calls:
        assert "Never quote prices" in call["messages"][0]["content"]

    # CSV export downloads a file with the documented header row
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export CSV").click()
    exported = Path(download_info.value.path()).read_text(encoding="utf-8")
    assert "Overall Score" in exported.splitlines()[0]
    assert "reset my password" in exported


@pytest.mark.batch
@pytest.mark.parametrize(
    "score, expected_class",
    [(100, "row-pass"), (86, "row-pass"), (85, "row-warn"),
     (76, "row-warn"), (75, "row-fail"), (0, "row-fail")],
)
def test_score_band_boundaries(page: Page, mock_anthropic, tmp_path, score, expected_class):
    """Boundary values on each side of the 86 and 76 cut-offs."""
    one_row = tmp_path / "one_row.csv"
    with one_row.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["prompt", "response"])
        writer.writerow(["How do I reset my password?", "Use Forgot password."])

    mock_anthropic.reply_with(make_judge_result(overall_score=score))
    run_batch(page, one_row)

    expect(page.locator("#summarySection")).to_be_visible(timeout=30_000)
    expect(page.locator(ROWS)).to_have_count(1)
    expect(page.locator(ROWS).first).to_have_class(expected_class)
