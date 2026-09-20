import { describe, expect, it } from 'vitest'
import examples from '../../../shared/guard_rules/examples.v1.json'
import agreement from '../test/guardAgreement.json'
import {
  checkRules,
  countCharacters,
  findBlockedTerm,
  medicalUiGuard,
  redactIdentifiers,
  RULES_VERSION,
  uiGuard,
  words,
} from './guards'

describe('uiGuard', () => {
  it.each(['', '   ', '\n\t '])('blocks an empty message (%j)', (text) => {
    expect(uiGuard(text)).toEqual({ ok: false, reason: 'Type a question first.' })
  })

  it('passes a normal question', () => {
    expect(uiGuard('What should I add to metformin?')).toEqual({ ok: true })
  })

  it('passes exactly 8000 characters and blocks 8001', () => {
    expect(uiGuard('a'.repeat(8000)).ok).toBe(true)
    expect(uiGuard('a'.repeat(8001))).toEqual({
      ok: false,
      reason: 'Your message is 8,001 characters; the limit is 8,000.',
    })
  })

  it('blocks a blocked word', () => {
    const result = uiGuard('you rudeword', new Set(['rudeword']))
    expect(result.ok).toBe(false)
  })
})

describe('countCharacters', () => {
  it('counts an emoji as one character, like the Python backend', () => {
    expect('💊'.length).toBe(2) // JavaScript's own count: two UTF-16 units
    expect(countCharacters('💊')).toBe(1)
    expect(countCharacters('मेटफॉर्मिन')).toBe('मेटफॉर्मिन'.length)
  })

  it('lets 8000 emoji through, as the backend would', () => {
    expect(uiGuard('💊'.repeat(8000)).ok).toBe(true)
  })
})

describe('findBlockedTerm', () => {
  const terms = new Set(['ass'])

  it('matches whole words in any case', () => {
    expect(findBlockedTerm('you ASS.', terms)).toBe('ass')
  })

  it('does not match inside other words', () => {
    expect(findBlockedTerm('please assess renal function', terms)).toBeNull()
  })

  it('finds nothing in an ordinary clinical question', () => {
    expect(findBlockedTerm('any ordinary clinical question')).toBeNull()
  })

  it('uses the real list from rules.v1.json by default', () => {
    expect(findBlockedTerm('you ASS.')).not.toBeNull()
    expect(findBlockedTerm('please assess renal function')).toBeNull()
  })

  it('lets the medical allowlist win', () => {
    expect(findBlockedTerm('urine ketones positive', new Set(['urine']))).toBeNull()
  })
})

describe('medicalUiGuard', () => {
  it('passes an ordinary in-scope question', () => {
    expect(medicalUiGuard('HbA1c 8.4% on metformin, eGFR 62. Which add-on?')).toEqual({ ok: true })
  })

  it('blocks a patient identifier', () => {
    expect(medicalUiGuard('Mobile 9876543210, HbA1c 9%')).toMatchObject({ ok: false, code: 'identifier' })
  })

  it('blocks an emergency', () => {
    expect(medicalUiGuard('CBG 45 mg/dL, sweating')).toMatchObject({ ok: false, code: 'emergency' })
  })

  it('blocks an out-of-scope question and names the topic', () => {
    expect(medicalUiGuard('She is pregnant, 28 weeks')).toMatchObject({
      ok: false,
      code: 'out_of_scope',
      topic: 'pregnancy',
    })
  })

  it('lets a negation or history cue cancel scope and emergency matches', () => {
    expect(medicalUiGuard('Type 2 diabetes for 6 years, not pregnant, no prior DKA.')).toEqual({ ok: true })
    expect(medicalUiGuard('History of seizures as a child, now 52 with T2DM on metformin.')).toEqual({ ok: true })
  })
})

describe('uiGuard and medicalUiGuard never repeat the matched word', () => {
  it.each(['what bullshit answer is this', 'Mobile 9876543210, HbA1c 9%'])('%s', (text) => {
    const results = [uiGuard(text), medicalUiGuard(text)]
    expect(JSON.stringify(results)).not.toContain('bullshit')
    expect(JSON.stringify(results)).not.toContain('9876543210')
  })
})

describe('the shared rules (shared/guard_rules/)', () => {
  it('has all 47 example cases', () => {
    expect(examples.cases).toHaveLength(47)
    expect(RULES_VERSION).toBe(examples.version)
  })

  it.each(examples.cases.map((c) => [c.id, c.text, c.expect]))('example %s', (_id, text, expected) => {
    expect(checkRules(text)).toBe(expected)
  })

  it.each(agreement.cases.map((c) => [c.text, c.expect]))('agrees with the reference guard: %s', (text, expected) => {
    expect(checkRules(text)).toBe(expected)
  })

  it('keeps a Devanagari word whole', () => {
    expect(words('मधुमेह रोगी')).toEqual(['मधुमेह', 'रोगी'])
  })

  it('the two guards together give the same verdict as checkRules', () => {
    for (const { text, expect: expected } of examples.cases) {
      const ui = uiGuard(text)
      const medical = medicalUiGuard(text)
      const code = !ui.ok ? ui.code : !medical.ok ? medical.code : undefined
      const verdict: Record<string, string> = {
        language: 'block:language',
        identifier: 'block:identifier',
        emergency: 'emergency',
      }
      const got = code === 'out_of_scope' && !medical.ok ? `out_of_scope:${medical.topic}` : code ? verdict[code] : 'pass'
      expect(got, text).toBe(expected)
    }
  })
})

describe('redactIdentifiers', () => {
  it('replaces identifiers so the page never shows them back', () => {
    expect(redactIdentifiers('Aadhaar 726018159082, phone 9876543210, HbA1c 8.4%')).toBe(
      'Aadhaar [removed], phone [removed], HbA1c 8.4%',
    )
  })

  it('leaves a 12-digit number with a wrong check digit alone', () => {
    expect(redactIdentifiers('Lab accession 726018159083')).toBe('Lab accession 726018159083')
  })
})
