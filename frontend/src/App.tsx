/**
 * App root — routing configuration.
 *
 * Route structure:
 *   /login                    → LoginPage
 *   /register                 → RegisterPage
 *   /                         → Dashboard (protected)
 *   /services                 → Services list (protected)
 *   /services/:id             → Service detail (protected)
 *   /services/:id/endpoints   → Endpoint explorer (protected)
 *   /incidents                → Incidents list (protected)
 *   /incidents/:id            → Incident investigation (protected)
 *
 * Protected routes check localStorage for a JWT token.
 * If none is found, the user is redirected to /login.
 * Full auth context and user data is wired in Phase 3.
 */

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { authStore } from '@/store/authStore'

// Page imports — stub components until each phase is built
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import DashboardPage from '@/pages/DashboardPage'
import ServicesPage from '@/pages/ServicesPage'
import ServiceDetailPage from '@/pages/ServiceDetailPage'
import IncidentsPage from '@/pages/IncidentsPage'
import IncidentDetailPage from '@/pages/IncidentDetailPage'

/** Wraps a route to require authentication. */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!authStore.isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected routes */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/services"
          element={
            <ProtectedRoute>
              <ServicesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/services/:serviceId"
          element={
            <ProtectedRoute>
              <ServiceDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/incidents"
          element={
            <ProtectedRoute>
              <IncidentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/incidents/:incidentId"
          element={
            <ProtectedRoute>
              <IncidentDetailPage />
            </ProtectedRoute>
          }
        />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
