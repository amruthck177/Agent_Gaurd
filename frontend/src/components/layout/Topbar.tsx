import React, { useState } from 'react'
import {
  Search,
  PauseCircle,
  ChevronDown,
  Shield,
  PlayCircle,
} from 'lucide-react'

interface TopbarProps {
  currentAgent?: string
  onAgentChange?: (agent: string) => void
  gatewayStatus?: 'online' | 'unreachable'
  latencyMs?: number
  onPauseAgent?: () => void
  isPaused?: boolean
  onSearch?: (query: string) => void
  onToggleTheme?: () => void
  theme?: 'dark' | 'light'
}

export const Topbar: React.FC<TopbarProps> = ({
  currentAgent = 'accounts-agent',
  onAgentChange,
  gatewayStatus = 'online',
  latencyMs = 0.4,
  onPauseAgent,
  isPaused = false,
  onSearch,
  onToggleTheme,
  theme = 'dark',
}) => {
  const [searchVal, setSearchVal] = useState('')
  const [agentDropdownOpen, setAgentDropdownOpen] = useState(false)

  const agents = ['accounts-agent', 'inventory-agent', 'reader-agent', 'all-autonomous-agents']

  const isOnline = gatewayStatus === 'online'

  return (
    <header className="h-16 px-4 sm:px-6 lg:px-8 bg-surface border-b border-line flex items-center justify-between sticky top-0 z-30 shrink-0">
      {/* Left Side: Mobile Logo & Agent Selector & Search */}
      <div className="flex items-center gap-3 sm:gap-4 flex-1 max-w-2xl min-w-0">
        {/* Mobile Shield Brand mark */}
        <div className="flex items-center gap-2 lg:hidden shrink-0">
          <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/40 flex items-center justify-center text-accent">
            <Shield className="w-5 h-5" />
          </div>
          <span className="font-bold text-accent text-[16px] tracking-tight hidden sm:inline">AgentGuard</span>
        </div>

        {/* Agent Selector */}
        <div className="relative shrink-0">
          <button
            onClick={() => setAgentDropdownOpen(!agentDropdownOpen)}
            className="h-9 px-2.5 sm:px-3 rounded-lg bg-surface2 border border-line text-ink flex items-center gap-2 font-mono text-[12px] sm:text-[13px] font-semibold hover:border-ink2 transition-colors focus-accent"
          >
            <span className="w-2 h-2 rounded-full bg-allow" />
            <span className="truncate max-w-[110px] sm:max-w-none">{currentAgent}</span>
            <ChevronDown className="w-3.5 h-3.5 text-ink2 shrink-0" />
          </button>

          {agentDropdownOpen && (
            <div className="absolute left-0 mt-1 w-48 rounded-lg bg-surface2 border border-line shadow-2xl py-1 z-50">
              {agents.map((ag) => (
                <button
                  key={ag}
                  onClick={() => {
                    onAgentChange?.(ag)
                    setAgentDropdownOpen(false)
                  }}
                  className={`w-full text-left px-3 py-2 text-[12px] font-mono transition-colors ${
                    ag === currentAgent
                      ? 'bg-accent/15 text-accent font-bold'
                      : 'text-ink hover:bg-surface'
                  }`}
                >
                  {ag}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Search Input */}
        <div className="relative flex-1 max-w-md hidden md:block">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink2" />
          <input
            type="text"
            value={searchVal}
            onChange={(e) => {
              setSearchVal(e.target.value)
              onSearch?.(e.target.value)
            }}
            placeholder="Search intercepts, hashes, payload..."
            className="w-full h-9 pl-9 pr-12 rounded-lg bg-surface2 border border-line text-ink placeholder:text-ink2/60 text-[13px] focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-all"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-mono bg-surface border border-line rounded text-ink2 pointer-events-none">
            ⌘K
          </kbd>
        </div>
      </div>

      {/* Right Side: Emergency Pause, Gateway Status, Avatar */}
      <div className="flex items-center gap-3 sm:gap-4 shrink-0">
        {/* Pause Agent Button */}
        <button
          onClick={onPauseAgent}
          className={`h-9 px-3 sm:px-3.5 rounded-lg border font-semibold text-[12px] sm:text-[13px] flex items-center gap-1.5 sm:gap-2 transition-all active:scale-95 shadow-sm ${
            isPaused
              ? 'border-allow/60 bg-allow/15 text-allow hover:bg-allow/25'
              : 'border-block/60 bg-block/10 text-block hover:bg-block/20'
          }`}
          title={isPaused ? 'Resume Agent' : 'Pause Agent'}
        >
          {isPaused ? (
            <>
              <PlayCircle className="w-4 h-4 text-allow" />
              <span className="hidden sm:inline">Resume Agent</span>
              <span className="sm:hidden">Resume</span>
            </>
          ) : (
            <>
              <PauseCircle className="w-4 h-4 text-block" />
              <span className="hidden sm:inline">Pause Agent</span>
              <span className="sm:hidden">Pause</span>
            </>
          )}
        </button>

        {/* Gateway Status Pill */}
        <div className="h-8 px-2.5 sm:px-3 rounded-pill bg-surface2 border border-line flex items-center gap-1.5 sm:gap-2 text-[11px] font-mono">
          <span className="relative flex h-2 w-2">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isOnline ? 'bg-allow' : 'bg-block'
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                isOnline ? 'bg-allow' : 'bg-block'
              }`}
            />
          </span>
          <span className="text-ink font-medium hidden sm:inline">
            {isOnline ? 'Gateway: online' : 'Gateway: unreachable'}
          </span>
          <span className="text-ink font-medium sm:hidden">
            {isOnline ? 'online' : 'unreachable'}
          </span>
          {isOnline && (
            <>
              <span className="text-ink2 hidden md:inline">•</span>
              <span className="text-accent hidden md:inline">{latencyMs}ms</span>
            </>
          )}
        </div>

        {/* Theme Switcher (optional light mode support per design.md) */}
        {onToggleTheme && (
          <button
            onClick={onToggleTheme}
            className="p-1.5 rounded-lg border border-line hover:bg-surface2 text-ink2 hover:text-ink text-[12px]"
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} theme`}
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        )}

        {/* Avatar */}
        <div className="flex items-center gap-2 pl-1 sm:pl-2 border-l border-line/70">
          <div className="w-8 h-8 rounded-full bg-accent/20 border border-accent/60 text-accent flex items-center justify-center font-mono text-[12px] font-bold">
            AG
          </div>
          <div className="hidden xl:flex flex-col text-left">
            <span className="text-[12px] font-semibold text-ink leading-tight">SecOps Lead</span>
            <span className="text-[10px] font-mono text-ink2 leading-tight">Forensic Tier 1</span>
          </div>
        </div>
      </div>
    </header>
  )
}
