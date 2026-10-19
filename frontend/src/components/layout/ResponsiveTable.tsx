import React from 'react'
import { ActionItem, ActionRow } from '../common/ActionRow'
import { DecisionChip } from '../common/DecisionChip'

interface ResponsiveTableProps {
  items: ActionItem[]
  onRowClick?: (item: ActionItem) => void
  selectedId?: string | number
  isMobileCardList?: boolean // For forcing mobile card list mode (e.g. In styleguide)
}

export const ResponsiveTable: React.FC<ResponsiveTableProps> = ({
  items,
  onRowClick,
  selectedId,
  isMobileCardList = false,
}) => {
  return (
    <div className="w-full">
      {/* 1. Mobile Card List View (visible when screen < 768px or forced) */}
      <div className={`space-y-3 ${isMobileCardList ? 'block' : 'block md:hidden'}`}>
        {items.map((item) => {
          const isSelected = selectedId === item.id
          const borderClass =
            item.decision === 'BLOCK'
              ? 'border-l-4 border-l-block'
              : item.decision === 'ASK HUMAN'
              ? 'border-l-4 border-l-ask'
              : 'border-l-4 border-l-allow'

          return (
            <div
              key={item.id}
              onClick={() => onRowClick?.(item)}
              className={`rounded-card border border-line bg-surface p-4 transition-all cursor-pointer ${borderClass} ${
                isSelected ? 'ring-1 ring-accent bg-surface2' : 'hover:bg-surface2/60'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="font-mono text-[11px] text-ink2">{item.time}</span>
                <DecisionChip decision={item.decision} size="sm" />
              </div>

              <div className="flex items-baseline justify-between mb-1.5">
                <span className="font-mono text-[14px] font-semibold text-accent truncate">
                  {item.tool}
                </span>
                {item.amount && (
                  <span className="font-mono text-[14px] font-bold text-ink tabular-nums">
                    {typeof item.amount === 'number'
                      ? `₹${item.amount.toLocaleString('en-IN')}`
                      : item.amount}
                  </span>
                )}
              </div>

              <div className="flex items-center justify-between text-[12px] text-ink2 mt-2 pt-2 border-t border-line/50">
                <span className="font-mono text-[11px] bg-surface2 px-1.5 py-0.5 rounded border border-line">
                  {item.agent}
                </span>
                <span className="truncate max-w-[200px]" title={item.reason}>
                  {item.reason}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* 2. Desktop & Tablet Table View (visible when screen >= 768px and not forced) */}
      <div
        className={`rounded-card border border-line bg-surface overflow-hidden shadow-sm ${
          isMobileCardList ? 'hidden' : 'hidden md:block'
        }`}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface2/80 border-b border-line text-[11px] font-mono text-ink2 uppercase tracking-wider">
                <th className="py-3 px-4">Time</th>
                <th className="py-3 px-3">Decision</th>
                <th className="py-3 px-3">Agent</th>
                <th className="py-3 px-4">Action (Tool)</th>
                <th className="py-3 px-4">Target</th>
                <th className="py-3 px-4">Amount</th>
                <th className="py-3 px-4">Enforcement Reason</th>
                <th className="py-3 px-3 text-right hidden lg:table-cell">Latency</th>
                <th className="py-3 px-4 text-right hidden sm:table-cell">Record</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/40">
              {items.map((item) => (
                <ActionRow
                  key={item.id}
                  item={item}
                  isSelected={selectedId === item.id}
                  onClick={onRowClick}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
