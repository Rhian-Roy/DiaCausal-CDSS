// iPhone 15-sized browser run of the website (screens-v2 markup) (used by tests/web/test_web.py): node phone_check.cjs URL OUTDIR
const { chromium, devices } = require(require('path').join(__dirname, '..', 'e2e', 'node_modules', 'playwright'));
(async () => {
  const url = process.argv[2], out = process.argv[3];
  const b = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const ctx = await b.newContext({ viewport: { width: 393, height: 852 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1' });
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', e => errors.push('pageerror: ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  await p.goto(url);
  // screens-v2: the panel starts empty (13); an example fills it (16); Compare runs the six stages (20)
  await p.getByText('Fill in the patient details to start').waitFor({ timeout: 20000 });
  const newPatient = async () => {  // on a phone the panel folds after Compare: tap the strip to open it
    if (!(await p.locator('#pd').evaluate((d) => d.open))) await p.locator('.pd__summary').click();
    await p.getByRole('button', { name: 'New patient' }).click();
  };
  const compareWith = async (name) => {
    await p.getByRole('button', { name }).click();
    await p.locator('#thread .compare-btn').last().click();
  };
  await compareWith(/Typical patient/);
  await p.locator('#out table.options').first().waitFor({ timeout: 20000 });  // the answer card (screens 17/21, P24)
  await p.screenshot({ path: out + '/p0.png', fullPage: true });
  const checks = {};
  checks.intended = await p.getByText('Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.').first().isVisible();
  // P27: a cited passage opens as a bottom sheet (18) and Esc closes it; a blocked question shows its notice (09-12)
  await p.locator('#out .cite').first().click();
  await p.locator('#drawer').waitFor();
  checks.drawerBottom = await p.evaluate(() => Math.round(document.querySelector('#drawer').getBoundingClientRect().bottom) === window.innerHeight);
  await p.screenshot({ path: out + '/p0b.png' });
  await p.keyboard.press('Escape');
  checks.drawerClosed = (await p.locator('#drawer').count()) === 0;
  await p.fill('#message', 'Patient unconscious in OPD, which add-on?');
  await p.press('#message', 'Enter');
  checks.emergency = await p.locator('#thread .emergency').last().isVisible();
  await newPatient();
  await compareWith(/eGFR 40/);
  await p.locator('#out tr.row--excluded').first().waitFor();
  checks.excluded = await p.locator('#out tr.row--excluded').count();
  checks.caution = await p.locator('#out .scard--check').count();
  await p.screenshot({ path: out + '/p1.png', fullPage: true });
  await newPatient();
  await compareWith(/Older/);
  await p.locator('#out .abstaincard').first().waitFor();
  checks.insufficient = await p.locator('#out .abstaincard').count();
  await p.screenshot({ path: out + '/p2.png', fullPage: true });
  await p.click('a[data-route="analysis"]');
  await p.locator('.tile').first().waitFor();
  checks.tiles = await p.locator('.tile').count();
  checks.charts = await p.locator('#view-results svg.cbar').count();
  await p.waitForTimeout(800);
  await p.screenshot({ path: out + '/p3.png', fullPage: false });
  await p.click('a[data-route="guide"]');
  await p.locator('#g-methods > summary').click();
  await p.locator('#doc h1, #doc h2').first().waitFor();
  checks.docHeadings = await p.locator('#doc h2').count();
  await p.screenshot({ path: out + '/p4.png' });
  await p.click('a[data-route="about"]');
  await p.getByText('B.Tech in Computer Engineering').waitFor();
  checks.team = await p.getByText('Guide: Mr. Rahul Jadhav.').isVisible();
  await p.screenshot({ path: out + '/p5.png', fullPage: true });
  await p.click('a[data-route="investigate"]');
  await p.getByRole('button', { name: 'Metformin and kidney function' }).click();
  await p.locator('#ev-out .result').first().waitFor();
  checks.passages = await p.locator('#ev-out .result .passage').count();
  checks.citesFda = (await p.locator('#ev-out .result dd').first().textContent()).startsWith('S08 · US FDA');
  checks.sourcesInSearch = await p.locator('#ev-sources li.src-ok').count();
  checks.sourcesFolded = !(await p.locator('#ev-side').evaluate((d) => d.open));  // a phone starts with the sources list folded
  await p.screenshot({ path: out + '/p6.png', fullPage: true });
  await p.fill('#q', 'How much does glimepiride cost in India?');
  await p.press('#q', 'Enter');
  checks.abstains = (await p.locator('#ev-out .finding').textContent()).startsWith('Insufficient evidence');
  checks.demoBanner = await p.locator('#demo').isVisible();
  await p.click('#acct');
  checks.accountDemo = await p.getByText('Sign-in is off on this copy').waitFor().then(() => true, () => false);
  await p.screenshot({ path: out + '/p7.png', fullPage: true });
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  checks.horizontalOverflow = overflow;
  console.log(JSON.stringify({ checks, errors }));
  await b.close();
})();
