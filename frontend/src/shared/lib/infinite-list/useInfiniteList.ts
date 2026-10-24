import { useMemo, useState } from 'react'

const DEFAULT_PAGE_SIZE = 10

interface UseInfiniteListResult<T> {
  visibleItems: T[]
  hasMore: boolean
  loadMore: () => void
}

// Отдаёт элементы порциями по pageSize, а не всё сразу — используется с
// InfiniteScrollSentinel, который подгружает следующую порцию при подскролле.
// items должен быть стабильной ссылкой (useMemo) — иначе счётчик будет
// сбрасываться на каждый ре-рендер.
export function useInfiniteList<T>(items: T[], pageSize = DEFAULT_PAGE_SIZE): UseInfiniteListResult<T> {
  const [visibleCount, setVisibleCount] = useState(pageSize)
  const [prevItems, setPrevItems] = useState(items)

  if (items !== prevItems) {
    setPrevItems(items)
    setVisibleCount(pageSize)
  }

  const visibleItems = useMemo(() => items.slice(0, visibleCount), [items, visibleCount])

  return {
    visibleItems,
    hasMore: visibleCount < items.length,
    loadMore: () => setVisibleCount((count) => Math.min(count + pageSize, items.length)),
  }
}
