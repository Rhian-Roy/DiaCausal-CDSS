// Every screens-v2 screen the website builds (P07), at 1280 px and 390 px: a screenshot, the visible HTML
// (checked by tests/web/test_web.py with design/screens-v2/handoff/check_screens.py) and a few facts.
// Sign-in screens use a fake account service: Supabase's replies are answered here, in the browser,
// so no real account, key or network is involved.      node screens_check.cjs URL OUTDIR
const { chromium } = require(require('path').join(__dirname, '..', 'e2e', 'node_modules', 'playwright'));
const fs = require('fs');

const MOCK = 'https://mock-account-service.test';
const NOW = Date.now();
const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
const USER_ID = '00000000-0000-4000-8000-000000000001';
function jwt(aal) {
  return [b64({ alg: 'HS256', typ: 'JWT' }), b64({ sub: USER_ID, aud: 'authenticated', role: 'authenticated', aal,
    amr: [{ method: aal === 'aal2' ? 'totp' : 'password', timestamp: Math.floor(NOW / 1000) }], exp: Math.floor(NOW / 1000) + 10 * 365 * 86400,
    session_id: 's1', email: 'doctor@hospital.example' }), 'sig'].join('.');
}
function user(factors) {
  return { id: USER_ID, aud: 'authenticated', role: 'authenticated', email: 'doctor@hospital.example', app_metadata: {},
    user_metadata: { full_name: 'Test Doctor' }, created_at: '2026-10-01T00:00:00Z', factors };
}
const VERIFIED = [{ id: 'f1', factor_type: 'totp', status: 'verified', friendly_name: 'DiaCausal', created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z' }];
const PROFILE = { full_name: 'Test Doctor', email: 'doctor@hospital.example', role: 'clinician', approved: true, rejected: false,
  is_admin: false, intended_use_ack_at: null, created_at: '2026-10-01T00:00:00Z' };

/** A browser context whose account service is fake. `who`: null (signed out), "aal1-new" (password only, no app yet),
 *  "aal2" (signed in with the code). `ack`: intended use acknowledged. `token`: the sign-in reply (status, body). */
async function context(b, viewport, { accounts = true, who = null, ack = false, token = null } = {}) {
  const ctx = await b.newContext({ viewport, deviceScaleFactor: 1, isMobile: viewport.width < 900, hasTouch: viewport.width < 900 });
  if (accounts) {
    await ctx.route('**/config.json', (r) => r.fulfill({ json: { supabaseUrl: MOCK, supabaseKey: 'sb_publishable_test' } }));
    const factors = who === 'aal2' ? VERIFIED : [];
    await ctx.route(MOCK + '/**', (r) => {
      const url = r.request().url();
      if (url.includes('/auth/v1/token')) return r.fulfill(token ? { status: token[0], json: token[1] } : { status: 400, json: { msg: 'Invalid login credentials' } });
      if (url.includes('/auth/v1/user')) return r.fulfill({ json: user(factors) });
      if (url.includes('/auth/v1/factors')) {
        return r.fulfill({ json: { id: 'f-new', type: 'totp', friendly_name: 'DiaCausal', totp: {
          qr_code: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="white"/><rect x="2" y="2" width="6" height="6"/></svg>',
          secret: 'ABCDEFGHIJKLMNOPQRSTUVWX', uri: 'otpauth://totp/DiaCausal' } } });
      }
      if (url.includes('/rest/v1/profiles')) return r.fulfill({ json: { ...PROFILE, intended_use_ack_at: ack ? '2026-10-01T00:00:00Z' : null } });
      if (url.includes('/auth/v1/logout')) return r.fulfill({ status: 204, body: '' });
      return r.fulfill({ json: {} });
    });
    if (who) {
      const session = { access_token: jwt(who === 'aal2' ? 'aal2' : 'aal1'), refresh_token: 'r1', token_type: 'bearer',
        expires_in: 3600, expires_at: Math.floor(NOW / 1000) + 10 * 365 * 86400, user: user(factors) };
      await ctx.addInitScript((s) => localStorage.setItem('diacausal-auth', s), JSON.stringify(session));
    }
  } else {
    await ctx.route('**/config.json', (r) => r.fulfill({ status: 404, body: '' }));
  }
  return ctx;
}

/** The visible part of the page: header, intended-use line, tabs, the open view and any open dialog. */
async function snapshot(p) {
  return p.evaluate(() => {
    const parts = ['.topbar', '.useline', '.tabs'].map((s) => document.querySelector(s).outerHTML);
    for (const v of document.querySelectorAll('.view')) if (!v.hidden) parts.push(v.outerHTML);
    const modal = document.querySelector('#session-modal');
    if (!modal.hidden) parts.push(modal.outerHTML);
    return '<!doctype html><html><head><title>snapshot</title></head><body>' + parts.join('\n') + '</body></html>';
  });
}

const fill = async (p, values) => {
  for (const [name, v] of Object.entries(values)) await p.fill(`#f-${name}`, String(v));
  for (const [name, v] of [['sex', 'female'], ['ascvd', 'no'], ['hf', 'no'], ['hypo', 'none'], ['dka_history', 'no'],
    ['pancreatitis_history', 'no'], ['t1d', 'no'], ['low_income', 'no']]) await p.click(`label[for="f-${name}-${v}"]`);
};
const openPanel = async (p) => { if (!(await p.locator('#pd').evaluate((d) => d.open))) await p.locator('.pd__summary').click(); };
const text = (p, sel) => p.locator(sel).first().innerText();

const SCREENS = [
  ['01-signin', { who: null }, '#account', async () => {}, async (p) => ({ h1: await text(p, '#account-main h1'), otp: await p.locator('#otp').count() })],
  ['02-signin-error', { who: null, token: [400, { msg: 'Invalid login credentials' }] }, '#account', async (p) => {
    await p.fill('#email', 'doctor@hospital.example'); await p.fill('#password', 'wrong password here'); await p.fill('#otp', '123456');
    await p.locator('#account-main button[type=submit]').click();
    await p.getByText('Those details did not match').waitFor();
  }, async (p) => ({ alert: await text(p, '#account-main .alert--danger'), invalid: await p.locator('#account-main input[aria-invalid="true"]').count() })],
  ['03-signin-locked', { who: null, token: [429, { msg: 'Request rate limit reached' }] }, '#account', async (p) => {
    await p.fill('#email', 'doctor@hospital.example'); await p.fill('#password', 'a password here'); await p.locator('#account-main button[type=submit]').click();
    await p.getByText('Signing in is locked').waitFor();
  }, async (p) => ({ alert: await text(p, '#account-main .alert--check') })],
  ['06-mfa-setup', { who: 'aal1-new' }, '#account', async (p) => { await p.locator('.qrimg').waitFor(); },
    async (p) => ({ h1: await text(p, '#account-main h1'), keyParts: await p.locator('.key span').count(), qr: await p.locator('.qrimg').count() })],
  ['07-intended-use', { who: 'aal2', ack: false }, '#account', async (p) => { await p.getByText('How to use DiaCausal').waitFor(); },
    async (p) => ({ h1: await text(p, '#account-main h1'), doesNot: await p.locator('#account-main .list li').count() })],
  ['08-session-ending', { who: 'aal2', ack: true, clock: true }, '#patient-details', async (p) => {
    await p.locator('#view-try').waitFor();
    await p.clock.fastForward('13:40');
    await p.clock.runFor(20000);
    await p.locator('#session-modal').waitFor();
  }, async (p) => ({ modal: await text(p, '#session-modal h2'), user: await text(p, '#acct-name') })],
  ['13-panel-empty', { accounts: false }, '#patient-details', async (p) => { await p.getByText('Fill in the patient details to start').waitFor(); },
    async (p) => ({ empty: await text(p, '#thread .emptystate h3') })],
  ['14-panel-filled', { accounts: false }, '#patient-details', async (p) => {
    await openPanel(p); await fill(p, { age: 58, duration_years: 6, hba1c: 8.4, egfr: 62, bmi: 31.2 });
    await p.getByText('Details received').waitFor();
  }, async (p) => ({ strip: await p.locator('#pd-strip').innerText(), badge: await text(p, '.pd-badge:not([hidden])'), ready: await text(p, '#thread .card h3') })],
  ['15-panel-out-of-range', { accounts: false }, '#patient-details', async (p) => {
    await openPanel(p); await fill(p, { age: 58, duration_years: 6, hba1c: 45, egfr: 62, bmi: 31.2 });
    await p.locator('#f-hba1c').blur();
    await p.locator('#hba1c-err').waitFor();
    await p.locator('#f-hba1c').scrollIntoViewIfNeeded();
  }, async (p) => ({ error: await text(p, '#hba1c-err'), invalid: await p.locator('#f-hba1c[aria-invalid="true"]').count(), compare: await p.locator('.compare-btn').count() })],
  ['16-panel-example-data', { accounts: false }, '#patient-details', async (p) => {
    await openPanel(p); await p.getByRole('button', { name: /Typical patient/ }).click();
    await p.getByText('Details received').waitFor();
  }, async (p) => ({ badge: await text(p, '.pd-badge:not([hidden])'), pressed: await p.locator('[data-preset][aria-pressed="true"]').count() })],
  ['20-loading-stages', { accounts: false, clock: true }, '#patient-details', async (p) => {
    await openPanel(p); await p.getByRole('button', { name: /Typical patient/ }).click();
    await p.locator('#thread .compare-btn').click();
    await p.clock.runFor(300);
    await p.getByText('Working through it').waitFor();
  }, async (p) => ({ states: await p.locator('.stage__state').allInnerTexts(), current: await p.locator('.stage[aria-current="step"] .stage__name').count() })],
  ['answer-today', { accounts: false }, '#patient-details', async (p) => {
    await openPanel(p); await p.getByRole('button', { name: /eGFR 40/ }).click();
    await p.locator('#thread .compare-btn').click();
    await p.locator('#out .decides').waitFor();
  }, async (p) => ({ h2: await text(p, '#out > h2'), last: (await p.locator('#out > *').last().innerText()).trim(), excluded: await p.locator('#out .opt--excluded').count() })],
  ['25-guide', { accounts: false }, '#guide', async (p) => { await p.locator('#g-advantages').waitFor(); },
    async (p) => ({ sections: await p.locator('#view-guide section.card').count(), methods: await text(p, '#g-methods > summary') })],
  ['26-about', { accounts: false }, '#about', async (p) => { await p.getByText('Pratham Pawar').waitFor(); },
    async (p) => ({ people: await p.locator('#view-about .person').count(), versions: await p.locator('#versions').innerText() })],
];

(async () => {
  const [url, out] = process.argv.slice(2);
  const b = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const report = { screens: {}, errors: [] };
  for (const [name, opts, hash, act, facts] of SCREENS) {
    for (const [size, viewport] of [['desktop', { width: 1280, height: 860 }], ['phone', { width: 390, height: 844 }]]) {
      const ctx = await context(b, viewport, opts);
      const p = await ctx.newPage();
      p.setDefaultTimeout(15000);
      p.on('pageerror', (e) => report.errors.push(`${name}/${size}: ${e.message}`));
      if (opts.clock) await p.clock.install({ time: NOW });
      await p.goto(url + hash);
      if (opts.clock) { await p.clock.pauseAt(NOW + 60000); await p.clock.runFor(1000); } // time moves only when the test says so
      try {
        await act(p);
        await p.waitForTimeout(150);
        const base = `${out}/${name}-${size}`;
        await p.screenshot({ path: base + '.png' });
        fs.writeFileSync(base + '.html', await snapshot(p));
        report.screens[`${name}/${size}`] = { png: base + '.png', html: base + '.html', facts: await facts(p),
          overflow: await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1) };
      } catch (e) {
        report.errors.push(`${name}/${size}: ${e.message.split('\n')[0]}`);
      }
      await ctx.close();
    }
  }
  console.log(JSON.stringify(report));
  await b.close();
})();
