"""Single Evaluator and landing page: pytest port of tests/evaluator.spec.js,
plus parametrized cases for every provider and every missing input."""
import json
import re

import pytest
from playwright.sync_api import Page, expect

from conftest import anthropic_body, gemini_body, page_url


@pytest.mark.smoke
def test_landing_page_links_to_both_tools(page: Page):
    page.goto(page_url("index.html"))
    expect(page.get_by_role("link", name=re.compile("Single Evaluator"))).to_have_attribute(
        "href", "evaluator.html")
    expect(page.get_by_role("link", name=re.compile("Batch Runner"))).to_have_attribute(
        "href", "batch-runner.html")


@pytest.mark.smoke
@pytest.mark.parametrize(
    "provider, key_label, default_model",
    [
        ("anthropic", "Anthropic API Key", "claude-sonnet-4-5"),
        ("gemini", "Google Cloud API Key", "gemini-2.5-pro"),
    ],
    ids=["anthropic", "gemini"],
)
def test_provider_sets_key_label_and_default_model(evaluator: Page, provider, key_label, default_model):
    evaluator.locator("#evaluatorProvider").select_option(provider)
    expect(evaluator.locator("#apiKeyLabel")).to_have_text(key_label)
    expect(evaluator.locator("#evaluatorModelId")).to_have_value(default_model)


def test_openrouter_uses_a_model_list_instead_of_free_text(evaluator: Page):
    evaluator.locator("#evaluatorProvider").select_option("openrouter")
    expect(evaluator.locator("#modelIdWrap")).to_be_hidden()
    expect(evaluator.locator("#loadModelsBtn")).to_be_visible()


@pytest.mark.parametrize(
    "missing",
    ["#apiKey", "#promptText", "#responseText"],
    ids=["no-key", "no-prompt", "no-response"],
)
def test_each_required_input_blocks_the_judge_call(evaluator: Page, missing):
    called = []
    evaluator.route("https://api.anthropic.com/**", lambda route: (called.append(1), route.abort()))
    evaluator.locator("#evaluatorProvider").select_option("anthropic")

    inputs = {"#apiKey": "sk-ant-test", "#promptText": "Hello", "#responseText": "Hi there"}
    for selector, value in inputs.items():
        if selector != missing:
            evaluator.locator(selector).fill(value)

    # The validation alert fires inside the click, so listen for it first
    messages = []
    evaluator.once("dialog", lambda d: (messages.append(d.message), d.dismiss()))
    evaluator.locator("#evalBtn").click()

    assert messages and "Key, Prompt, and Response required" in messages[0]
    assert not called, "the judge API must not be called when input is missing"


def test_scores_a_response_and_sends_every_input(evaluator: Page, mock_anthropic):
    evaluator.locator("#evaluatorProvider").select_option("anthropic")
    evaluator.locator("#evaluatorModelId").fill("claude-custom-test")
    evaluator.locator("#apiKey").fill("sk-ant-test")
    evaluator.locator("#promptText").fill("How do I reset my password?")
    evaluator.locator("#responseText").fill("Select Forgot password on the sign-in page.")
    evaluator.locator("#ragContext").fill("Users reset passwords from the sign-in page.")
    evaluator.locator("#systemPromptText").fill("Answer only from the provided context.")
    evaluator.locator("#evalBtn").click()

    expect(evaluator.locator("#ovScore")).to_have_text("90")
    expect(evaluator.locator("#verdictText")).to_have_text("Pass: accurate and grounded.")
    expect(evaluator.locator("#scoreGrid")).to_contain_text("Groundedness")
    expect(evaluator.locator("#scoreGrid")).to_contain_text("System Prompt Adherence")
    expect(evaluator.locator("#respImprov")).to_contain_text("Add a link to the help article.")

    # The request used the edited model ID and carried every input to the judge
    sent = mock_anthropic.calls[0]
    assert sent["model"] == "claude-custom-test"
    assert sent["temperature"] == 0
    content = sent["messages"][0]["content"]
    assert "PROMPT: How do I reset my password?" in content
    assert "RAG CONTEXT: Users reset passwords" in content
    assert "SYSTEM PROMPT: Answer only from the provided context." in content


@pytest.mark.parametrize(
    "provider, url_pattern, wrap",
    [
        ("anthropic", "https://api.anthropic.com/v1/messages", anthropic_body),
        ("gemini", "https://generativelanguage.googleapis.com/**", gemini_body),
    ],
    ids=["anthropic", "gemini"],
)
def test_each_provider_response_shape_is_parsed(evaluator: Page, judge_result, provider, url_pattern, wrap):
    """Same judge result, each provider's API envelope: the UI shows the same score."""
    evaluator.route(url_pattern, lambda route: route.fulfill(
        content_type="application/json", body=wrap(judge_result(overall_score=77))))

    evaluator.locator("#evaluatorProvider").select_option(provider)
    evaluator.locator("#apiKey").fill("test-key")
    evaluator.locator("#promptText").fill("Hello")
    evaluator.locator("#responseText").fill("Hi there")
    evaluator.locator("#evalBtn").click()

    expect(evaluator.locator("#ovScore")).to_have_text("77")


def test_hides_optional_dimensions_when_inputs_are_missing(evaluator: Page, mock_anthropic, judge_result):
    mock_anthropic.reply_with(judge_result(groundedness_score=None, system_prompt_adherence_score=None))

    evaluator.locator("#evaluatorProvider").select_option("anthropic")
    evaluator.locator("#apiKey").fill("sk-ant-test")
    evaluator.locator("#promptText").fill("What does the Pro plan cost?")
    evaluator.locator("#responseText").fill("Please contact sales.")
    evaluator.locator("#evalBtn").click()

    grid = evaluator.locator("#scoreGrid")
    expect(evaluator.locator("#ovScore")).to_have_text("90")
    expect(grid).to_contain_text("Relevance")
    expect(grid).not_to_contain_text("Groundedness")
    expect(grid).not_to_contain_text("System Prompt Adherence")


def test_reports_a_clear_error_when_the_judge_returns_plain_text(evaluator: Page):
    evaluator.route("https://api.anthropic.com/v1/messages", lambda route: route.fulfill(
        content_type="application/json",
        body=json.dumps({"content": [{"type": "text", "text": "I think this response is fine."}]})))

    evaluator.locator("#evaluatorProvider").select_option("anthropic")
    evaluator.locator("#apiKey").fill("sk-ant-test")
    evaluator.locator("#promptText").fill("Hello")
    evaluator.locator("#responseText").fill("Hi there")

    with evaluator.expect_event("dialog") as dialog_info:
        evaluator.locator("#evalBtn").click()
    dialog = dialog_info.value
    assert "plain text instead of JSON" in dialog.message
    dialog.dismiss()
