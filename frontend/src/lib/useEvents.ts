import { useEffect, useRef, useState, useCallback } from 'react'

export type WsEventType =
  | 'gateway.decision'
  | 'approval.created'
  | 'approval.updated'
  | 'policy.updated'
  | 'demo.reset'
  | 'demo.tamper'
  | 'demo.scenario'

export interface WsEvent<T = unknown> {
  type: WsEventType
  action?: string
  data?: T
  status?: string
  record_id?: number
}

export interface GatewayDecisionEventData {
  agent_id: string
  task_id: string
  tool: string
  decision: 'ALLOW' | 'ASK_HUMAN' | 'BLOCK'
  reason: string
  executed: boolean
  audit_id: number | null
  approval_id: string | null
}

export function useEvents(onEvent?: (event: WsEvent) => void) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const pingIntervalRef = useRef<number | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const reconnectAttemptRef = useRef(0)
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  const connect = useCallback(() => {
    // Clean existing
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/events`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        reconnectAttemptRef.current = 0

        // Keep-alive heartbeat: send 'ping' every 20 seconds
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current)
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping')
          }
        }, 20000)
      }

      ws.onmessage = (event) => {
        if (event.data === 'pong') return

        try {
          const parsed = JSON.parse(event.data) as WsEvent
          setLastEvent(parsed)
          onEventRef.current?.(parsed)
        } catch {
          // Non-JSON ping/pong or string ignore
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current)

        // Automatic Reconnect with exponential backoff capped at 10s
        const backoffMs = Math.min(1000 * Math.pow(1.5, reconnectAttemptRef.current), 10000)
        reconnectAttemptRef.current += 1

        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect()
        }, backoffMs)
      }

      ws.onerror = () => {
        setIsConnected(false)
        ws.close()
      }
    } catch {
      setIsConnected(false)
    }
  }, [])

  useEffect(() => {
    connect()

    return () => {
      if (wsRef.current) wsRef.current.close()
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current)
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
    }
  }, [connect])

  return {
    isConnected,
    lastEvent,
    reconnect: connect,
  }
}
