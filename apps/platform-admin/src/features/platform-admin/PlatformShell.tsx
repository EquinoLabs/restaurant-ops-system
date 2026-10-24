import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import {
  Building2,
  CheckSquare,
  CreditCard,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react';
import { RoleBadge } from '../../components/ops-ui';

export type PlatformTab = 'dashboard' | 'businesses' | 'plans' | 'subscriptions' | 'admins' | 'approvals' | 'audit-logs';

interface PlatformShellProps {
  activeTab: PlatformTab;
  onTabChange: (tab: PlatformTab) => void;
  children: React.ReactNode;
}

interface NavItem {
  id: PlatformTab;
  label: string;
  icon: LucideIcon;
}

interface NavGroup {
  label: string | null;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    label: null,
    items: [{ id: 'dashboard', label: 'Overview', icon: LayoutDashboard }],
  },
  {
    label: 'Customers',
    items: [{ id: 'businesses', label: 'Businesses', icon: Building2 }],
  },
  {
    label: 'Commercial',
    items: [
      { id: 'subscriptions', label: 'Subscriptions', icon: CreditCard },
      { id: 'plans', label: 'Plans', icon: FileText },
    ],
  },
  {
    label: 'Platform',
    items: [
      { id: 'admins', label: 'Team', icon: Users },
      { id: 'approvals', label: 'Approvals', icon: CheckSquare },
      { id: 'audit-logs', label: 'Audit Logs', icon: ScrollText },
    ],
  },
];

function NavButton({
  item,
  isActive,
  onSelect,
}: {
  item: NavItem;
  isActive: boolean;
  onSelect: (id: PlatformTab) => void;
}) {
  const Icon = item.icon;
  return (
    <button
      type="button"
      onClick={() => onSelect(item.id)}
      aria-current={isActive ? 'page' : undefined}
      className={`relative flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-[13px] font-medium transition-colors duration-100 ease-in-out focus:outline-none focus:ring-2 focus:ring-ops-accent-focus focus:ring-offset-1 ${
        isActive
          ? 'bg-ops-accent/10 text-ops-accent font-semibold'
          : 'text-ops-text-secondary hover:bg-ops-canvas hover:text-ops-text-primary'
      }`}
    >
      {isActive && (
        <span className="absolute inset-y-1 left-0 w-0.5 rounded bg-ops-accent" aria-hidden="true" />
      )}
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{item.label}</span>
    </button>
  );
}

function NavList({
  groups,
  activeTab,
  onSelect,
}: {
  groups: NavGroup[];
  activeTab: PlatformTab;
  onSelect: (id: PlatformTab) => void;
}) {
  return (
    <nav className="flex flex-col gap-5" aria-label="Platform navigation">
      {groups.map((group) => (
        <div key={group.label ?? 'overview'}>
          {group.label && (
            <div className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wide text-ops-text-secondary">
              {group.label}
            </div>
          )}
          <div className="flex flex-col gap-0.5">
            {group.items.map((item) => (
              <NavButton
                key={item.id}
                item={item}
                isActive={activeTab === item.id}
                onSelect={onSelect}
              />
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

export const PlatformShell: React.FC<PlatformShellProps> = ({
  activeTab,
  onTabChange,
  children,
}) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const isOperator = user?.platform_role === 'operator';
  const visibleNavGroups = navGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !(item.id === 'admins' && isOperator)),
    }))
    .filter((group) => group.items.length > 0);

  const roleBadgeLabel = (() => {
    if (user?.platform_role === 'owner') return 'Platform Owner';
    if (user?.platform_role === 'admin') return 'Platform Admin';
    if (user?.platform_role === 'operator') return 'Platform Operator';
    if (user?.platform_role == null && user?.is_platform_admin) return 'Platform Admin (Legacy)';
    return 'Platform Staff';
  })();

  const handleSelect = (tab: PlatformTab) => {
    onTabChange(tab);
    setIsMobileMenuOpen(false);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen min-h-screen bg-ops-canvas font-sans text-ops-text-primary">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-ops-border bg-white md:flex">
        <div className="flex h-12 items-center border-b border-ops-border px-4">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded bg-ops-accent text-[10px] font-semibold text-white">
              ROMS
            </div>
            <span className="text-sm font-semibold tracking-tight text-ops-text-primary">
              Platform Admin
            </span>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          <NavList groups={visibleNavGroups} activeTab={activeTab} onSelect={handleSelect} />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-ops-border bg-white px-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              className="rounded p-1.5 text-ops-text-secondary hover:bg-ops-canvas hover:text-ops-text-primary focus:outline-none focus:ring-2 focus:ring-ops-accent-focus md:hidden"
              aria-label="Toggle Navigation Menu"
            >
              <Menu className="h-5 w-5" aria-hidden="true" />
            </button>
            <span className="text-sm font-semibold text-ops-text-primary md:hidden">
              Platform Admin
            </span>
            <span className="hidden text-sm font-medium text-ops-text-secondary md:inline">
              ROMS Platform
            </span>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden flex-col items-end leading-tight sm:flex">
              <span className="text-[13px] font-medium text-ops-text-primary">
                {user?.display_name || 'Platform Admin'}
              </span>
              <span className="text-[11px] text-ops-text-secondary">{user?.email}</span>
            </div>
            <RoleBadge label={roleBadgeLabel} />
            <button
              type="button"
              onClick={handleLogout}
              className="rounded p-1.5 text-ops-text-secondary transition-colors hover:bg-ops-canvas hover:text-ops-text-primary focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
              title="Sign Out"
              aria-label="Sign Out"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1440px] p-4 sm:p-6 lg:p-8">{children}</div>
        </main>
      </div>

      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-[rgba(31,41,51,0.40)]"
            aria-hidden="true"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-full flex-col border-r border-ops-border bg-white shadow-ops-l2">
            <div className="flex h-12 items-center justify-between border-b border-ops-border px-4">
              <span className="text-sm font-semibold text-ops-text-primary">Navigation</span>
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen(false)}
                className="rounded p-1 text-ops-text-secondary hover:bg-ops-canvas hover:text-ops-text-primary focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
                aria-label="Close Navigation Menu"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              <NavList groups={visibleNavGroups} activeTab={activeTab} onSelect={handleSelect} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
