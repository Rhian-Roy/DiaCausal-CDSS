/**
 * Trace IDs: one short random ID per message. Every console line about that
 * message starts with it, it is sent to the backend as `client_trace_id`, and
 * the backend prints it on every log line. One ID follows the message end to end.
 */

/** 8 random hex characters, e.g. "a1b2c3d4". */
export function newTraceId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(4))
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

export type TraceLogger = {
  info: (message: string) => void
  warn: (message: string) => void
  error: (message: string) => void
}

type ConsoleLike = Pick<Console, 'log' | 'warn' | 'error'>

/** Console logger that starts every line with `[traceId]`. */
export function traceLogger(traceId: string, sink: ConsoleLike = console): TraceLogger {
  const prefix = `[${traceId}]`
  return {
    info: (message) => sink.log(`${prefix} ${message}`),
    warn: (message) => sink.warn(`${prefix} ${message}`),
    error: (message) => sink.error(`${prefix} ${message}`),
  }
}
