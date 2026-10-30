// Shared test helpers.
// Every test runs offline against mocked evaluator APIs, so no API keys or credits are used.
const { test: base, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const ROOT = path.resolve(__dirname, '..');
const pageUrl = (file) => pathToFileURL(path.join(ROOT, file)).href;

// A realistic judge response that matches the JSON schema in SYSTEM_PROMPT.
function judgeResult(overrides = {}) {
  return {
    relevance_score: 90, relevance_reasoning: 'Answers the question directly.',
    tone_score: 88, tone_reasoning: 'Friendly and professional.',
    groundedness_score: 95, groundedness_reasoning: 'Matches the provided context.',
    system_prompt_adherence_score: 85, system_prompt_adherence_reasoning: 'Follows the main rules.',
    system_prompt_instructions_detected: ['Answer only from context', 'Never quote prices'],
    system_prompt_violations: [],
    overall_score: 90,
    verdict: 'Pass: accurate and grounded.',
    response_improvements: ['Add a link to the help article.'],
    prompt_refinements: ['Ask which plan the user is on.'],
    ...overrides,
  };
}

// Wraps a judge result in the Anthropic Messages API response shape.
function anthropicBody(result) {
  return JSON.stringify({ content: [{ type: 'text', text: JSON.stringify(result) }] });
}

// Optional offline mode: set VENDOR_DIR to a folder holding xlsx.full.min.js and docx.js
// to serve the batch runner's CDN libraries locally (CI without internet access).
const VENDOR = {
  'cdn.sheetjs.com': 'xlsx.full.min.js',
  'cdn.jsdelivr.net': 'docx.js',
};

const test = base.extend({
  page: async ({ page }, use) => {
    if (process.env.VENDOR_DIR) {
      for (const [host, file] of Object.entries(VENDOR)) {
        await page.route(`https://${host}/**`, (route) =>
          route.fulfill({
            contentType: 'application/javascript',
            body: fs.readFileSync(path.join(process.env.VENDOR_DIR, file)),
          }));
      }
    }
    await use(page);
  },
});

module.exports = { test, expect, pageUrl, judgeResult, anthropicBody, ROOT };
