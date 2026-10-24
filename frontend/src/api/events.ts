import { create } from 'zustand'
import { API_BASE_URL, ApiError, refreshSession } from './client'

export type EventsStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'offline'

export const useEventsStore = create<{ revision: number; status: EventsStatus; invalidate: () => void; setStatus: (status: EventsStatus) => void }>()((set) => ({
  revision: 0,
  status: 'idle',
  invalidate: () => set((state) => ({ revision: state.revision + 1 })),
  setStatus: (status) => set((state) => state.status === status ? state : { status }),
}))

export function subscribeToEvents(): () => void {
  let source: EventSource | undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  let disposed = false
  let version: string | undefined
  const { setStatus } = useEventsStore.getState()

  function changed(event: MessageEvent) {
    if (disposed) return
    setStatus('connected')
    version = event.lastEventId
    useEventsStore.getState().invalidate()
  }

  function connect() {
    if (disposed) return
    setStatus('connecting')
    source = new EventSource(`${API_BASE_URL}/events`, { withCredentials: true })
    source.onopen = () => { if (!disposed) setStatus('connected') }
    source.addEventListener('recalculated', changed)
    source.addEventListener('ready', (event) => {
      if (disposed) return
      setStatus('connected')
      // Refetch on the first ready as well: a recalculation may have happened after GET.
      if (version !== event.lastEventId) changed(event)
      version = event.lastEventId
    })
    source.onerror = () => {
      if (disposed) return
      setStatus('reconnecting')
      if (source?.readyState !== EventSource.CLOSED) return
      source.close()
      void refreshSession().then(connect).catch((error: unknown) => {
        if (disposed) return
        if (error instanceof ApiError && error.status === 401) {
          window.dispatchEvent(new Event('session-expired'))
        } else {
          setStatus('offline')
          timer = setTimeout(connect, 10_000)
        }
      })
    }
  }

  connect()
  return () => {
    disposed = true
    clearTimeout(timer)
    source?.close()
    setStatus('idle')
  }
}
