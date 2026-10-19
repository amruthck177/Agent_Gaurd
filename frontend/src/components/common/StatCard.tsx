import React from 'react'

interface StatCardProps {
  label: string
  value: number | string
  subtext?: string
  trend?: 'up' | 'down' | 'neutral'
  sparklinePoints?: number[]
  sparklineColor?: string
  icon?: React.ReactNode
  variant?: 'default' | 'allow' | 'ask' | 'block'
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  subtext,
  sparklinePoints,
  sparklineColor = '#C8963E',
  icon,
  variant = 'default',
}) => {
  const borderVariants = {
    default: 'hover:border-ink2/50',
    allow: 'hover:border-allow/50',
    ask: 'hover:border-ask/50',
    block: 'hover:border-block/50',
  }

  // Generate SVG path if sparkline points exist
  let sparklinePath = ''
  let sparklineAreaPath = ''
  if (sparklinePoints && sparklinePoints.length > 1) {
    const min = Math.min(...sparklinePoints)
    const max = Math.max(...sparklinePoints)
    const range = max - min || 1
    const width = 100
    const height = 24

    const coords = sparklinePoints.map((pt, idx) => {
      const x = (idx / (sparklinePoints.length - 1)) * width
      const y = height - ((pt - min) / range) * (height - 6) - 3
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })

    sparklinePath = `M${coords.join(' L')}`
    sparklineAreaPath = `${sparklinePath} L100,24 L0,24 Z`
  }

  return (
    <div
      className={`rounded-card border border-line bg-surface p-4 sm:p-5 flex flex-col justify-between transition-colors shadow-sm ${borderVariants[variant]}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[13px] font-medium text-ink2">{label}</span>
        {icon && <div className="text-ink2">{icon}</div>}
      </div>

      <div className="flex items-baseline justify-between mb-2">
        <span className="text-[30px] sm:text-[32px] font-bold text-ink tabular-nums tracking-tight leading-none">
          {value}
        </span>
        {subtext && <span className="text-[11px] font-mono text-ink2 truncate ml-2">{subtext}</span>}
      </div>

      {sparklinePath && (
        <div className="h-7 w-full pt-1">
          <svg className="w-full h-full" viewBox="0 0 100 24" preserveAspectRatio="none">
            <defs>
              <linearGradient id={`grad-${label.replace(/\s+/g, '')}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={sparklineColor} stopOpacity="0.25" />
                <stop offset="100%" stopColor={sparklineColor} stopOpacity="0.0" />
              </linearGradient>
            </defs>
            <path
              d={sparklineAreaPath}
              fill={`url(#grad-${label.replace(/\s+/g, '')})`}
            />
            <path
              d={sparklinePath}
              fill="none"
              stroke={sparklineColor}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      )}
    </div>
  )
}
