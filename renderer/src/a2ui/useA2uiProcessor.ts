import type { ReactComponentImplementation } from '@a2ui/react/v0_9'
import { MessageProcessor } from '@a2ui/web_core/v0_9'
import type { A2uiClientAction, A2uiMessage, SurfaceModel } from '@a2ui/web_core/v0_9'
import { useCallback, useEffect, useState } from 'react'
import { shadcnCatalog } from '@/a2ui/catalog'

export function useA2uiProcessor() {
  const [lastAction, setLastAction] = useState<A2uiClientAction | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [processor] = useState(
    () =>
      new MessageProcessor<ReactComponentImplementation>([shadcnCatalog], (action) => {
        setLastAction(action)
      }, { version: 'v0.9.1' }),
  )
  const [surfaces, setSurfaces] = useState<SurfaceModel<ReactComponentImplementation>[]>([])

  const syncSurfaces = useCallback(() => {
    setSurfaces(Array.from(processor.model.surfacesMap.values()))
  }, [processor])

  useEffect(() => {
    const created = processor.onSurfaceCreated(syncSurfaces)
    const deleted = processor.onSurfaceDeleted(syncSurfaces)
    return () => {
      created.unsubscribe()
      deleted.unsubscribe()
    }
  }, [processor, syncSurfaces])

  const loadMessages = useCallback(
    (messages: A2uiMessage[]) => {
      setError(null)
      try {
        for (const surface of Array.from(processor.model.surfacesMap.values())) {
          processor.processMessages([
            { version: 'v0.9.1', deleteSurface: { surfaceId: surface.id } },
          ])
        }
        processor.processMessages(messages)
        syncSurfaces()
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : 'Failed to process A2UI messages')
      }
    },
    [processor, syncSurfaces],
  )

  return { processor, surfaces, lastAction, error, loadMessages, setError }
}
