import { authApi, type SessionInfo } from '@/features/auth/api'
import { CodePage } from '@/features/auth/CodePage'
import { IntendedUsePage } from '@/features/auth/IntendedUsePage'
import { MfaSetupPage } from '@/features/auth/MfaSetupPage'
import { SessionTimer } from '@/features/auth/SessionTimer'
import { SignInPage } from '@/features/auth/SignInPage'
import { setSessionEndedHandler } from '@/lib/authSession'
import { ChatPage } from '@/pages/ChatPage'
import { useCallback, useEffect, useState } from 'react'

/**
 * Which screen is showing. Sign-in order:
 *   sign in (ID + password + CAPTCHA) -> [first time: authenticator set-up] -> 6-digit code
 *   -> intended use (until acknowledged) -> chat
 * Leaving the chat (sign out, timeout) unmounts ChatPage, which clears the conversation.
 */
type Screen =
  | { name: 'loading' }
  | { name: 'signin'; notice?: string }
  | { name: 'code'; userId: string }
  | { name: 'mfa_setup' }
  | { name: 'acknowledge'; info: SessionInfo }
  | { name: 'chat'; info: SessionInfo }

const ENDED = 'Your session has ended. Please sign in again.'
const STEP_LOST =
  'That took too long, or your browser did not keep the sign-in. Please sign in again — ' +
  'if this keeps happening, use Google Chrome, or open the site over https (see docs/DEPLOY.md).'

export default function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'loading' })

  const signedIn = useCallback((info: SessionInfo) => {
    setScreen(info.needs_acknowledgement ? { name: 'acknowledge', info } : { name: 'chat', info })
  }, [])
  const backToSignIn = useCallback((notice?: string) => setScreen({ name: 'signin', notice }), [])
  const startAgain = useCallback((why?: string) => backToSignIn(why ?? STEP_LOST), [backToSignIn])

  useEffect(() => {
    // Already signed in (e.g. the page was reloaded)? The cookie decides; the page cannot read it.
    void authApi.me().then((result) => {
      if (result.ok && result.data.stage === 'full') signedIn(result.data)
      else backToSignIn()
    })
    setSessionEndedHandler(() => backToSignIn(ENDED))
    return () => setSessionEndedHandler(null)
  }, [signedIn, backToSignIn])

  const signOut = useCallback(
    async (reason: 'idle' | 'button') => {
      await authApi.logout()
      backToSignIn(reason === 'idle' ? 'You were signed out because the session was idle.' : 'You have signed out.')
    },
    [backToSignIn],
  )

  switch (screen.name) {
    case 'loading':
      return <p className="p-8 text-ink-muted">Loading…</p>
    case 'signin':
      return (
        <SignInPage
          notice={screen.notice}
          onSignedIn={(result) =>
            setScreen(result.next === 'mfa' ? { name: 'code', userId: result.user_id } : { name: 'mfa_setup' })
          }
        />
      )
    case 'code':
      return (
        <CodePage
          userId={screen.userId}
          onVerified={signedIn}
          onLocked={(message) => backToSignIn(message)}
          onStartAgain={startAgain}
        />
      )
    case 'mfa_setup':
      return <MfaSetupPage onVerified={signedIn} onLocked={(message) => backToSignIn(message)} onStartAgain={startAgain} />
    case 'acknowledge':
      return (
        <IntendedUsePage
          version={screen.info.intended_use_version}
          onAcknowledged={(info) => setScreen({ name: 'chat', info })}
          onSessionEnded={() => backToSignIn(ENDED)}
        />
      )
    case 'chat':
      return (
        <>
          <ChatPage userName={screen.info.display_name} onSignOut={() => void signOut('button')} />
          <SessionTimer
            idleSeconds={screen.info.idle_timeout_seconds}
            warningSeconds={screen.info.warning_seconds}
            onStay={() => void authApi.keepalive()}
            onSignOut={(reason) => void signOut(reason)}
          />
        </>
      )
  }
}
