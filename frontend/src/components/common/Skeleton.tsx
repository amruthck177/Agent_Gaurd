import React from 'react'

interface SkeletonProps {
  className?: string
}

export const Skeleton: React.FC<SkeletonProps> = ({ className = 'h-4 w-full' }) => {
  return (
    <div
      className={`animate-pulse rounded bg-surface2/70 border border-line/40 ${className}`}
    />
  )
}

export const SkeletonTableRow: React.FC = () => {
  return (
    <tr className="h-[52px] border-b border-line/40">
      <td className="py-2.5 px-4"><Skeleton className="h-4 w-16" /></td>
      <td className="py-2.5 px-3"><Skeleton className="h-6 w-20 rounded-pill" /></td>
      <td className="py-2.5 px-3"><Skeleton className="h-4 w-24" /></td>
      <td className="py-2.5 px-4"><Skeleton className="h-4 w-28" /></td>
      <td className="py-2.5 px-4"><Skeleton className="h-4 w-24" /></td>
      <td className="py-2.5 px-4"><Skeleton className="h-4 w-16" /></td>
      <td className="py-2.5 px-4"><Skeleton className="h-4 w-40" /></td>
    </tr>
  )
}

export const SkeletonStatCard: React.FC = () => {
  return (
    <div className="rounded-card border border-line bg-surface p-5 space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-20" />
      <Skeleton className="h-6 w-full" />
    </div>
  )
}
