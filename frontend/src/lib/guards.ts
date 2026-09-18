/**
 * Browser-side guards, run before anything is sent. They give instant feedback
 * only: the backend repeats the checks that matter (backend/app/pipeline/),
 * because a request can reach the API without going through this page.
 */

import { MAX_TEXT_CHARS } from './contract'

export type GuardResult = { ok: true } | { ok: false; reason: string }

/**
 * Words that must not be sent (the "foul language" list). Empty until the agreed
 * list is supplied; add lowercase single words. The backend's copy is
 * backend/app/pipeline/blocklist.py.
 */
export const BLOCKED_TERMS: ReadonlySet<string> = new Set<string>([])

const WORD = /[\p{L}\p{N}]+(?:'[\p{L}\p{N}]+)*/gu

/** Length as Python counts it (one per character, emoji included), so the 8000 limit agrees. */
export function countCharacters(text: string): number {
  return Array.from(text).length
}

export function findBlockedTerm(text: string, terms: ReadonlySet<string> = BLOCKED_TERMS): string | null {
  for (const word of text.toLowerCase().match(WORD) ?? []) {
    if (terms.has(word)) return word
  }
  return null
}

/** UI guard: not empty, not too long, no blocked words. */
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
  if (findBlockedTerm(text, terms)) {
    return { ok: false, reason: 'Please rephrase: the message contains language that is not allowed.' }
  }
  return { ok: true }
}

/**
 * Medical UI guard — a stub that lets everything through for now.
 * Planned checks, each to run before sending:
 *  - patient identifiers typed into the box (names, phone or Aadhaar numbers)
 *  - emergencies ("unconscious", "chest pain now") -> tell the user to call for help instead
 *  - questions outside scope (second-line therapy for adults already on metformin)
 */
export function medicalUiGuard(_text: string): GuardResult {
  return { ok: true }
}
