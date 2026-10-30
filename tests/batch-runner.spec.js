const fs = require('fs');
const path = require('path');
const { test, expect, pageUrl, judgeResult, anthropicBody, ROOT } = require('./fixtures');

const SAMPLE_CSV = path.join(ROOT, 'samples', 'sample_input.csv');
const SYSTEM_PROMPT = fs.readFileSync(path.join(ROOT, 'samples', 'sample_system_prompt.txt'), 'utf8');

// Score each sample row differently so the summary counts can be checked
function scoreFor(content) {
  if (content.includes('reset my password')) return judgeResult({ overall_score: 92 });            // pass
  if (content.includes('export my data')) return judgeResult({ overall_score: 80 });               // warn
  return judgeResult({ overall_score: 40, verdict: 'Fail', system_prompt_violations: ['Quoted a price'] }); // fail
}

test('runs a full batch from the sample CSV and summarizes the results', async ({ page }) => {
  const calls = [];
  await page.route('https://api.anthropic.com/v1/messages', async (route) => {
    const body = JSON.parse(route.request().postData());
    calls.push(body);
    await route.fulfill({ contentType: 'application/json', body: anthropicBody(scoreFor(body.messages[0].content)) });
  });

  await page.goto(pageUrl('batch-runner.html'));

  // Step 1: evaluator setup
  await page.locator('#providerSelect').selectOption('anthropic');
  await page.locator('#apiKey').fill('sk-ant-test');
  await page.locator('#delaySlider').fill('1');
  await page.getByRole('button', { name: 'Next →' }).first().click();

  // Step 2: system prompt applied to every row
  await page.locator('#systemPromptText').fill(SYSTEM_PROMPT);
  await page.locator('#step2').getByRole('button', { name: 'Next →' }).click();

  // Step 3: upload and auto-map columns
  await page.locator('#fileInput').setInputFiles(SAMPLE_CSV);
  await expect(page.locator('#fileInfo')).toContainText('5 rows');
  await expect(page.locator('#runBtn')).toBeEnabled();
  await page.locator('#runBtn').click();

  // Every row is evaluated, then the summary appears
  await expect(page.locator('#summarySection')).toBeVisible({ timeout: 45_000 });
  await expect(page.locator('#resultsBody > tr:not(.row-detail)')).toHaveCount(5);
  await expect(page.locator('#resultsBody > tr.row-error')).toHaveCount(0);
  const summary = page.locator('#summaryGrid');
  await expect(summary.locator('.stat-card').nth(0)).toContainText('5');  // total
  await expect(summary.locator('.stat-card').nth(1)).toContainText('1');  // passed
  await expect(summary.locator('.stat-card').nth(2)).toContainText('1');  // warned
  await expect(summary.locator('.stat-card').nth(3)).toContainText('3');  // failed

  // The shared system prompt reached the judge on every call
  expect(calls).toHaveLength(5);
  for (const c of calls) expect(c.messages[0].content).toContain('Never quote prices');

  // CSV export downloads a file with the documented header row
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  const file = await (await download).path();
  const csv = fs.readFileSync(file, 'utf8');
  expect(csv.split('\n')[0]).toContain('Overall Score');
  expect(csv).toContain('reset my password');
});
