"""Shared pytest fixtures for the LLM Judge Evaluator.

Python/pytest port of tests/fixtures.js. Every test runs offline against a
mocked evaluator API, so no API keys or credits are used.
"""
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Optional offline mode: VENDOR_DIR holds local copies of the batch runner's CDN
# libraries, for CI machines without internet access.
VENDOR = {
    "cdn.sheetjs.com": "xlsx.full.min.js",
    "cdn.jsdelivr.net": "docx.js",
}


# ── Plain helpers ────────────────────────────────────────────────────────────

def page_url(file_name: str) -> str:
    """file:// URL for one of the app's HTML pages."""
    return (ROOT / file_name).as_uri()


def make_judge_result(**overrides) -> dict:
    """A realistic judge response matching the JSON schema the app asks for."""
    result = {
        "relevance_score": 90, "relevance_reasoning": "Answers the question directly.",
        "tone_score": 88, "tone_reasoning": "Friendly and professional.",
        "groundedness_score": 95, "groundedness_reasoning": "Matches the provided context.",
        "system_prompt_adherence_score": 85,
        "system_prompt_adherence_reasoning": "Follows the main rules.",
        "system_prompt_instructions_detected": ["Answer only from context", "Never quote prices"],
        "system_prompt_violations": [],
        "overall_score": 90,
        "verdict": "Pass: accurate and grounded.",
        "response_improvements": ["Add a link to the help article."],
        "prompt_refinements": ["Ask which plan the user is on."],
    }
    result.update(overrides)
    return result


def anthropic_body(result: dict) -> str:
    """Wrap a judge result in the Anthropic Messages API response shape."""
    return json.dumps({"content": [{"type": "text", "text": json.dumps(result)}]})


def gemini_body(result: dict) -> str:
    """Wrap a judge result in the Gemini generateContent response shape."""
    return json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(result)}]}}]})


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Match the JS suite's viewport. Overrides pytest-playwright's built-in fixture."""
    return {**browser_context_args, "viewport": {"width": 1400, "height": 1000}}


@pytest.fixture(autouse=True)
def vendor_routes(request):
    """Serve CDN libraries from VENDOR_DIR when it is set.

    Autouse, but it only touches browser tests: a test that never asks for
    `page` (the sample-data checks) doesn't start a browser.
    """
    vendor_dir = os.environ.get("VENDOR_DIR")
    if vendor_dir and "page" in request.fixturenames:
        page = request.getfixturevalue("page")
        for host, file_name in VENDOR.items():
            body = (Path(vendor_dir) / file_name).read_bytes()
            page.route(f"https://{host}/**", serve_script(body))
    yield


def serve_script(body: bytes):
    """Route handler that answers with a local copy of a script."""
    def handler(route):
        route.fulfill(content_type="application/javascript", body=body)
    return handler


@pytest.fixture
def judge_result():
    """Factory fixture: call judge_result(overall_score=40) to vary the response."""
    return make_judge_result


class JudgeMock:
    """Records every call to the mocked judge and replies with a chosen result."""

    def __init__(self):
        self.calls = []
        self.responder = lambda content: make_judge_result()

    def reply_with(self, result_or_fn):
        """Pass a fixed result dict, or a function of the prompt content."""
        self.responder = result_or_fn if callable(result_or_fn) else (lambda _: result_or_fn)

    def handle(self, route):
        body = json.loads(route.request.post_data)
        self.calls.append(body)
        content = body["messages"][0]["content"]
        route.fulfill(content_type="application/json", body=anthropic_body(self.responder(content)))


@pytest.fixture
def mock_anthropic(page):
    """Intercept Anthropic API calls; the test reads .calls afterwards."""
    mock = JudgeMock()
    page.route("https://api.anthropic.com/v1/messages", mock.handle)
    yield mock
    page.unroute("https://api.anthropic.com/v1/messages")


@pytest.fixture
def evaluator(page):
    """The Single Evaluator page, opened and ready."""
    page.goto(page_url("evaluator.html"))
    return page


@pytest.fixture(scope="session")
def sample_csv() -> Path:
    return ROOT / "samples" / "sample_input.csv"


@pytest.fixture(scope="session")
def sample_system_prompt() -> str:
    return (ROOT / "samples" / "sample_system_prompt.txt").read_text(encoding="utf-8")
