import { useState } from 'react'

export function LetterZ({ className }: { className?: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return null
  return <img className={className} src="/z.0b5983b8.svg" alt="" onError={() => setFailed(true)} />
}
