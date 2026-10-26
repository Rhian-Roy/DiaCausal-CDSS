// The Observability screen (used by tests/web/test_web.py): node observability_check.cjs URL [clinic]
// Runs a Compare (HbA1c typed as 9.87), a question, an emergency question and an Investigate search on the real page, then opens
// #observability and reports what it shows: the requests, their statuses, one trace's lifecycle and timeline, and whether any
// typed value or question word reached a record. With "clinic" the page is served by the DiaCausal server (uvicorn), so the question
// goes to POST /api/v1/ask and the server's stored trace must be listed and linked from the browser's span.
const { chromium } = require(require('path').join(__dirname, '..', 'e2e', 'node_modules', 'playwright'));
(async () => {
  const url = process.argv[2];
  const clinic = process.argv[3] === 'clinic';
  const b = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  const p = await ctx.newPage();
  const errors = [];
  const api = [];
  p.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  p.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  p.on('request', (r) => { if (r.url().includes('/api/')) api.push(new URL(r.url()).pathname); });
  const c = {};
  await p.goto(url);
  await p.getByText('Fill in the patient details to start').waitFor({ timeout: 20000 });
  // nothing recorded yet: the empty state
  await p.goto(url + '#observability');
  await p.locator('#obs-root .emptystate').waitFor({ timeout: 10000 });
  c.emptyState = await p.locator('#obs-root .emptystate').textContent();
  c.headerLink = await p.locator('.topbar a[href="#observability"]').count();

  await p.goto(url + '#patient-details');
  await p.getByRole('button', { name: /Typical patient/ }).click();
  await p.fill('#f-hba1c', '9.87');
  await p.locator('#thread .compare-btn').click();
  await p.locator('#thread .answer[data-compare] table.options').waitFor({ timeout: 20000 });
  await p.fill('#message', 'Is ketoacidosis a risk with SGLT2 inhibitors?');
  await p.press('#message', 'Enter');
  await p.locator('#thread .answer:not([data-compare]) .decides').first().waitFor({ timeout: 20000 });
  await p.fill('#message', 'Patient unconscious in OPD, which add-on?');
  await p.press('#message', 'Enter');
  await p.waitForTimeout(500);
  await p.goto(url + '#investigate');
  await p.fill('#q', 'Metformin and reduced kidney function');
  await p.press('#q', 'Enter');
  await p.locator('#ev-out .decides').first().waitFor({ timeout: 20000 });

  await p.goto(url + '#observability');
  await p.locator('#obs-root .obs-table').waitFor({ timeout: 10000 });
  c.rows = await p.$$eval('#obs-root .obs-table tbody tr', (rows) => rows.map((r) => ({
    workflow: r.querySelector('[data-label="Workflow"]').firstChild.textContent,
    status: r.querySelector('[data-label="Status"] .badge').textContent,
    ci: r.querySelector('[data-label="Causal inference"] .badge').textContent,
    rag: r.querySelector('[data-label="Retrieval"] .badge').textContent })));
  c.tiles = await p.$$eval('#obs-root .tile', (t) => Object.fromEntries(t.map((x) => [x.querySelector('span').textContent, x.querySelector('b').textContent])));
  c.problems = await p.locator('#obs-root [aria-labelledby="obs-prob-h"] tbody tr').count();
  c.sources = await p.$$eval('#obs-root input[name="obs-src"]', (i) => i.map((x) => x.value));

  // open the Compare trace
  const openRow = async (workflow) => {
    const row = p.locator('#obs-root .obs-table tbody tr', { has: p.locator('[data-label="Workflow"]', { hasText: new RegExp(`^${workflow}`) }) }).last();
    await row.locator('.obs-open').click();
    await p.locator('.obs-detail').waitFor({ timeout: 10000 });
  };
  await openRow('compare');
  c.compareFlow = await p.$$eval('.obs-detail .obs-flow .flow__name', (x) => x.map((e) => e.textContent));
  c.compareSpans = await p.$$eval('.obs-detail .obs-span', (x) => x.map((e) => ({ name: e.querySelector('.obs-span__name').firstChild.textContent,
    depth: Number((e.className.match(/obs-depth-(\d)/) || [0, 0])[1]), status: e.querySelector('.obs-span__end .badge').textContent })));
  await p.locator('.obs-detail .obs-span', { hasText: 'safety rules' }).first().locator('summary').click();
  c.stepDetail = await p.locator('.obs-detail .obs-span[open] .obs-kv').first().textContent();
  c.integrated = await p.$$eval('.obs-detail [aria-labelledby="obs-int-h"] tbody th', (x) => x.map((e) => e.textContent));
  await p.locator('.obs-detail .chip', { hasText: 'Causal inference' }).click();
  c.ciOnly = await p.$$eval('.obs-detail .obs-span', (x) => x.length);
  c.hash = await p.evaluate(() => location.hash);
  await p.locator('.obs-detail button', { hasText: 'Close' }).click();

  // the stopped question
  await p.selectOption('#obs-status', 'blocked');
  await p.locator('#obs-root form.obs-controls button[type="submit"]').click();
  await p.waitForTimeout(300);
  c.blockedRows = await p.$$eval('#obs-root .obs-table tbody tr', (rows) => rows.map((r) => r.querySelector('[data-label="Workflow"]').firstChild.textContent));
  await openRow('question');
  c.blockedFlow = await p.$$eval('.obs-detail .obs-flow .flow__desc', (x) => x.map((e) => e.textContent));

  // nothing typed reached a record or the screen
  const records = await p.evaluate(() => JSON.stringify(window.DiaCausalTrace.list()));
  const screen = await p.locator('#view-observability').textContent();
  c.leaks = ['9.87', 'ketoacidosis', 'unconscious', 'Metformin and reduced'].filter((s) => records.includes(s) || screen.includes(s));

  if (clinic) {
    await p.selectOption('#obs-status', '');
    await p.locator('#obs-root form.obs-controls button[type="submit"]').click();
    await p.waitForTimeout(300);
    await openRow('question');
    c.serverButton = await p.locator('.obs-detail button', { hasText: "Open the server's trace" }).count();
    if (c.serverButton) {
      await p.locator('.obs-detail button', { hasText: "Open the server's trace" }).click();
      await p.locator('.obs-detail').waitFor({ timeout: 10000 });
      await p.waitForTimeout(500);
      c.serverFlow = await p.$$eval('.obs-detail .obs-flow .flow__name', (x) => x.map((e) => e.textContent));
      c.serverSteps = await p.$$eval('.obs-detail .obs-span.obs-depth-1 .obs-span__name', (x) => x.map((e) => e.firstChild.textContent));
      c.serverRecordedBy = await p.locator('.obs-detail .obs-kv').first().textContent();
      c.serverEngine = await p.locator('.obs-engine summary').textContent();
      const serverScreen = await p.locator('#view-observability').textContent();
      c.serverLeaks = ['9.87', 'ketoacidosis'].filter((s) => serverScreen.includes(s));
    }
  }
  // a phone: the open trace fits the width
  await p.setViewportSize({ width: 390, height: 844 });
  await p.waitForTimeout(300);
  c.horizontalOverflow = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  c.api = [...new Set(api)];
  await b.close();
  console.log(JSON.stringify({ errors, checks: c }));
})().catch((e) => { console.error(e); process.exit(1); });
