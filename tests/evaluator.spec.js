const { test, expect, pageUrl, judgeResult, anthropicBody } = require('./fixtures');

test.describe('Landing page', () => {
  test('links to both tools', async ({ page }) => {
    await page.goto(pageUrl('index.html'));
    await expect(page.getByRole('link', { name: /Single Evaluator/ })).toHaveAttribute('href', 'evaluator.html');
    await expect(page.getByRole('link', { name: /Batch Runner/ })).toHaveAttribute('href', 'batch-runner.html');
  });
});

test.describe('Single evaluator', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(pageUrl('evaluator.html'));
  });

  test('switching provider updates the key label and default model', async ({ page }) => {
    const provider = page.locator('#evaluatorProvider');
    const modelId = page.locator('#evaluatorModelId');

    await provider.selectOption('anthropic');
    await expect(page.locator('#apiKeyLabel')).toHaveText('Anthropic API Key');
    await expect(modelId).toHaveValue('claude-sonnet-4-5');

    await provider.selectOption('gemini');
    await expect(page.locator('#apiKeyLabel')).toHaveText('Google Cloud API Key');
    await expect(modelId).toHaveValue('gemini-2.5-pro');

    // OpenRouter picks its model from a live list, so the free-text field is hidden
    await provider.selectOption('openrouter');
    await expect(page.locator('#modelIdWrap')).toBeHidden();
    await expect(page.locator('#loadModelsBtn')).toBeVisible();
  });

  test('requires a key, prompt and response before calling the judge', async ({ page }) => {
    let called = false;
    await page.route('https://api.anthropic.com/**', (route) => { called = true; route.abort(); });
    // The validation alert fires synchronously inside the click, so handle it up front
    let message = '';
    page.once('dialog', (d) => { message = d.message(); d.dismiss(); });
    await page.locator('#evalBtn').click();
    await expect.poll(() => message).toContain('Key, Prompt, and Response required');
    expect(called).toBe(false);
  });

  test('scores a response with the chosen model and renders the result', async ({ page }) => {
    let sent;
    await page.route('https://api.anthropic.com/v1/messages', async (route) => {
      sent = JSON.parse(route.request().postData());
      await route.fulfill({ contentType: 'application/json', body: anthropicBody(judgeResult()) });
    });

    await page.locator('#evaluatorProvider').selectOption('anthropic');
    await page.locator('#evaluatorModelId').fill('claude-custom-test');
    await page.locator('#apiKey').fill('sk-ant-test');
    await page.locator('#promptText').fill('How do I reset my password?');
    await page.locator('#responseText').fill('Select Forgot password on the sign-in page.');
    await page.locator('#ragContext').fill('Users reset passwords from the sign-in page.');
    await page.locator('#systemPromptText').fill('Answer only from the provided context.');
    await page.locator('#evalBtn').click();

    await expect(page.locator('#ovScore')).toHaveText('90');
    await expect(page.locator('#verdictText')).toHaveText('Pass: accurate and grounded.');
    await expect(page.locator('#scoreGrid')).toContainText('Groundedness');
    await expect(page.locator('#scoreGrid')).toContainText('System Prompt Adherence');
    await expect(page.locator('#respImprov')).toContainText('Add a link to the help article.');

    // The request used the edited model ID and carried every input to the judge
    expect(sent.model).toBe('claude-custom-test');
    expect(sent.temperature).toBe(0);
    const content = sent.messages[0].content;
    expect(content).toContain('PROMPT: How do I reset my password?');
    expect(content).toContain('RAG CONTEXT: Users reset passwords');
    expect(content).toContain('SYSTEM PROMPT: Answer only from the provided context.');
  });

  test('hides optional dimensions when their inputs are missing', async ({ page }) => {
    await page.route('https://api.anthropic.com/v1/messages', (route) =>
      route.fulfill({
        contentType: 'application/json',
        body: anthropicBody(judgeResult({ groundedness_score: null, system_prompt_adherence_score: null })),
      }));

    await page.locator('#evaluatorProvider').selectOption('anthropic');
    await page.locator('#apiKey').fill('sk-ant-test');
    await page.locator('#promptText').fill('What does the Pro plan cost?');
    await page.locator('#responseText').fill('Please contact sales.');
    await page.locator('#evalBtn').click();

    await expect(page.locator('#ovScore')).toHaveText('90');
    await expect(page.locator('#scoreGrid')).toContainText('Relevance');
    await expect(page.locator('#scoreGrid')).not.toContainText('Groundedness');
    await expect(page.locator('#scoreGrid')).not.toContainText('System Prompt Adherence');
  });

  test('reports a clear error when the judge returns plain text instead of JSON', async ({ page }) => {
    await page.route('https://api.anthropic.com/v1/messages', (route) =>
      route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ content: [{ type: 'text', text: 'I think this response is fine.' }] }),
      }));

    await page.locator('#evaluatorProvider').selectOption('anthropic');
    await page.locator('#apiKey').fill('sk-ant-test');
    await page.locator('#promptText').fill('Hello');
    await page.locator('#responseText').fill('Hi there');
    const dialog = page.waitForEvent('dialog');
    await page.locator('#evalBtn').click();
    const d = await dialog;
    expect(d.message()).toContain('plain text instead of JSON');
    await d.dismiss();
  });
});
