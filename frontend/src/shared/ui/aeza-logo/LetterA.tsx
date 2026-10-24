import { useState } from 'react'

export function LetterA({ className }: { className?: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return null
  return <img className={className} src="/a.9a01553c.svg" alt="" onError={() => setFailed(true)} />
}
