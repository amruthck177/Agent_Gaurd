import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { LiveFeed } from './pages/LiveFeed'
import { Approvals } from './pages/Approvals'
import { Policies } from './pages/Policies'
import { AuditLog } from './pages/AuditLog'
import { TestResults } from './pages/TestResults'
import { DemoPanel } from './pages/DemoPanel'
import { Styleguide } from './pages/Styleguide'
import { MobileApproval } from './pages/MobileApproval'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Mobile Simulated Approver Screen (/m/:approvalId) - Dedicated full screen enclave */}
        <Route path="/m/:approvalId" element={<MobileApproval />} />
        <Route path="/m/:id" element={<MobileApproval />} />

        {/* Dashboard Pages wrapped in AppShell */}
        <Route
          path="/"
          element={
            <AppShell>
              <LiveFeed />
            </AppShell>
          }
        />
        <Route
          path="/approvals"
          element={
            <AppShell>
              <Approvals />
            </AppShell>
          }
        />
        <Route
          path="/policies"
          element={
            <AppShell>
              <Policies />
            </AppShell>
          }
        />
        <Route
          path="/audit"
          element={
            <AppShell>
              <AuditLog />
            </AppShell>
          }
        />
        <Route
          path="/tests"
          element={
            <AppShell>
              <TestResults />
            </AppShell>
          }
        />
        <Route
          path="/demo"
          element={
            <AppShell>
              <DemoPanel />
            </AppShell>
          }
        />
        <Route
          path="/styleguide"
          element={
            <AppShell>
              <Styleguide />
            </AppShell>
          }
        />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
