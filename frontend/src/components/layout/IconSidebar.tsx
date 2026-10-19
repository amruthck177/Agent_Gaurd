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

interface IconSidebarProps {
  currentPath?: string
  onNavigate?: (path: string) => void
  pendingApprovalCount?: number
}

export const IconSidebar: React.FC<IconSidebarProps> = ({
  currentPath = '/',
  onNavigate,
  pendingApprovalCount = 1,
}) => {
  const navItems = [
    { id: 'feed', label: 'Live Feed', href: '/', icon: <Activity className="w-5 h-5" /> },
    {
      id: 'approvals',
      label: 'Approvals',
      href: '/approvals',
      icon: <CheckSquare className="w-5 h-5" />,
      badge: pendingApprovalCount,
    },
    { id: 'policies', label: 'Policies', href: '/policies', icon: <FileText className="w-5 h-5" /> },
    { id: 'audit', label: 'Audit Log', href: '/audit', icon: <History className="w-5 h-5" /> },
    { id: 'tests', label: 'Test Results', href: '/tests', icon: <FlaskConical className="w-5 h-5" /> },
    { id: 'demo', label: 'Demo Panel', href: '/demo', icon: <PlaySquare className="w-5 h-5" /> },
    { id: 'styleguide', label: 'Styleguide', href: '/styleguide', icon: <Palette className="w-5 h-5" /> },
  ]

  return (
    <aside className="w-[72px] shrink-0 bg-bg border-r border-line flex flex-col items-center justify-between py-3 h-full select-none">
      <div className="flex flex-col items-center space-y-4">
        {/* Brand Shield */}
        <div className="w-10 h-10 rounded-lg bg-accent/15 border border-accent/40 flex items-center justify-center text-accent shadow-[0_0_12px_rgba(200,150,62,0.15)] mb-2">
          <Shield className="w-5 h-5" />
        </div>

        {/* Icons */}
        <nav className="flex flex-col items-center space-y-1.5 w-full px-2">
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
                className={`w-11 h-11 rounded-lg flex items-center justify-center relative transition-all ${
                  isActive
                    ? 'bg-surface2 text-accent border border-accent/40 shadow-sm'
                    : 'text-ink2 hover:text-ink hover:bg-surface border border-transparent'
                }`}
                title={item.label}
              >
                {item.icon}
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-ask text-bg font-mono font-bold text-[10px] flex items-center justify-center">
                    {item.badge}
                  </span>
                )}
              </a>
            )
          })}
        </nav>
      </div>

      {/* Bottom Dot */}
      <div className="w-3 h-3 rounded-full bg-allow animate-live-dot" title="Gateway Online" />
    </aside>
  )
}
