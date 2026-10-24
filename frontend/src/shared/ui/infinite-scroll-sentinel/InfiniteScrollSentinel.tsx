import { useEffect, useRef } from 'react'
import { Spin } from 'antd'
import './infinite-scroll-sentinel.css'

interface InfiniteScrollSentinelProps {
  hasMore: boolean
  onIntersect: () => void
}

// Невидимый маркер в конце списка: как только он попадает во вьюпорт
// (или в скролл-контейнер родителя), подгружает следующую порцию.
export function InfiniteScrollSentinel({ hasMore, onIntersect }: InfiniteScrollSentinelProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!hasMore) return
    const node = ref.current
    if (!node) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) onIntersect()
      },
      { rootMargin: '200px' },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [hasMore, onIntersect])

  if (!hasMore) return null

  return (
    <div ref={ref} className="infinite-scroll-sentinel" role="status" aria-live="polite" aria-label="Загрузка следующих записей">
      <Spin size="small" />
    </div>
  )
}
