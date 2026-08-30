/**
 * AppLayout — shared shell for all authenticated pages.
 *
 * Structure:
 *   ┌─────────────────────────────────────┐
 *   │  Sidebar (fixed, left)              │
 *   │  ┌─────────────────────────────┐    │
 *   │  │  Logo                       │    │
 *   │  │  Nav links                  │    │
 *   │  │  ...                        │    │
 *   │  │  User section (bottom)      │    │
 *   │  └─────────────────────────────┘    │
 *   │  Main content area (scrollable)     │
 *   └─────────────────────────────────────┘
 *
 * Phase 14 will add: mobile sidebar toggle, active incident badge,
 * project switcher, and notification bell.
 */

import { NavLink, useNavigate } from 'react-router-dom'
import { authStore } from '@/store/authStore'
import clsx from 'clsx'

// ── Nav item definition ───────────────────────────────────────────────────────
interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
}

const navItems: NavItem[] = [
  {
    label: 'Overview',
    path: '/',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    label: 'Services',
    path: '/services',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
      </svg>
    ),
  },
  {
    label: 'Incidents',
    path: '/incidents',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round"
          d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
        />
      </svg>
    ),
  },
]

// ── Sidebar ───────────────────────────────────────────────────────────────────
function Sidebar() {
  const navigate = useNavigate()

  function handleSignOut() {
    authStore.clearToken()
    navigate('/login')
  }

  return (
    <aside className="fixed inset-y-0 left-0 w-56 bg-surface-800 border-r border-surface-600 flex flex-col z-20">
      {/* Logo */}
      <div className="h-14 flex items-center gap-2.5 px-4 border-b border-surface-600">
        <div className="w-7 h-7 rounded-md bg-brand-600 flex items-center justify-center flex-shrink-0">
          <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd"
              d="M3 3a1 1 0 000 2v8a2 2 0 002 2h2.586l-1.293 1.293a1 1 0 101.414 1.414L10 15.414l2.293 2.293a1 1 0 001.414-1.414L12.414 15H15a2 2 0 002-2V5a1 1 0 100-2H3zm11 4a1 1 0 10-2 0v4a1 1 0 102 0V7zm-3 1a1 1 0 10-2 0v3a1 1 0 102 0V8zM8 9a1 1 0 00-2 0v2a1 1 0 102 0V9z"
              clipRule="evenodd"
            />
          </svg>
        </div>
        <div>
          <p className="text-white font-semibold text-sm leading-tight">PulseOps</p>
          <p className="text-gray-500 text-xs leading-tight">AI Observability</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto">
        <p className="text-xs font-medium text-gray-600 uppercase tracking-wider px-2 mb-2">
          Platform
        </p>
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-2.5 px-2 py-2 rounded-lg text-sm font-medium transition-colors duration-100',
                isActive
                  ? 'bg-brand-600/20 text-brand-400 border border-brand-600/30'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-surface-700',
              )
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Bottom: status indicator + sign out */}
      <div className="px-3 py-4 border-t border-surface-600 space-y-3">
        {/* System status pill */}
        <div className="flex items-center gap-2 px-2">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs text-gray-500">System operational</span>
        </div>

        <button
          onClick={handleSignOut}
          className="w-full flex items-center gap-2.5 px-2 py-2 rounded-lg text-sm text-gray-500
                     hover:text-gray-300 hover:bg-surface-700 transition-colors duration-100"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
            />
          </svg>
          Sign out
        </button>
      </div>
    </aside>
  )
}

// ── Top header bar ────────────────────────────────────────────────────────────
function TopBar({ title }: { title?: string }) {
  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-surface-600 bg-surface-800/50 backdrop-blur-sm">
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span>PulseOps AI</span>
        {title && (
          <>
            <span>/</span>
            <span className="text-gray-300">{title}</span>
          </>
        )}
      </div>

      {/* Phase 14: notification bell, project switcher */}
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 rounded-full bg-surface-600 flex items-center justify-center">
          <span className="text-xs text-gray-400 font-medium">U</span>
        </div>
      </div>
    </header>
  )
}

// ── Main layout ───────────────────────────────────────────────────────────────
interface AppLayoutProps {
  children: React.ReactNode
  title?: string
}

export default function AppLayout({ children, title }: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-surface-900">
      <Sidebar />

      {/* Main content pushed right by sidebar width */}
      <div className="ml-56 flex flex-col min-h-screen">
        <TopBar title={title} />

        <main className="flex-1 p-6 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
