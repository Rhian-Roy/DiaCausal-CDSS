// Live update of the Compare card (used by tests/web/test_web.py): node live_update_check.cjs URL
// After the first Compare, every change to the panel redraws the same card without a page reload: eGFR 88 -> 40 on the
// Typical patient removes SGLT2i by R01; an empty age removes every estimate; a question answered earlier is marked.
const { chromium } = require(require('path').join(__dirname, '..', 'e2e', 'node_modules', 'playwright'));
(async () => {
  const url = process.argv[2];
  const b = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  p.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  await p.goto(url);
  await p.getByText('Fill in the patient details to start').waitFor({ timeout: 20000 });
  const box = '#thread .answer[data-compare]';
  const c = {};
  await p.getByRole('button', { name: /Typical patient/ }).click();
  await p.locator('#thread .compare-btn').click();
  await p.locator(`${box} table.options`).waitFor({ timeout: 20000 });
  const sglt2 = () => p.evaluate((sel) => {
    const card = [...document.querySelectorAll(`${sel} .scard`)].find((a) => a.querySelector('h4').textContent.startsWith('SGLT2'));
    return card ? { stop: card.classList.contains('scard--stop'), text: card.textContent } : null;
  }, box);
  c.before = await sglt2();
  // no reload: this mark would be lost; count what #live-status says
  await p.evaluate(() => {
    window.__sameLoad = true;
    window.__said = [];
    new MutationObserver(() => { const t = document.querySelector('#live-status').textContent; if (t) window.__said.push(t); })
      .observe(document.querySelector('#live-status'), { childList: true, characterData: true, subtree: true });
  });
  // a question answered for these details
  await p.fill('#message', 'Is ketoacidosis a risk with SGLT2 inhibitors?');
  await p.press('#message', 'Enter');
  await p.locator('#thread .answer:not([data-compare]) .decides').first().waitFor({ timeout: 20000 });

  // (a) eGFR 88 -> 40, typed one key at a time (debounced): SGLT2i becomes "Do not use" with R01, no number
  await p.locator('#f-egfr').click();
  await p.keyboard.press('ControlOrMeta+A');
  await p.keyboard.type('40', { delay: 60 });
  await p.waitForFunction((sel) => /Updated for the current details/.test(document.querySelector(sel).textContent), box, { timeout: 10000 });
  await p.waitForTimeout(800);
  c.after = await sglt2();
  c.sglt2Row = await p.evaluate((sel) => {
    const row = [...document.querySelectorAll(`${sel} table.options tbody tr`)].find((r) => r.querySelector('th').textContent.startsWith('SGLT2'));
    return { excluded: row.classList.contains('row--excluded'), text: row.querySelector('td').textContent };
  }, box);
  c.patientLine = await p.locator(`${box} #out .sub`).first().textContent();
  c.sameLoad = await p.evaluate(() => window.__sameLoad === true);
  c.said = await p.evaluate(() => window.__said.slice());
  c.stale = await p.locator('#thread .turn .stale').count();
  c.earlierFolded = await p.evaluate(() => [...document.querySelectorAll('#thread details.earlier')].map((d) => d.open));
  c.askAgain = await p.getByRole('button', { name: 'Ask again for the current details' }).count();

  // (c) still one Compare card after several changes, a yes/no toggle and a preset
  await p.locator('label[for="f-ascvd-yes"]').click();
  await p.waitForFunction((sel) => !document.querySelector(sel).classList.contains('answer--updating'), box);
  await p.getByRole('button', { name: /Older/ }).click();
  await p.locator(`${box} .abstaincard`).first().waitFor({ timeout: 10000 });
  c.presetLive = await p.locator(`${box} .abstaincard`).count();
  c.compareCards = await p.locator(box).count();
  c.compareTurns = await p.locator('#thread .turn', { hasText: 'Compare the three options for this patient.' }).count();
  c.cardsInBox = await p.locator(`${box} section.card`).count();

  // (b) age emptied: every estimate leaves the card at once, and the field's message is listed
  await p.locator('#f-age').fill('');
  await p.locator(`${box} [data-live="incomplete"]`).waitFor({ timeout: 2000 });
  c.incomplete = await p.evaluate((sel) => {
    const el = document.querySelector(sel);
    return { tables: el.querySelectorAll('table.options, .scard, .num').length, text: el.textContent };
  }, box);
  await p.locator('#f-age').fill('80');
  await p.locator(`${box} table.options`).waitFor({ timeout: 5000 });
  c.backAfterFix = await p.locator(`${box} table.options`).count();

  // Ask again re-runs the old question for the current details (one new turn), and only when pressed
  const turnsBefore = await p.locator('#thread .turn').count();
  await p.getByRole('button', { name: 'Ask again for the current details' }).first().click();
  await p.waitForFunction((n) => document.querySelectorAll('#thread .turn').length === n + 1, turnsBefore);
  c.askedAgain = true;
  // New patient still clears everything
  await p.getByRole('button', { name: 'New patient' }).click();
  c.clearedCards = await p.locator(box).count();
  c.sameLoadAtEnd = await p.evaluate(() => window.__sameLoad === true);
  console.log(JSON.stringify({ checks: c, errors }));
  await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
