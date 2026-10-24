import { useCallback, useEffect, useState } from 'react'
import { useEventsStore } from './events'

export function useApiResource<T>(loader: () => Promise<T>) {
  const revision = useEventsStore((state) => state.revision)
  const [retry, setRetry] = useState(0)
  const [state, setState] = useState<{ loader?: () => Promise<T>; revision: number; retry: number; data?: T; error: string | null }>({ revision: -1, retry: -1, error: null })

  useEffect(() => {
    let active = true
    void loader().then(
      (data) => { if (active) setState({ loader, revision, retry, data, error: null }) },
      (error: unknown) => {
        if (active) setState((previous) => ({ loader, revision, retry, data: previous.loader === loader ? previous.data : undefined, error: error instanceof Error ? error.message : 'Не удалось загрузить данные' }))
      },
    )
    return () => { active = false }
  }, [loader, revision, retry])

  const reload = useCallback(() => setRetry((value) => value + 1), [])
  const setData = (data: T) => setState({ loader, revision, retry, data, error: null })
  const current = state.loader === loader && state.revision === revision && state.retry === retry
  return { data: state.loader === loader ? state.data : undefined, loading: !current, error: current ? state.error : null, reload, setData }
}
