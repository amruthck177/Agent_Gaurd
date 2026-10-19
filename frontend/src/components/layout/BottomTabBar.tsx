import React from 'react'
import {
  Activity,
  CheckSquare,
  History,
  FileText,
  Sliders,
} from 'lucide-react'

interface BottomTabBarProps {
  currentPath?: string
  onNavigate?: (path: string) => void
  pendingApprovalCount?: number
}

export const BottomTabBar: React.FC<BottomTabBarProps> = ({
  currentPath = '/',
  onNavigate,
  pendingApprovalCount = 1,
}) => {
  const tabs = [
    { id: 'feed', label: 'Feed', href: '/', icon: <Activity className="w-5 h-5" /> },
    {
      id: 'approvals',
      label: 'Approvals',
      href: '/approvals',
      icon: <CheckSquare className="w-5 h-5" />,
      badge: pendingApprovalCount,
    },
    { id: 'audit', label: 'Audit', href: '/audit', icon: <History className="w-5 h-5" /> },
    { id: 'policies', label: 'Policies', href: '/policies', icon: <FileText className="w-5 h-5" /> },
    { id: 'more', label: 'More', href: '/demo', icon: <Sliders className="w-5 h-5" /> },
  ]

  return (
    <nav className="fixed bottom-0 left-0 right-0 h-16 bg-surface/95 backdrop-blur-md border-t border-line flex items-center justify-around px-2 z-40 select-none pb-safe">
      {tabs.map((tab) => {
        const isActive = currentPath === tab.href

        return (
          <a
            key={tab.id}
            href={tab.href}
            onClick={(e) => {
              if (onNavigate) {
                e.preventDefault()
                onNavigate(tab.href)
              }
            }}
            className={`flex flex-col items-center justify-center flex-1 py-1 gap-1 relative transition-colors ${
              isActive ? 'text-accent font-semibold' : 'text-ink2 hover:text-ink'
            }`}
          >
            <div className="relative">
              {tab.icon}
              {tab.badge !== undefined && tab.badge > 0 && (
                <span className="absolute -top-1.5 -right-2 px-1 rounded-full bg-ask text-bg font-mono font-bold text-[9px] flex items-center justify-center min-w-[14px]">
                  {tab.badge}
                </span>
              )}
            </div>
            <span className="text-[11px] tracking-tight">{tab.label}</span>
            {isActive && (
              <span className="w-1 h-1 rounded-full bg-accent absolute bottom-1" />
            )}
          </a>
        )
      })}
    </nav>
  )
}
