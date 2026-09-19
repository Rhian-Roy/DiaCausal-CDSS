import { Composer } from '@/components/chat/Composer'
import { PatientStrip } from '@/components/chat/PatientStrip'
import { Thread } from '@/components/chat/Thread'
import { TopBar } from '@/components/chat/TopBar'
import { useChat } from '@/hooks/useChat'

/** The chat screen from design/chat.html: top bar, patient strip, conversation, message box. */
type Props = { userName?: string; onSignOut?: () => void }

export function ChatPage({ userName, onSignOut }: Props = {}) {
  const chat = useChat()
  return (
    <div className="flex h-dvh flex-col">
      <TopBar userName={userName} onSignOut={onSignOut} />
      <PatientStrip />
      <Thread turns={chat.turns} />
      <Composer onSend={chat.send} onType={chat.clearNotice} notice={chat.notice} waiting={chat.waiting} />
    </div>
  )
}
