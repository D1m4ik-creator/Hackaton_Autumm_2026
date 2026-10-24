import { useState } from 'react'

export function LetterE({ className }: { className?: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return null
  return <img className={className} src="/e.14a68307.svg" alt="" onError={() => setFailed(true)} />
}
