import React, { useEffect, useState } from 'react'
import { Clock, AlertCircle } from 'lucide-react'

interface CountdownProps {
  initialSeconds?: number
  expiresAt?: string | Date
  onExpire?: () => void
  className?: string
}

export const Countdown: React.FC<CountdownProps> = ({
  initialSeconds = 600,
  expiresAt,
  onExpire,
  className = '',
}) => {
  const calculateRemaining = () => {
    if (expiresAt) {
      const target = new Date(expiresAt).getTime()
      const diff = Math.max(0, Math.floor((target - Date.now()) / 1000))
      return diff
    }
    return initialSeconds
  }

  const [secondsLeft, setSecondsLeft] = useState(calculateRemaining)

  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          onExpire?.()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [onExpire])

  const mins = Math.floor(secondsLeft / 60)
  const secs = secondsLeft % 60
  const formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`

  const isExpired = secondsLeft === 0

  if (isExpired) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-pill bg-block/15 border border-block/40 text-block text-[12px] font-mono font-semibold ${className}`}
      >
        <AlertCircle className="w-3.5 h-3.5 text-block" />
        <span>Expired</span>
      </span>
    )
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-pill bg-ask/15 border border-ask/40 text-ask text-[12px] font-mono font-semibold tracking-wide ${className}`}
    >
      <Clock className="w-3.5 h-3.5 text-ask animate-pulse" />
      <span>Expires in {formatted}</span>
    </span>
  )
}
