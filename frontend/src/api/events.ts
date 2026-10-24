import { create } from 'zustand'
import { API_BASE_URL, ApiError, refreshSession } from './client'

export const useEventsStore = create<{ revision: number; invalidate: () => void }>()((set) => ({
  revision: 0,
  invalidate: () => set((state) => ({ revision: state.revision + 1 })),
}))

export function subscribeToEvents(): () => void {
  let source: EventSource | undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  let disposed = false
  let version: string | undefined

  function changed(event: MessageEvent) {
    version = event.lastEventId
    useEventsStore.getState().invalidate()
  }

  function connect() {
    if (disposed) return
    source = new EventSource(`${API_BASE_URL}/events`, { withCredentials: true })
    source.addEventListener('recalculated', changed)
    source.addEventListener('ready', (event) => {
      // Refetch on the first ready as well: a recalculation may have happened after GET.
      if (version !== event.lastEventId) changed(event)
      version = event.lastEventId
    })
    source.onerror = () => {
      if (disposed || source?.readyState !== EventSource.CLOSED) return
      source.close()
      void refreshSession().then(connect).catch((error: unknown) => {
        if (disposed) return
        if (error instanceof ApiError && error.status === 401) {
          window.dispatchEvent(new Event('session-expired'))
        } else {
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
  }
}
