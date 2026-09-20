import { Composer } from '@/components/chat/Composer'
import { Thread } from '@/components/chat/Thread'
import { TopBar } from '@/components/chat/TopBar'
import { PatientPanel } from '@/features/patient/PatientPanel'
import {
  EMPTY_PANEL,
  EXAMPLE_PANEL,
  panelProblems,
  toPatientPart,
  type PanelValues,
} from '@/features/patient/panelValues'
import { useChat } from '@/hooks/useChat'
import { useState } from 'react'

type Props = { userName?: string; onSignOut?: () => void }

/** The chat screen: patient panel beside the conversation (design/chat.html, design/v1/13-16). */
export function ChatPage({ userName, onSignOut }: Props = {}) {
  // It starts with the design's example patient, clearly badged as example data.
  const [panel, setPanel] = useState<PanelValues>(EXAMPLE_PANEL)
  const [isExample, setIsExample] = useState(true)

  // Only plausible values are sent: a value the browser flagged is left out, and the
  // server checks everything again anyway. `send` is rebuilt on every render, so this
  // closure always sees the panel as it is now.
  const chat = useChat(() => {
    const values = { ...panel }
    for (const field of Object.keys(panelProblems(values)) as (keyof PanelValues)[]) {
      values[field] = '' as never
    }
    return toPatientPart(values)
  })

  function newPatient() {
    setPanel(EMPTY_PANEL)
    setIsExample(false)
    chat.clearConversation() // the next patient must not inherit these answers
  }

  return (
    <div className="flex h-dvh flex-col">
      <TopBar userName={userName} onSignOut={onSignOut} />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <PatientPanel
          values={panel}
          isExample={isExample}
          onChange={(values) => {
            setPanel(values)
            setIsExample(false) // the moment it is edited it is no longer the example
          }}
          onNewPatient={newPatient}
        />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <Thread turns={chat.turns} />
          <Composer onSend={chat.send} onType={chat.clearNotice} notice={chat.notice} waiting={chat.waiting} />
        </div>
      </div>
    </div>
  )
}
