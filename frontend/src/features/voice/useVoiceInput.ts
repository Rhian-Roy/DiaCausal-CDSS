/**
 * The mic button: press to record (the browser asks for microphone permission only
 * now), press again to stop, or it stops by itself after 30 seconds. The clip goes to
 * the backend; the text comes back and is handed to `onTranscript` — it is put INTO the
 * message box and never sent by itself. Console lines carry the recording's trace ID.
 */

import { newTraceId, traceLogger } from '@/lib/trace'
import { useEffect, useRef, useState } from 'react'
import { postTranscribe } from './api'

export const MAX_SECONDS = 30

export type VoiceState =
  | { kind: 'idle' }
  | { kind: 'recording'; seconds: number }
  | { kind: 'transcribing' }
  | { kind: 'error'; message: string }

export function voiceSupported(): boolean {
  return typeof window !== 'undefined' && 'MediaRecorder' in window && Boolean(navigator.mediaDevices?.getUserMedia)
}

export function useVoiceInput(onTranscript: (text: string) => void) {
  const [state, setState] = useState<VoiceState>({ kind: 'idle' })
  const recorder = useRef<MediaRecorder | null>(null)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)
  const deliver = useRef(onTranscript)
  useEffect(() => {
    deliver.current = onTranscript
  }, [onTranscript])

  useEffect(
    () => () => {
      // Leaving the page (sign out, timeout): stop recording and let go of the microphone.
      if (timer.current) clearInterval(timer.current)
      if (recorder.current?.state === 'recording') recorder.current.stop()
    },
    [],
  )

  async function start() {
    if (!voiceSupported()) {
      setState({ kind: 'error', message: 'This browser cannot record audio. Type the question instead.' })
      return
    }
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setState({ kind: 'error', message: 'The microphone is blocked. Allow it in the browser’s address bar, then try again.' })
      return
    }

    const traceId = newTraceId()
    const log = traceLogger(traceId)
    const chunks: Blob[] = []
    const started = Date.now()
    const media = new MediaRecorder(stream)
    recorder.current = media
    media.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data)
    }
    media.onstop = async () => {
      if (timer.current) clearInterval(timer.current)
      stream.getTracks().forEach((track) => track.stop()) // the browser's red "recording" dot goes off
      const seconds = Math.round((Date.now() - started) / 100) / 10
      log.info(`voice: ${seconds} s recorded`)
      setState({ kind: 'transcribing' })
      const result = await postTranscribe(new Blob(chunks, { type: media.mimeType || 'audio/webm' }), traceId)
      if (!result.ok) {
        log.warn(`voice: speech-to-text failed: ${result.message}`)
        setState({ kind: 'error', message: result.message })
        return
      }
      if (!result.transcript.trim()) {
        setState({ kind: 'error', message: 'No speech was heard. Try again, a little closer to the microphone.' })
        return
      }
      log.info('voice: transcript put in the message box (not sent)')
      setState({ kind: 'idle' })
      deliver.current(result.transcript)
    }

    media.start()
    setState({ kind: 'recording', seconds: 0 })
    timer.current = setInterval(() => {
      const seconds = Math.floor((Date.now() - started) / 1000)
      if (seconds >= MAX_SECONDS) stop()
      else setState({ kind: 'recording', seconds })
    }, 250)
  }

  function stop() {
    if (timer.current) clearInterval(timer.current)
    if (recorder.current?.state === 'recording') recorder.current.stop()
  }

  return {
    state,
    toggle: () => (state.kind === 'recording' ? stop() : void start()),
    dismiss: () => setState({ kind: 'idle' }),
  }
}
