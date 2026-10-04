/** Small helpers shared by the end-to-end tests: TOTP codes and the CAPTCHA answer. */

import crypto from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'

/** The 6-digit code an authenticator app would show for `secret` (RFC 6238). */
export function totp(secretBase32, stepOffset = 0) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  let bits = ''
  for (const character of secretBase32) bits += alphabet.indexOf(character).toString(2).padStart(5, '0')
  const key = Buffer.from(bits.match(/.{8}/g).map((byte) => parseInt(byte, 2)))
  const counter = Buffer.alloc(8)
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 1000 / 30) + stepOffset))
  const digest = crypto.createHmac('sha1', key).update(counter).digest()
  const offset = digest[digest.length - 1] & 0x0f
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, '0')
}

/**
 * The answer to the newest CAPTCHA, read straight from the server's own database.
 * Only something with access to the server can do this — which is the point: a bot on
 * the network cannot, so this is a test shortcut, not a way in.
 */
export function newestCaptchaAnswer() {
  const db = new DatabaseSync(process.env.E2E_DB_FILE, { readOnly: true })
  const row = db.prepare('SELECT answer FROM captcha_challenges ORDER BY created_at DESC LIMIT 1').get()
  db.close()
  if (!row) throw new Error('no CAPTCHA in the database — did the page ask for one?')
  return row.answer
}

export const WEB_URL = () => process.env.E2E_WEB_URL
export const USER_ID = 'e2e.admin'
export const PASSWORD = () => process.env.E2E_PASSWORD
