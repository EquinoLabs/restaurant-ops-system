import React, { useCallback, useId, useRef } from 'react';

export interface TabItem {
  id: string;
  label: string;
  disabled?: boolean;
}

export interface TabsProps {
  tabs: TabItem[];
  activeId: string;
  onChange: (id: string) => void;
  className?: string;
  /** Class for the optional tabpanel wrapper (only used when children are provided). */
  panelClassName?: string;
  /**
   * Optional panel content for the active tab. When provided, an associated
   * `role="tabpanel"` is rendered so keyboard and AT navigation stay in sync.
   */
  children?: React.ReactNode;
}

function findEnabledTabIndex(tabs: TabItem[], fromIndex: number, direction: 1 | -1): number {
  const count = tabs.length;
  let index = fromIndex;
  for (let step = 0; step < count; step += 1) {
    index = (index + direction + count) % count;
    if (!tabs[index].disabled) return index;
  }
  return -1;
}

function findEdgeEnabledTabIndex(tabs: TabItem[], edge: 'first' | 'last'): number {
  const indices =
    edge === 'first' ? tabs.map((_, i) => i) : tabs.map((_, i) => i).reverse();
  for (const index of indices) {
    if (!tabs[index].disabled) return index;
  }
  return -1;
}

export const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeId,
  onChange,
  className = '',
  panelClassName = '',
  children,
}) => {
  const baseId = useId();
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const listId = `${baseId}-tablist`;
  const tabId = (id: string) => `${baseId}-tab-${id}`;
  const panelId = (id: string) => `${baseId}-panel-${id}`;

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      const currentIndex = tabs.findIndex((tab) => tab.id === activeId);
      if (currentIndex < 0) return;

      let nextIndex = -1;
      if (event.key === 'ArrowRight') {
        nextIndex = findEnabledTabIndex(tabs, currentIndex, 1);
      } else if (event.key === 'ArrowLeft') {
        nextIndex = findEnabledTabIndex(tabs, currentIndex, -1);
      } else if (event.key === 'Home') {
        nextIndex = findEdgeEnabledTabIndex(tabs, 'first');
      } else if (event.key === 'End') {
        nextIndex = findEdgeEnabledTabIndex(tabs, 'last');
      } else {
        return;
      }

      if (nextIndex < 0) return;
      event.preventDefault();
      const nextId = tabs[nextIndex].id;
      onChange(nextId);
      window.requestAnimationFrame(() => {
        tabRefs.current[nextId]?.focus();
      });
    },
    [activeId, onChange, tabs]
  );

  const hasPanel = children !== undefined && children !== null;

  return (
    <div className={className}>
      <div className="border-b border-ops-border" role="tablist" id={listId} aria-orientation="horizontal" onKeyDown={onKeyDown}>
        <div className="flex items-center gap-6">
          {tabs.map((tab) => {
            const isActive = tab.id === activeId;
            return (
              <button
                key={tab.id}
                ref={(node) => {
                  tabRefs.current[tab.id] = node;
                }}
                type="button"
                role="tab"
                id={tabId(tab.id)}
                aria-selected={isActive}
                aria-controls={hasPanel ? panelId(tab.id) : undefined}
                tabIndex={isActive ? 0 : -1}
                disabled={tab.disabled}
                onClick={() => onChange(tab.id)}
                className={`relative h-10 text-[13px] font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ops-accent-focus focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 ${
                  isActive ? 'text-ops-accent' : 'text-ops-text-secondary hover:text-ops-text-primary'
                }`}
              >
                {tab.label}
                {isActive && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-ops-accent" />
                )}
              </button>
            );
          })}
        </div>
      </div>
      {hasPanel && (
        <div
          role="tabpanel"
          id={panelId(activeId)}
          aria-labelledby={tabId(activeId)}
          tabIndex={0}
          className={panelClassName}
        >
          {children}
        </div>
      )}
    </div>
  );
};
