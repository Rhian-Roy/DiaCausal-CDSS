/**
 * The gap docs/TESTING.md part 3 admitted: the real page, in real Chrome, against the
 * real backend. Everything else runs in a simulated browser (jsdom) or without JavaScript.
 *
 * One sign-in is shared by the tests below (Playwright reuses the browser context in
 * file order), because signing in costs a CAPTCHA and a 6-digit code each time.
 */

import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import { newestCaptchaAnswer, PASSWORD, totp, USER_ID, WEB_URL } from '../helpers.js'

test.describe.configure({ mode: 'serial' })

let page // one browser page for the whole file
const consoleLines = []

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage()
  page.on('console', (message) => consoleLines.push(`${message.type()}|${message.text()}`))
})
test.afterAll(async () => page?.close())

/** The console lines printed since the last call, as plain text. */
function newLines() {
  const lines = consoleLines.splice(0, consoleLines.length)
  return lines.filter((line) => !line.includes('[vite]') && !line.includes('React DevTools'))
}

async function send(text) {
  // The app answers one question at a time on purpose ("Please wait for the current
  // answer"), so wait for the previous one to finish before sending the next.
  await expect(page.getByRole('button', { name: 'Send message' })).toBeEnabled()
  const box = page.getByLabel('Message DiaCausal')
  await box.fill(text)
  await box.press('Enter')
}

test('sign in with ID, password, CAPTCHA and a 6-digit code', async () => {
  await page.goto(WEB_URL())
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  await page.waitForSelector('img[alt^="CAPTCHA"]')

  await page.getByLabel('User ID').fill(USER_ID)
  await page.getByLabel('Password').fill(PASSWORD())
  await page.getByLabel('Type the 6 digits shown').fill(newestCaptchaAnswer())
  await page.getByRole('button', { name: 'Sign in' }).click()

  // First sign-in: set up the authenticator app, as a doctor would with their phone.
  await expect(page.getByRole('heading', { name: 'Set up your authenticator app' })).toBeVisible()
  await expect(page.locator('img[alt="QR code for your authenticator app"]')).toBeVisible()
  const key = (await page.getByLabel('Setup key').innerText()).replace(/\s/g, '')
  await page.getByLabel('Enter the 6-digit code to confirm').fill(totp(key))
  await page.getByRole('button', { name: 'Confirm and finish setup' }).click()

  await expect(page.getByRole('heading', { name: 'How to use DiaCausal' })).toBeVisible()
  await page.getByLabel('I understand').check()
  await page.getByRole('button', { name: 'Continue' }).click()
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()

  const printed = newLines().filter((line) => line.startsWith('log|'))
  expect(printed.map((line) => line.replace(/^log\|\[\w+\] /, ''))).toEqual([
    'login input passed', 'captcha passed', 'password passed', 'mfa passed',
  ])
  process.env.E2E_TOTP_KEY = key
})

test('a question prints exactly four console lines with one trace ID, and the reply appears', async () => {
  newLines()
  await send('HbA1c 8.4% on metformin 1 g twice daily, eGFR 62. What should I add?')

  await expect(page.getByText('Dummy reply from the DiaCausal backend.', { exact: false })).toBeVisible()
  const printed = newLines().filter((line) => line.startsWith('log|')).map((line) => line.slice(4))
  const traceId = /^\[([0-9a-f]{8})\] /.exec(printed[0])?.[1]
  expect(traceId, 'the first line starts with an 8-character trace ID').toBeTruthy()
  expect(printed).toEqual([
    `[${traceId}] input passed`,
    `[${traceId}] ui guard passed`,
    `[${traceId}] medical ui guard passed`,
    `[${traceId}] output passed`,
  ])

  // The same ID in the backend's own log, on the request, every stage and the reply.
  const log = fs.readFileSync(process.env.E2E_BACKEND_LOG, 'utf8')
  const tagged = log.split('\n').filter((line) => line.includes(`[${traceId}]`))
  for (const needed of ['chat request received', 'backend_guard:', 'clinical_guardrails:', 'causal_engine:',
                        'rag_retrieval:', 'llm_explanation:', 'output_guard:', 'reply sent']) {
    expect(tagged.join('\n'), `backend log line for ${needed}`).toContain(needed)
  }
  expect(log, 'the question itself is never logged').not.toContain('What should I add?')
})

test('an empty message is blocked in the browser and never sent', async () => {
  newLines()
  const before = fs.readFileSync(process.env.E2E_BACKEND_LOG, 'utf8').length
  await page.getByLabel('Message DiaCausal').press('Enter')

  await expect(page.getByText('Type a question first.')).toBeVisible()
  expect(newLines().some((line) => line.startsWith('warning|') && line.includes('ui guard blocked'))).toBe(true)
  expect(fs.readFileSync(process.env.E2E_BACKEND_LOG, 'utf8').length).toBe(before) // nothing reached the server
})

test('an Aadhaar-like number shows notice 09 and is not shown back', async () => {
  await send('Patient Aadhaar 726018159082, HbA1c 8.4%')

  await expect(page.getByText('Identifier removed — not sent')).toBeVisible()
  await expect(page.getByText('Patient Aadhaar [removed], HbA1c 8.4%')).toBeVisible()
  expect(await page.locator('body').innerText()).not.toContain('726018159082')
})

test('a type 1 question shows notice 10 and names the reason', async () => {
  await send('Type 1 diabetes patient, 24 years old, HbA1c 9% — add an SGLT2 inhibitor?')

  await expect(page.getByText('Out of scope')).toBeVisible()
  await expect(page.getByText(/This question is about type 1 diabetes\./)).toBeVisible()
})

test('the conversation scrolls and stays on the newest answer', async () => {
  for (let i = 1; i <= 8; i++) {
    await send(`Question number ${i}: HbA1c 8.${i}% on metformin, what next?`)
    await expect(page.getByText(`Question number ${i}`, { exact: false })).toBeVisible()
  }
  await expect(page.getByRole('button', { name: 'Send message' })).toBeEnabled() // last answer is in

  const thread = page.locator('main')
  const { scrollTop, scrollHeight, clientHeight } = await thread.evaluate((element) => ({
    scrollTop: element.scrollTop, scrollHeight: element.scrollHeight, clientHeight: element.clientHeight,
  }))
  expect(scrollHeight, 'the conversation is taller than the window').toBeGreaterThan(clientHeight)
  expect(scrollTop + clientHeight).toBeGreaterThan(scrollHeight - 5) // scrolled to the bottom
})

test('the patient panel: example data, a bad value caught, "New patient" clears everything', async () => {
  const panel = page.getByRole('complementary', { name: 'Patient details' })
  await expect(panel.getByText('Example data')).toBeVisible()
  await expect(panel.getByLabel('HbA1c')).toHaveValue('8.4')
  await expect(panel.getByText('Category: Obese (≥25)')).toBeVisible() // Asian-Indian cut-offs

  await panel.getByLabel('HbA1c').fill('45')
  await expect(panel.getByRole('alert')).toContainText('expected 4.0–20.0 %')

  await panel.getByLabel('HbA1c').fill('8.4')
  await panel.getByRole('button', { name: 'New patient' }).click()
  await expect(panel.getByLabel('HbA1c')).toHaveValue('')
  await expect(panel.getByText('Not filled in')).toBeVisible()
  await expect(page.getByText('Question number 8', { exact: false })).toHaveCount(0) // conversation cleared
})

test('the microphone button is ready to use', async () => {
  // Voice is built (docs/prompts/11-voice.md), so the button is enabled and labelled for
  // dictation. Recording itself needs a real microphone, so it is not clicked here.
  const mic = page.getByRole('button', { name: 'Dictate message' })
  await expect(mic).toBeVisible()
  await expect(mic).toBeEnabled()
})

test('the phone layout works at 390x844', async () => {
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByLabel('Message DiaCausal')).toHaveAttribute('placeholder', 'Ask a question')
  await expect(page.getByRole('button', { name: 'Send message' })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow, 'nothing sticks out sideways on a phone').toBeLessThanOrEqual(0)
  await page.setViewportSize({ width: 1280, height: 900 })
})

test('signing out clears the conversation, and the old session is dead', async () => {
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  expect(await page.locator('body').innerText()).not.toContain('Question number 8')

  // Signing in again goes straight to the 6-digit code (the app is already set up).
  await page.waitForSelector('img[alt^="CAPTCHA"]')
  await page.getByLabel('User ID').fill(USER_ID)
  await page.getByLabel('Password').fill(PASSWORD())
  await page.getByLabel('Type the 6 digits shown').fill(newestCaptchaAnswer())
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Enter your 6-digit code' })).toBeVisible()
  await page.getByLabel('6-digit code', { exact: true }).fill(totp(process.env.E2E_TOTP_KEY, 1))
  await page.getByRole('button', { name: 'Verify and continue' }).click()
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
})
