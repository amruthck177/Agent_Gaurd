import React, { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { WifiOff } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { IconSidebar } from './IconSidebar'
import { BottomTabBar } from './BottomTabBar'
import { Topbar } from './Topbar'
import { Banner } from './Banner'
import { api } from '../../lib/api'
import { useEvents } from '../../lib/useEvents'

interface AppShellProps {
  children: React.ReactNode
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const location = useLocation()
  const navigate = useNavigate()
  const [currentAgent, setCurrentAgent] = useState('accounts-agent')
  const [isPaused, setIsPaused] = useState(false)
  const [isGatewayOnline, setIsGatewayOnline] = useState(true)
  const [pendingApprovalCount, setPendingApprovalCount] = useState(0)

  // Live WebSocket hook
  useEvents((event) => {
    if (event.type === 'approval.created') {
      setPendingApprovalCount((prev) => prev + 1)
    } else if (event.type === 'approval.updated') {
      setPendingApprovalCount((prev) => Math.max(0, prev - 1))
    }
  })

  // Poll health and pending approvals
  useEffect(() => {
    let isMounted = true

    const checkHealth = async () => {
      try {
        await api.health()
        if (isMounted) setIsGatewayOnline(true)
      } catch {
        if (isMounted) setIsGatewayOnline(false)
      }
    }

    const fetchPendingApprovals = async () => {
      try {
        const approvals = await api.listApprovals('pending')
        if (isMounted) setPendingApprovalCount(approvals.length)
      } catch {
        // Handled by health check
      }
    }

    checkHealth()
    fetchPendingApprovals()

    const interval = setInterval(() => {
      checkHealth()
    }, 10000)

    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [])

  return (
    <div className="min-h-screen bg-bg text-ink flex flex-col font-sans">
      {/* 1. Critical Red Banner: Shown whenever Gateway is Unreachable / Offline */}
      {!isGatewayOnline && (
        <div
          role="alert"
          className="bg-block text-white px-4 py-2.5 flex items-center justify-between text-xs sm:text-sm font-semibold sticky top-0 z-50 shadow-lg"
        >
          <div className="flex items-center gap-2 max-w-5xl mx-auto w-full">
            <WifiOff className="w-5 h-5 shrink-0 animate-pulse" />
            <span>
              Gateway unreachable. All actions are being blocked until it returns. (Fail-closed mode active)
            </span>
          </div>
        </div>
      )}

      {/* 2. Slim Architectural Banner */}
      <Banner />

      {/* 3. Top Navigation Bar */}
      <Topbar
        currentAgent={currentAgent}
        onAgentChange={setCurrentAgent}
        gatewayStatus={isGatewayOnline ? 'online' : 'unreachable'}
        isPaused={isPaused}
        onPauseAgent={() => setIsPaused(!isPaused)}
      />

      {/* 4. Adaptive Layout (Sidebar on Laptop, IconSidebar on Tablet, BottomTabBar on Mobile) */}
      <div className="flex-1 flex min-w-0 pb-16 md:pb-0">
        {/* Laptop Sidebar (>= 1200px) */}
        <div className="hidden xl:block shrink-0">
          <Sidebar
            currentPath={location.pathname}
            onNavigate={(path) => navigate(path)}
            pendingApprovalCount={pendingApprovalCount}
          />
        </div>

        {/* Tablet IconSidebar (768px - 1199px) */}
        <div className="hidden md:block xl:hidden shrink-0">
          <IconSidebar
            currentPath={location.pathname}
            onNavigate={(path) => navigate(path)}
            pendingApprovalCount={pendingApprovalCount}
          />
        </div>

        {/* Main Content Canvas (Fluid up to 1440px) */}
        <div className="flex-1 min-w-0 overflow-y-auto">
          <div className="max-w-[1440px] mx-auto w-full p-4 sm:p-6 lg:p-8">
            {children}
          </div>
        </div>
      </div>

      {/* 5. Mobile Bottom Tab Bar (< 768px) */}
      <div className="md:hidden">
        <BottomTabBar
          currentPath={location.pathname}
          onNavigate={(path) => navigate(path)}
          pendingApprovalCount={pendingApprovalCount}
        />
      </div>
    </div>
  )
}
