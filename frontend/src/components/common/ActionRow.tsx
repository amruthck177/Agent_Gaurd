import React from 'react'
import { DecisionChip, DecisionType } from './DecisionChip'

export interface ActionItem {
  id: string | number
  time: string
  agent: string
  tool: string
  target?: string
  amount?: string | number
  decision: DecisionType
  reason: string
  latencyMs?: number
  sequence?: number | string
}

interface ActionRowProps {
  item: ActionItem
  isSelected?: boolean
  onClick?: (item: ActionItem) => void
}

export const ActionRow: React.FC<ActionRowProps> = ({
  item,
  isSelected = false,
  onClick,
}) => {
  const leftBorderClasses: Record<DecisionType, string> = {
    ALLOW: 'border-l-2 border-l-transparent',
    'ASK HUMAN': 'border-l-2 border-l-ask',
    ASK_HUMAN: 'border-l-2 border-l-ask',
    BLOCK: 'border-l-2 border-l-block',
  }

  const bgHighlight = isSelected
    ? 'bg-surface2 border-line'
    : 'hover:bg-surface2/60'

  return (
    <tr
      onClick={() => onClick?.(item)}
      className={`h-[52px] cursor-pointer transition-colors border-b border-line/60 ${leftBorderClasses[item.decision]} ${bgHighlight}`}
    >
      <td className="py-2.5 px-3 sm:px-4 font-mono text-[13px] text-ink2 whitespace-nowrap">
        {item.time}
      </td>
      <td className="py-2.5 px-2.5 sm:px-3">
        <DecisionChip decision={item.decision} size="sm" />
      </td>
      <td className="py-2.5 px-2.5 sm:px-3 text-[13px] font-mono text-ink whitespace-nowrap">
        <span className="px-1.5 py-0.5 rounded bg-surface2/80 border border-line text-ink2 text-[12px]">
          {item.agent}
        </span>
      </td>
      <td className="py-2.5 px-3 sm:px-4 font-mono text-[13px] text-accent font-medium whitespace-nowrap">
        {item.tool}
      </td>
      <td className="py-2.5 px-3 sm:px-4 text-[13px] text-ink whitespace-nowrap">
        {item.target || '—'}
      </td>
      <td className="py-2.5 px-3 sm:px-4 font-mono text-[13px] text-ink font-semibold tabular-nums whitespace-nowrap">
        {typeof item.amount === 'number'
          ? `₹${item.amount.toLocaleString('en-IN')}`
          : item.amount || '—'}
      </td>
      <td className="py-2.5 px-3 sm:px-4 text-[13px] text-ink2 truncate max-w-xs" title={item.reason}>
        {item.reason}
      </td>
      {item.latencyMs !== undefined && (
        <td className="py-2.5 px-3 font-mono text-[11px] text-ink2 text-right hidden lg:table-cell">
          {item.latencyMs}ms
        </td>
      )}
      {item.sequence !== undefined && (
        <td className="py-2.5 px-3 font-mono text-[12px] text-accent text-right font-medium pr-4 hidden sm:table-cell">
          #{item.sequence}
        </td>
      )}
    </tr>
  )
}
