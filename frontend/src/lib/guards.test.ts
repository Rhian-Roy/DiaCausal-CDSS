import { describe, expect, it } from 'vitest'
import { countCharacters, findBlockedTerm, medicalUiGuard, uiGuard } from './guards'

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

  it('finds nothing while the list is empty', () => {
    expect(findBlockedTerm('any ordinary clinical question')).toBeNull()
  })
})

describe('medicalUiGuard', () => {
  it('is a stub that passes everything for now', () => {
    expect(medicalUiGuard('anything at all')).toEqual({ ok: true })
  })
})
