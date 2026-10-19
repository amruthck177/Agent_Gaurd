import React from 'react'
import {
  Shield,
  Activity,
  CheckSquare,
  FileText,
  History,
  FlaskConical,
  PlaySquare,
  Palette,
} from 'lucide-react'
import { SimulatedBadge } from '../common/SimulatedBadge'

export interface NavItem {
  id: string
  label: string
  href: string
  icon: React.ReactNode
  badgeCount?: number
}

interface SidebarProps {
  currentPath?: string
  onNavigate?: (path: string) => void
  pendingApprovalCount?: number
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPath = '/',
  onNavigate,
  pendingApprovalCount = 1,
}) => {
  const navItems: NavItem[] = [
    { id: 'feed', label: 'Live Feed', href: '/', icon: <Activity className="w-[18px] h-[18px]" /> },
    {
      id: 'approvals',
      label: 'Approvals',
      href: '/approvals',
      icon: <CheckSquare className="w-[18px] h-[18px]" />,
      badgeCount: pendingApprovalCount,
    },
    { id: 'policies', label: 'Policies', href: '/policies', icon: <FileText className="w-[18px] h-[18px]" /> },
    { id: 'audit', label: 'Audit Log', href: '/audit', icon: <History className="w-[18px] h-[18px]" /> },
    { id: 'tests', label: 'Test Results', href: '/tests', icon: <FlaskConical className="w-[18px] h-[18px]" /> },
    { id: 'demo', label: 'Demo Panel', href: '/demo', icon: <PlaySquare className="w-[18px] h-[18px]" /> },
    { id: 'styleguide', label: 'Styleguide', href: '/styleguide', icon: <Palette className="w-[18px] h-[18px]" /> },
  ]

  return (
    <aside className="w-[240px] shrink-0 bg-bg border-r border-line flex flex-col justify-between h-full select-none">
      <div className="flex flex-col">
        {/* Brand Anchor */}
        <div className="h-16 flex items-center px-5 border-b border-line gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/40 flex items-center justify-center text-accent shadow-[0_0_12px_rgba(200,150,62,0.15)]">
            <Shield className="w-5 h-5" />
          </div>
          <div className="flex flex-col">
            <span className="text-[17px] font-bold text-accent tracking-tight leading-none">
              AgentGuard
            </span>
            <span className="font-mono text-[10px] text-ink2 tracking-wider mt-1 uppercase">
              Sovereign Gate
            </span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const isActive = currentPath === item.href

            return (
              <a
                key={item.id}
                href={item.href}
                onClick={(e) => {
                  if (onNavigate) {
                    e.preventDefault()
                    onNavigate(item.href)
                  }
                }}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all ${
                  isActive
                    ? 'bg-surface2 border border-accent/40 text-accent shadow-[inset_2px_0_0_#C8963E] font-semibold'
                    : 'text-ink2 hover:text-ink hover:bg-surface border border-transparent'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className={isActive ? 'text-accent' : 'text-ink2'}>{item.icon}</span>
                  <span>{item.label}</span>
                </div>

                {item.badgeCount !== undefined && item.badgeCount > 0 && (
                  <span className="px-1.5 py-0.2 rounded text-[11px] font-mono font-bold bg-ask/15 text-ask border border-ask/30">
                    {item.badgeCount}
                  </span>
                )}

                {isActive && !item.badgeCount && (
                  <span className="w-1.5 h-1.5 rounded-full bg-accent shadow-[0_0_6px_#C8963E]" />
                )}
              </a>
            )
          })}
        </nav>
      </div>

      {/* Bottom Status Cards */}
      <div className="p-3 border-t border-line space-y-2 bg-bg/80">
        <div className="p-2.5 rounded-lg bg-surface border border-line">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-accent" />
            <span className="font-mono text-[11px] font-semibold text-accent">
              Deterministic Guard
            </span>
          </div>
          <p className="text-[10px] text-ink2 font-mono">Enclave: Fail-Closed Strict</p>
        </div>

        <SimulatedBadge variant="footer" />
      </div>
    </aside>
  )
}
