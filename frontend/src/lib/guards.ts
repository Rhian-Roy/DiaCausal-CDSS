/**
 * Browser-side guards, run before anything is sent. They give instant feedback;
 * the backend repeats every check (backend/app/pipeline/backend_guard.py) and has
 * the final say, because a request can reach the API without going through this page.
 *
 * All lists come from ONE file shared with the backend: shared/guard_rules/rules.v1.json.
 * Both sides are tested on every case in examples.v1.json and must give the same
 * answer as shared/guard_rules/reference_guard.py.
 *
 * Order (first match wins), as in the reference:
 *   identifier -> language -> emergency -> out of scope
 * uiGuard covers empty / too long / foul language; medicalUiGuard covers the rest.
 * The matched word is never shown or logged.
 */

import rules from '../../../shared/guard_rules/rules.v1.json'
import { MAX_TEXT_CHARS, type ReasonCode, type ScopeTopic } from './contract'

export const RULES_VERSION: string = rules.version

export type GuardResult =
  | { ok: true }
  | { ok: false; reason: string; code?: ReasonCode; topic?: ScopeTopic }

// ── text helpers ─────────────────────────────────────────────────────────────

// A word = letters + combining marks + digits, so Devanagari words stay whole
// ("मधुमेह" is one word). An apostrophe inside a word keeps it whole ("fournier's").
const WORD = /[\p{L}\p{M}\p{N}]+(?:'[\p{L}\p{M}\p{N}]+)*/gu

/** Python's NFKC + casefold(): upper-then-lower also folds "ß" to "ss", as casefold does. */
function fold(text: string): string {
  return text.normalize('NFKC').toUpperCase().toLowerCase()
}

export function words(text: string): string[] {
  return fold(text).match(WORD) ?? []
}

/** Length as Python counts it (one per character, emoji included), so the 8000 limit agrees. */
export function countCharacters(text: string): number {
  return Array.from(text).length
}

/**
 * The rules file holds Python regexes. Make JavaScript read them the same way:
 * Python's \d and \b understand every script, JavaScript's only ASCII.
 */
const W = '[\\p{L}\\p{M}\\p{N}_]'
export function pythonRegex(source: string, flags = ''): RegExp {
  const translated = source
    .replaceAll('\\d', '\\p{Nd}')
    .replaceAll('\\D', '\\P{Nd}')
    .replaceAll('\\b', `(?:(?<=${W})(?!${W})|(?<!${W})(?=${W}))`)
  return new RegExp(translated, `gu${flags}`)
}

/** Value of any Unicode decimal digit ("7", "७", "𝟕"): digits come in runs of ten, 0 to 9. */
function digitValue(ch: string): number {
  let value = 0
  let point = ch.codePointAt(0)!
  while (/\p{Nd}/u.test(String.fromCodePoint(point - 1))) {
    point -= 1
    value += 1
  }
  return value % 10
}

// Verhoeff check digit (Aadhaar's last digit): a 12-digit number that fails it is not an Aadhaar.
// prettier-ignore
const D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],
  [5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
// prettier-ignore
const P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],
  [4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]

export function verhoeffOk(digits: string[]): boolean {
  let check = 0
  digits.toReversed().forEach((ch, i) => {
    check = D[check][P[i % 8][digitValue(ch)]]
  })
  return check === 0
}

// ── the rules, loaded once ───────────────────────────────────────────────────

type IdentifierSpec = { regex: string; flags?: string; extra_check?: string }

const IDENTIFIERS = Object.values(rules.identifiers as Record<string, IdentifierSpec>).map((spec) => ({
  pattern: pythonRegex(spec.regex, spec.flags === 'i' ? 'i' : ''),
  verhoeff: spec.extra_check === 'verhoeff',
}))

export const BLOCKED_TERMS: ReadonlySet<string> = new Set(rules.profanity.blocked_words)
const BLOCKED_PHRASES: readonly string[] = rules.profanity.blocked_phrases
const MEDICAL_ALLOWLIST: ReadonlySet<string> = new Set(rules.medical_allowlist)
const CUES = [...rules.context_cues.negation, ...rules.context_cues.history]
const CUE_WINDOW = rules.context_cues.window_words
const EMERGENCY = rules.emergency
const GLUCOSE = pythonRegex(EMERGENCY.glucose_value_regex, 'i')
const [LOW_MGDL, HIGH_MGDL] = EMERGENCY.thresholds.map((t) => t.value_mg_dl)
const OUT_OF_SCOPE = Object.entries(rules.out_of_scope).filter(
  (entry): entry is [ScopeTopic, string[]] => entry[0] !== 'note',
)

/** Word index where each whole-word phrase match starts. */
function phrasePositions(phrases: readonly string[], text: string): number[] {
  const joined = ` ${words(text).join(' ')} `
  const positions: number[] = []
  for (const phrase of phrases) {
    const key = ` ${words(phrase).join(' ')} `
    for (let start = joined.indexOf(key); start !== -1; start = joined.indexOf(key, start + 1)) {
      positions.push(joined.slice(0, start).split(' ').filter(Boolean).length)
    }
  }
  return positions
}

/** Is there a negation or history cue in the few words before word `index`? */
function cued(text: string, index: number): boolean {
  const before = ` ${words(text).slice(Math.max(0, index - CUE_WINDOW), index).join(' ')} `
  return CUES.some((cue) => before.includes(` ${cue} `))
}

// ── the checks ───────────────────────────────────────────────────────────────

export function hasIdentifier(text: string): boolean {
  return IDENTIFIERS.some(({ pattern, verhoeff }) =>
    Array.from(text.matchAll(pattern)).some((m) => !verhoeff || verhoeffOk(m[0].match(/\p{Nd}/gu) ?? [])),
  )
}

/** Replace every identifier with "[removed]", so the page never shows it back. */
export function redactIdentifiers(text: string): string {
  return IDENTIFIERS.reduce(
    (out, { pattern, verhoeff }) =>
      out.replace(pattern, (m) => (!verhoeff || verhoeffOk(m.match(/\p{Nd}/gu) ?? []) ? '[removed]' : m)),
    text,
  )
}

/** The first blocked word or phrase, or null. Internal only: never show or log it. */
export function findBlockedTerm(text: string, terms: ReadonlySet<string> = BLOCKED_TERMS): string | null {
  for (const word of words(text)) {
    if (terms.has(word) && !MEDICAL_ALLOWLIST.has(word)) return word
  }
  return BLOCKED_PHRASES.find((phrase) => phrasePositions([phrase], text).length > 0) ?? null
}

export function isEmergency(text: string): boolean {
  if (phrasePositions(EMERGENCY.phrases, text).some((i) => !cued(text, i))) return true
  for (const m of text.matchAll(GLUCOSE)) {
    const value = Number(m[1])
    const unit = (m[2] ?? 'mg/dl').toLowerCase()
    const mgdl = unit.startsWith('mmol') ? value * EMERGENCY.mmol_to_mgdl : value
    if ((mgdl < LOW_MGDL || mgdl >= HIGH_MGDL) && !cued(text, words(text.slice(0, m.index)).length)) return true
  }
  return false
}

export function outOfScopeTopic(text: string): ScopeTopic | null {
  for (const [topic, phrases] of OUT_OF_SCOPE) {
    if (phrasePositions(phrases, text).some((i) => !cued(text, i))) return topic
  }
  return null
}

/** The verdict in the words of examples.v1.json (the same as reference_guard.py). */
export function checkRules(text: string): string {
  if (hasIdentifier(text)) return 'block:identifier'
  if (findBlockedTerm(text)) return 'block:language'
  if (isEmergency(text)) return 'emergency'
  const topic = outOfScopeTopic(text)
  return topic ? `out_of_scope:${topic}` : 'pass'
}

// ── the two guards the chat flow runs ────────────────────────────────────────

export const TOPIC_NAMES: Record<ScopeTopic, string> = {
  type_1: 'type 1 diabetes',
  pregnancy: 'pregnancy',
  under_18: 'a patient under 18',
  dka_hhs: 'ketoacidosis or a hyperosmolar state',
  insulin_start: 'starting insulin',
}

/** UI guard: not empty, not too long, no foul language. */
export function uiGuard(text: string, terms: ReadonlySet<string> = BLOCKED_TERMS): GuardResult {
  if (text.trim() === '') {
    return { ok: false, reason: 'Type a question first.' }
  }
  const length = countCharacters(text)
  if (length > MAX_TEXT_CHARS) {
    return {
      ok: false,
      reason: `Your message is ${length.toLocaleString('en-US')} characters; the limit is ${MAX_TEXT_CHARS.toLocaleString('en-US')}.`,
    }
  }
  // An identifier outranks foul language (as in the reference): leave it to medicalUiGuard.
  if (!hasIdentifier(text) && findBlockedTerm(text, terms)) {
    return { ok: false, reason: 'Please rephrase: the message contains language that is not allowed.', code: 'language' }
  }
  return { ok: true }
}

/** Medical UI guard: no patient identifiers, not an emergency, inside DiaCausal's scope. */
export function medicalUiGuard(text: string): GuardResult {
  if (hasIdentifier(text)) {
    return {
      ok: false,
      reason: 'Please remove patient identifiers (Aadhaar, phone, PAN, email) and ask again.',
      code: 'identifier',
    }
  }
  if (isEmergency(text)) {
    return { ok: false, reason: 'This may be an emergency. Follow your emergency protocol.', code: 'emergency' }
  }
  const topic = outOfScopeTopic(text)
  if (topic) {
    return { ok: false, reason: `Out of scope: this question is about ${TOPIC_NAMES[topic]}.`, code: 'out_of_scope', topic }
  }
  return { ok: true }
}
