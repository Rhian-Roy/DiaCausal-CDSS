import { describe, expect, it, vi } from 'vitest'
import { newTraceId, traceLogger } from './trace'

describe('newTraceId', () => {
  it('is 8 lowercase hex characters', () => {
    expect(newTraceId()).toMatch(/^[0-9a-f]{8}$/)
  })

  it('is different every time', () => {
    const ids = new Set(Array.from({ length: 1000 }, newTraceId))
    expect(ids.size).toBe(1000)
  })
})

describe('traceLogger', () => {
  it('starts every line with [traceId]', () => {
    const sink = { log: vi.fn(), warn: vi.fn(), error: vi.fn() }
    const log = traceLogger('a1b2c3d4', sink)

    log.info('input passed')
    log.warn('ui guard blocked: empty')
    log.error('request failed')

    expect(sink.log).toHaveBeenCalledWith('[a1b2c3d4] input passed')
    expect(sink.warn).toHaveBeenCalledWith('[a1b2c3d4] ui guard blocked: empty')
    expect(sink.error).toHaveBeenCalledWith('[a1b2c3d4] request failed')
  })
})
