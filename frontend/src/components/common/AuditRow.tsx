import React from 'react'
import { Copy, Link, AlertTriangle } from 'lucide-react'
import { DecisionChip, DecisionType } from './DecisionChip'

export interface AuditRecordItem {
  id: number
  timestamp: string
  agent: string
  action: string
  decision: DecisionType
  reason: string
  decidedBy: string
  currentHash: string
  prevHash: string
  isChainBroken?: boolean
}

interface AuditRowProps {
  record: AuditRecordItem
  isLast?: boolean
  onInspect?: (record: AuditRecordItem) => void
  onCopyHash?: (hash: string) => void
}

export const AuditRow: React.FC<AuditRowProps> = ({
  record,
  isLast = false,
  onInspect,
  onCopyHash,
}) => {
  const shortHash = (h: string) => {
    if (!h || h.length < 10) return h
    return `${h.slice(0, 6)}…${h.slice(-4)}`
  }

  const rowBg = record.isChainBroken
    ? 'bg-block/15 border-l-4 border-l-block'
    : 'hover:bg-surface2/60'

  return (
    <tr
      className={`h-[52px] border-b border-line/60 transition-colors text-[13px] relative group ${rowBg}`}
    >
      {/* Sequence # */}
      <td className="py-2.5 px-3 sm:px-4 font-mono font-bold text-accent whitespace-nowrap">
        #{record.id}
      </td>

      {/* Timestamp */}
      <td className="py-2.5 px-3 font-mono text-[12px] text-ink2 whitespace-nowrap">
        {record.timestamp}
      </td>

      {/* Agent */}
      <td className="py-2.5 px-3 whitespace-nowrap">
        <span className="px-1.5 py-0.5 rounded bg-surface2 border border-line font-mono text-[11px] text-ink2">
          {record.agent}
        </span>
      </td>

      {/* Action / Tool */}
      <td className="py-2.5 px-3 font-mono font-medium text-ink whitespace-nowrap">
        {record.action}
      </td>

      {/* Decision */}
      <td className="py-2.5 px-3 whitespace-nowrap">
        <DecisionChip decision={record.decision} size="sm" />
      </td>

      {/* Enforcement Reason */}
      <td className="py-2.5 px-3 text-ink2 truncate max-w-xs" title={record.reason}>
        {record.reason}
      </td>

      {/* Decided By */}
      <td className="py-2.5 px-3 text-ink2 text-[12px] hidden md:table-cell">
        {record.decidedBy}
      </td>

      {/* Current Hash */}
      <td className="py-2.5 px-3 text-center whitespace-nowrap">
        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface2 font-mono text-[11px] text-ink border border-line">
          <span>{shortHash(record.currentHash)}</span>
          <button
            onClick={() => onCopyHash?.(record.currentHash)}
            className="text-ink2 hover:text-accent transition-colors"
            title="Copy SHA-256 Hash"
          >
            <Copy className="w-3 h-3" />
          </button>
        </div>
      </td>

      {/* Prev Hash & Chain Connector Line */}
      <td className="py-2.5 px-3 text-center whitespace-nowrap relative">
        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface2/60 font-mono text-[11px] text-ink2 border border-line">
          <span>{shortHash(record.prevHash)}</span>
          <button
            onClick={() => onCopyHash?.(record.prevHash)}
            className="text-ink2 hover:text-ink transition-colors"
            title="Copy Previous Hash"
          >
            <Copy className="w-3 h-3" />
          </button>
        </div>

        {/* Chain Connector Graphic linking consecutive rows */}
        {!isLast && (
          <span
            className={`absolute -bottom-3 left-1/2 -translate-x-1/2 w-0.5 h-6 z-10 hidden group-hover:block pointer-events-none ${
              record.isChainBroken ? 'bg-block' : 'bg-accent/40'
            }`}
          />
        )}
      </td>

      {/* Chain Status Icon / Inspect */}
      <td className="py-2.5 px-3 text-right pr-4 whitespace-nowrap">
        {record.isChainBroken ? (
          <span className="inline-flex items-center gap-1 text-block text-[11px] font-semibold">
            <AlertTriangle className="w-4 h-4 text-block" />
            <span>Broken</span>
          </span>
        ) : (
          <button
            onClick={() => onInspect?.(record)}
            className="p-1 rounded hover:bg-surface2 text-ink2 hover:text-accent transition-colors"
            title="Inspect record"
          >
            <Link className="w-4 h-4" />
          </button>
        )}
      </td>
    </tr>
  )
}
