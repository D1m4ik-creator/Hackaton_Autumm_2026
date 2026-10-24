import { useCallback, useMemo, useState } from 'react'

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
//
// resetKey отдельно от items: по умолчанию равен items, но вызывающий код
// может передать более узкий ключ (например, только фильтр без сортировки),
// чтобы пересортировка того же набора не сбрасывала уже подгруженные строки
// обратно на первую страницу — сбрасываться должна только смена состава
// списка, а не его порядка.
export function useInfiniteList<T>(items: T[], pageSize = DEFAULT_PAGE_SIZE, resetKey: unknown = items): UseInfiniteListResult<T> {
  const [visibleCount, setVisibleCount] = useState(pageSize)
  const [prevResetKey, setPrevResetKey] = useState(resetKey)

  if (resetKey !== prevResetKey) {
    setPrevResetKey(resetKey)
    setVisibleCount(pageSize)
  }

  const visibleItems = useMemo(() => items.slice(0, visibleCount), [items, visibleCount])

  // Стабильная ссылка — InfiniteScrollSentinel держит её в зависимостях
  // своего IntersectionObserver-эффекта; без useCallback здесь обсёрвер
  // пересоздавался бы на каждый ре-рендер родителя.
  const loadMore = useCallback(
    () => setVisibleCount((count) => Math.min(count + pageSize, items.length)),
    [pageSize, items.length],
  )

  return {
    visibleItems,
    hasMore: visibleCount < items.length,
    loadMore,
  }
}
