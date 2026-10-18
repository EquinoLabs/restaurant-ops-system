import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import {
  Button,
  StatusBadge,
  RoleBadge,
  PageHeader,
  StatBlock,
  DataTable,
  Tabs,
  Drawer,
  ConfirmDialog,
  FormField,
  opsSelectClass,
  getFormFieldControlAriaProps,
  StateBlock,
  InlineStateBanner,
  SkeletonTable,
} from '../components/ops-ui';

describe('Button', () => {
  it('renders with primary variant styling and calls onClick', () => {
    const onClick = vi.fn();
    render(
      <Button variant="primary" onClick={onClick}>
        Save
      </Button>
    );
    const btn = screen.getByRole('button', { name: 'Save' });
    expect(btn.className).toContain('bg-ops-accent');
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('disables when disabled prop is set', () => {
    render(
      <Button variant="destructive" disabled>
        Delete
      </Button>
    );
    expect((screen.getByRole('button', { name: 'Delete' }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('StatusBadge', () => {
  it('renders label with active tone class', () => {
    render(<StatusBadge tone="active" label="Active" />);
    const badge = screen.getByText('Active');
    expect(badge.className).toContain('bg-ops-status-active-bg');
    expect(badge.className).toContain('text-ops-status-active-text');
  });

  it('renders critical tone class', () => {
    render(<StatusBadge tone="critical" label="Suspended" />);
    expect(screen.getByText('Suspended').className).toContain('bg-ops-status-critical-bg');
  });

  it('renders pending tone class', () => {
    render(<StatusBadge tone="pending" label="Trial" />);
    expect(screen.getByText('Trial').className).toContain('bg-ops-status-pending-bg');
  });
});

describe('RoleBadge', () => {
  it('renders neutral-styled role label', () => {
    render(<RoleBadge label="Viewer" />);
    const badge = screen.getByText('Viewer');
    expect(badge.className).toContain('bg-ops-status-neutral-bg');
    expect(badge.className).toContain('text-ops-status-neutral-text');
  });
});

describe('PageHeader', () => {
  it('renders title, description, and action', () => {
    render(
      <PageHeader
        title="Businesses"
        description="Manage customer businesses"
        action={<button type="button">Add business</button>}
      />
    );
    expect(screen.getByRole('heading', { name: 'Businesses' })).toBeTruthy();
    expect(screen.getByText('Manage customer businesses')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Add business' })).toBeTruthy();
  });

  it('omits description when not provided', () => {
    render(<PageHeader title="Plans" />);
    expect(screen.getByRole('heading', { name: 'Plans' })).toBeTruthy();
    expect(screen.queryByText(/Manage/i)).toBeNull();
  });
});

describe('StatBlock', () => {
  it('renders caption, value, and optional badge at 20px metric size', () => {
    render(<StatBlock caption="Total businesses" value={42} badge={<span>+4</span>} />);
    expect(screen.getByText('Total businesses')).toBeTruthy();
    const value = screen.getByText('42');
    expect(value.className).toContain('text-xl');
    expect(value.className).not.toContain('text-2xl');
    expect(value.className).toContain('tabular-nums');
    expect(screen.getByText('+4')).toBeTruthy();
  });
});

describe('DataTable', () => {
  interface Row {
    id: string;
    name: string;
    count: number;
  }

  const columns = [
    { key: 'name', header: 'Name', render: (r: Row) => r.name },
    { key: 'count', header: 'Outlets', align: 'right' as const, render: (r: Row) => r.count },
  ];

  const rows: Row[] = [
    { id: 'b1', name: 'Acme', count: 3 },
    { id: 'b2', name: 'Globex', count: 5 },
  ];

  it('renders rows, headers, and footer', () => {
    render(
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        footer={<span>Showing 2 businesses</span>}
      />
    );
    expect(screen.getByText('Name')).toBeTruthy();
    expect(screen.getByText('Outlets')).toBeTruthy();
    expect(screen.getByText('Acme')).toBeTruthy();
    expect(screen.getByText('Globex')).toBeTruthy();
    expect(screen.getByText('Showing 2 businesses')).toBeTruthy();
  });

  it('right-aligns numeric column cells', () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);
    const rightCell = screen.getByText('3');
    expect(rightCell.className).toContain('text-right');
    expect(rightCell.className).toContain('tabular-nums');
  });

  it('marks column headers with scope="col"', () => {
    const { container } = render(
      <DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />
    );
    const headers = container.querySelectorAll('th');
    expect(headers.length).toBe(2);
    headers.forEach((th) => {
      expect(th.getAttribute('scope')).toBe('col');
    });
  });

  it('supports explicit tabular numerals and single-line truncation on name-like columns with native title', () => {
    const customCols = [
      {
        key: 'name',
        header: 'Tenant Name',
        truncateName: true,
        getTitle: (r: Row) => `Full Tenant Name: ${r.name}`,
        render: (r: Row) => r.name,
      },
      { key: 'created', header: 'Created', tabular: true, render: () => '14 Oct 2026' },
      { key: 'notes', header: 'Notes', render: () => 'Regular wrapped description text' },
    ];
    render(<DataTable columns={customCols} rows={rows} rowKey={(r) => r.id} />);
    const nameCell = screen.getByText('Acme').closest('td');
    expect(nameCell?.className).toContain('truncate');
    expect(nameCell?.className).toContain('max-w-[240px]');
    expect(nameCell?.getAttribute('title')).toBe('Full Tenant Name: Acme');

    const dateCell = screen.getAllByText('14 Oct 2026')[0].closest('td');
    expect(dateCell?.className).toContain('tabular-nums');
    expect(dateCell?.getAttribute('title')).toBeNull();

    const notesCell = screen.getAllByText('Regular wrapped description text')[0].closest('td');
    expect(notesCell?.className).not.toContain('truncate');
    expect(notesCell?.getAttribute('title')).toBeNull();
  });
});

function ControlledTabsWithPanel() {
  const [activeId, setActiveId] = useState('overview');
  return (
    <Tabs
      tabs={[
        { id: 'overview', label: 'Overview' },
        { id: 'outlets', label: 'Outlets' },
      ]}
      activeId={activeId}
      onChange={setActiveId}
    >
      <p>Panel for {activeId}</p>
    </Tabs>
  );
}

describe('Tabs', () => {
  it('renders tabs and switches active id', () => {
    const onChange = vi.fn();
    const tabs = [
      { id: 'overview', label: 'Overview' },
      { id: 'outlets', label: 'Outlets' },
    ];
    render(<Tabs tabs={tabs} activeId="overview" onChange={onChange} />);
    fireEvent.click(screen.getByRole('tab', { name: 'Outlets' }));
    expect(onChange).toHaveBeenCalledWith('outlets');
  });

  it('marks selected tab with aria-selected and roving tabIndex', () => {
    render(
      <Tabs
        tabs={[
          { id: 'a', label: 'A' },
          { id: 'b', label: 'B' },
        ]}
        activeId="a"
        onChange={() => {}}
      />
    );
    const tabA = screen.getByRole('tab', { name: 'A' });
    const tabB = screen.getByRole('tab', { name: 'B' });
    expect(tabA.getAttribute('aria-selected')).toBe('true');
    expect(tabA.getAttribute('tabindex')).toBe('0');
    expect(tabB.getAttribute('aria-selected')).toBe('false');
    expect(tabB.getAttribute('tabindex')).toBe('-1');
  });

  it('associates tabs with panel via aria-controls and aria-labelledby', () => {
    render(<ControlledTabsWithPanel />);
    const overviewTab = screen.getByRole('tab', { name: 'Overview' });
    const panel = screen.getByRole('tabpanel');
    expect(overviewTab.getAttribute('aria-controls')).toBe(panel.id);
    expect(panel.getAttribute('aria-labelledby')).toBe(overviewTab.id);
    expect(panel.textContent).toContain('Panel for overview');
  });

  it('moves selection and focus with ArrowRight, ArrowLeft, Home, and End', async () => {
    render(<ControlledTabsWithPanel />);
    const list = screen.getByRole('tablist');
    const overviewTab = screen.getByRole('tab', { name: 'Overview' });
    overviewTab.focus();

    fireEvent.keyDown(list, { key: 'ArrowRight' });
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Outlets' }));
    });
    expect(screen.getByRole('tabpanel').textContent).toContain('Panel for outlets');

    fireEvent.keyDown(list, { key: 'ArrowLeft' });
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Overview' }));
    });

    fireEvent.keyDown(list, { key: 'End' });
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Outlets' }));
    });

    fireEvent.keyDown(list, { key: 'Home' });
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Overview' }));
    });
  });

  it('skips disabled tabs during arrow navigation', async () => {
    function WithDisabled() {
      const [activeId, setActiveId] = useState('a');
      return (
        <Tabs
          tabs={[
            { id: 'a', label: 'A' },
            { id: 'b', label: 'B', disabled: true },
            { id: 'c', label: 'C' },
          ]}
          activeId={activeId}
          onChange={setActiveId}
        />
      );
    }
    render(<WithDisabled />);
    const list = screen.getByRole('tablist');
    screen.getByRole('tab', { name: 'A' }).focus();
    fireEvent.keyDown(list, { key: 'ArrowRight' });
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'C' }));
    });
  });
});

function DrawerHarness({ initiallyOpen = false }: { initiallyOpen?: boolean }) {
  const [open, setOpen] = useState(initiallyOpen);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Open drawer
      </button>
      <Drawer open={open} onClose={() => setOpen(false)} title="Edit subscription">
        <button type="button">Inner action</button>
      </Drawer>
    </div>
  );
}

describe('Drawer', () => {
  it('renders nothing when closed', () => {
    render(
      <Drawer open={false} onClose={() => {}} title="Subscription">
        Content
      </Drawer>
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders open drawer with title, subtitle, body, and footer', () => {
    render(
      <Drawer
        open
        onClose={() => {}}
        title="Edit subscription"
        subtitle="Acme"
        footer={<button type="button">Save</button>}
      >
        <p>Drawer body</p>
      </Drawer>
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog.className).toContain('animate-ops-drawer-enter');
    expect(dialog.className).toContain('motion-reduce:animate-none');
    expect(screen.getByText('Edit subscription')).toBeTruthy();
    expect(screen.getByText('Acme')).toBeTruthy();
    expect(screen.getByText('Drawer body')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Save' })).toBeTruthy();
  });

  it('associates accessible name with visible heading via aria-labelledby', () => {
    render(
      <Drawer open onClose={() => {}} title="Edit subscription">
        Body
      </Drawer>
    );
    const dialog = screen.getByRole('dialog');
    const labelledBy = dialog.getAttribute('aria-labelledby');
    expect(labelledBy).toBeTruthy();
    const heading = document.getElementById(labelledBy as string);
    expect(heading).toBeTruthy();
    expect(heading?.textContent).toBe('Edit subscription');
  });

  it('invokes onClose on Escape', () => {
    const onClose = vi.fn();
    render(
      <Drawer open onClose={onClose} title="Panel">
        Body
      </Drawer>
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('closes when the scrim is clicked', () => {
    const onClose = vi.fn();
    const { container } = render(
      <Drawer open onClose={onClose} title="Panel">
        Body
      </Drawer>
    );
    const scrim = container.querySelector('.fixed.inset-0.z-40');
    expect(scrim).toBeTruthy();
    fireEvent.click(scrim as Element);
    expect(onClose).toHaveBeenCalled();
  });

  it('moves focus into the dialog and restores focus on close', async () => {
    render(<DrawerHarness />);
    const trigger = screen.getByRole('button', { name: 'Open drawer' });
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    fireEvent.click(trigger);
    await waitFor(() => {
      const dialog = screen.getByRole('dialog');
      expect(dialog.contains(document.activeElement)).toBe(true);
    });

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
    });
    expect(document.activeElement).toBe(trigger);
  });

  it('contains Tab focus within the open dialog', async () => {
    render(<DrawerHarness initiallyOpen />);
    const dialog = await screen.findByRole('dialog');
    await waitFor(() => {
      expect(dialog.contains(document.activeElement)).toBe(true);
    });

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(dialog.contains(document.activeElement)).toBe(true);

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(dialog.contains(document.activeElement)).toBe(true);
  });
});

describe('ConfirmDialog', () => {
  const baseProps = {
    open: true,
    onClose: () => {},
    onConfirm: vi.fn(),
    title: 'Suspend operator',
    consequence: 'This operator will lose access.',
    confirmLabel: 'Suspend operator',
    confirmationName: 'sarah.chen@northwind.app',
  };

  it('keeps destructive confirm disabled until exact name is typed', () => {
    render(<ConfirmDialog {...baseProps} />);
    const confirmBtn = screen.getByRole('button', {
      name: 'Suspend operator',
    }) as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText(/To confirm, type:/i), {
      target: { value: 'sarah.chen@northwind.app' },
    });
    expect(confirmBtn.disabled).toBe(false);
  });

  it('stays disabled for partial or wrong name', () => {
    render(<ConfirmDialog {...baseProps} />);
    const confirmBtn = screen.getByRole('button', {
      name: 'Suspend operator',
    }) as HTMLButtonElement;
    fireEvent.change(screen.getByLabelText(/To confirm, type:/i), {
      target: { value: 'sarah.chen@northwind.a' },
    });
    expect(confirmBtn.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/To confirm, type:/i), {
      target: { value: 'wrong@name.app' },
    });
    expect(confirmBtn.disabled).toBe(true);
  });

  it('resets typed value when reopened', () => {
    const { rerender } = render(<ConfirmDialog {...baseProps} />);
    fireEvent.change(screen.getByLabelText(/To confirm, type:/i), {
      target: { value: 'sarah.chen@northwind.app' },
    });
    expect(
      (screen.getByLabelText(/To confirm, type:/i) as HTMLInputElement).value
    ).toBe('sarah.chen@northwind.app');

    rerender(<ConfirmDialog {...baseProps} open={false} />);
    rerender(<ConfirmDialog {...baseProps} />);
    expect(
      (screen.getByLabelText(/To confirm, type:/i) as HTMLInputElement).value
    ).toBe('');
  });

  it('calls onConfirm when exact name is typed and confirmed', () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...baseProps} onConfirm={onConfirm} />);
    fireEvent.change(screen.getByLabelText(/To confirm, type:/i), {
      target: { value: 'sarah.chen@northwind.app' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Suspend operator' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('shows error message when provided', () => {
    render(<ConfirmDialog {...baseProps} errorMessage="Could not suspend operator" />);
    expect(screen.getByText('Could not suspend operator')).toBeTruthy();
    expect(
      document.querySelector('[role="alert"]')?.textContent
    ).toContain('Could not suspend operator');
  });

  it('invokes onClose from Cancel', () => {
    const onClose = vi.fn();
    render(<ConfirmDialog {...baseProps} onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('invokes onClose on Escape when not submitting', () => {
    const onClose = vi.fn();
    render(<ConfirmDialog {...baseProps} onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('blocks Escape and dismissal while submitting; shows Working… label', () => {
    const onClose = vi.fn();
    render(<ConfirmDialog {...baseProps} onClose={onClose} isSubmitting />);
    const confirmBtn = screen.getByRole('button', { name: 'Working…' }) as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('associates accessible name with visible heading and applies enter animation classes', () => {
    render(<ConfirmDialog {...baseProps} />);
    const dialog = screen.getByRole('alertdialog');
    const labelledBy = dialog.getAttribute('aria-labelledby');
    expect(labelledBy).toBeTruthy();
    expect(dialog.className).toContain('animate-ops-dialog-enter');
    expect(dialog.className).toContain('motion-reduce:animate-none');
    const heading = document.getElementById(labelledBy as string);
    expect(heading?.textContent).toBe('Suspend operator');
  });

  it('moves focus into the typed-name input and restores focus on close', async () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <div>
          <button type="button" onClick={() => setOpen(true)}>
            Open confirm
          </button>
          <ConfirmDialog
            {...baseProps}
            open={open}
            onClose={() => setOpen(false)}
          />
        </div>
      );
    }
    render(<Harness />);
    const trigger = screen.getByRole('button', { name: 'Open confirm' });
    trigger.focus();

    fireEvent.click(trigger);
    await waitFor(() => {
      expect(document.activeElement).toBe(screen.getByLabelText(/To confirm, type:/i));
    });

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('alertdialog')).toBeNull();
    });
    expect(document.activeElement).toBe(trigger);
  });

  it('contains Tab focus within the open dialog', async () => {
    render(<ConfirmDialog {...baseProps} />);
    const dialog = screen.getByRole('alertdialog');
    await waitFor(() => {
      expect(dialog.contains(document.activeElement)).toBe(true);
    });

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(dialog.contains(document.activeElement)).toBe(true);

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it('does not dismiss when the scrim is clicked', () => {
    const onClose = vi.fn();
    render(<ConfirmDialog {...baseProps} onClose={onClose} />);
    const scrim = document.querySelector('.fixed.inset-0.z-50.bg-\\[rgba\\(31\\,41\\,51\\,0\\.40\\)\\]');
    expect(scrim).toBeTruthy();
    fireEvent.click(scrim as Element);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe('FormField', () => {
  it('renders label, hint, and input association', () => {
    render(
      <FormField id="biz-name" label="Business name" hint="Shown to the customer">
        <input id="biz-name" />
      </FormField>
    );
    expect(screen.getByLabelText('Business name')).toBeTruthy();
    expect(screen.getByText('Shown to the customer')).toBeTruthy();
  });

  it('auto-wires hint association onto a single child control', () => {
    render(
      <FormField id="biz-name" label="Business name" hint="Shown to the customer">
        <input id="biz-name" />
      </FormField>
    );
    const input = screen.getByLabelText('Business name') as HTMLInputElement;
    expect(input.getAttribute('aria-describedby')).toBe('biz-name-hint');
    expect(input.getAttribute('aria-invalid')).toBeNull();
  });

  it('auto-wires error association and aria-invalid when error is present', () => {
    render(
      <FormField id="biz-name" label="Business name" hint="Hint" error="Required field">
        <input id="biz-name" />
      </FormField>
    );
    const input = screen.getByLabelText('Business name') as HTMLInputElement;
    expect(screen.getByRole('alert').textContent).toBe('Required field');
    expect(screen.queryByText('Hint')).toBeNull();
    expect(input.getAttribute('aria-describedby')).toBe('biz-name-error');
    expect(input.getAttribute('aria-invalid')).toBe('true');
  });

  it('exposes getFormFieldControlAriaProps for non-cloned consumers', () => {
    const props = getFormFieldControlAriaProps('biz-name', {
      hint: 'Hint only',
      error: null,
    });
    expect(props.id).toBe('biz-name');
    expect(props['aria-describedby']).toBe('biz-name-hint');
    expect(props['aria-invalid']).toBeUndefined();

    const invalid = getFormFieldControlAriaProps('biz-name', { error: 'Required' });
    expect(invalid['aria-describedby']).toBe('biz-name-error');
    expect(invalid['aria-invalid']).toBe(true);
  });

  it('renders label with 12px weight 500 (font-medium) text-ops-text-secondary', () => {
    render(
      <FormField id="test-field" label="Field label">
        <input id="test-field" />
      </FormField>
    );
    const label = screen.getByText('Field label');
    expect(label.className).toContain('text-xs');
    expect(label.className).toContain('font-medium');
    expect(label.className).toContain('text-ops-text-secondary');
  });

  it('provides opsSelectClass with custom SVG chevron and 32px height', () => {
    expect(opsSelectClass).toContain('h-8');
    expect(opsSelectClass).toContain('rounded-md');
    expect(opsSelectClass).toContain('border-ops-border');
    expect(opsSelectClass).toContain('appearance-none');
    expect(opsSelectClass).toContain('background-image');
  });
});

describe('StateBlock', () => {
  it('renders loading state', () => {
    render(<StateBlock variant="loading" />);
    expect(screen.getByText('Loading…')).toBeTruthy();
    expect(document.querySelector('[data-state-variant="loading"]')).toBeTruthy();
  });

  it('renders empty state', () => {
    render(<StateBlock variant="empty" />);
    expect(screen.getByText('Nothing here yet')).toBeTruthy();
  });

  it('renders no-results with clear filters action', () => {
    const onAction = vi.fn();
    render(<StateBlock variant="no-results" onAction={onAction} />);
    expect(screen.getByText('No results match your filters')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it('renders error with retry action', () => {
    const onAction = vi.fn();
    render(<StateBlock variant="error" onAction={onAction} />);
    expect(screen.getByText('Something went wrong')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it('renders permission-denied copy without inventing extra fields', () => {
    render(<StateBlock variant="permission-denied" />);
    expect(screen.getByText("You don't have access to this page")).toBeTruthy();
    expect(
      screen.getByText(/Contact the Platform Owner to request access/i)
    ).toBeTruthy();
  });

  it('renders not-found state', () => {
    render(<StateBlock variant="not-found" />);
    expect(screen.getByText('Record not found')).toBeTruthy();
  });

  it('renders conflict with required copy', () => {
    const onAction = vi.fn();
    render(<StateBlock variant="conflict" onAction={onAction} />);
    expect(screen.getByText('This record changed')).toBeTruthy();
    expect(screen.getByText('Reload to see the latest.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Reload' }));
    expect(onAction).toHaveBeenCalled();
  });

  it('renders unknown-outcome with non-failure copy', () => {
    render(<StateBlock variant="unknown-outcome" />);
    expect(screen.getByText('Checking current state…')).toBeTruthy();
    expect(screen.queryByText(/failed/i)).toBeNull();
  });

  it('accepts custom title and description overrides', () => {
    render(
      <StateBlock
        variant="empty"
        title="No businesses yet"
        description="Create your first business to get started."
      />
    );
    expect(screen.getByText('No businesses yet')).toBeTruthy();
    expect(screen.getByText('Create your first business to get started.')).toBeTruthy();
  });
});

describe('InlineStateBanner', () => {
  it('renders conflict banner with action', () => {
    render(
      <InlineStateBanner
        variant="conflict"
        message="This record changed. Reload to see the latest."
        action={<button type="button">Reload</button>}
      />
    );
    expect(
      screen.getByText('This record changed. Reload to see the latest.')
    ).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Reload' })).toBeTruthy();
  });

  it('renders unknown-outcome without failure wording', () => {
    render(<InlineStateBanner variant="unknown-outcome" message="Checking current state…" />);
    expect(screen.getByText('Checking current state…')).toBeTruthy();
    expect(screen.queryByText(/failed/i)).toBeNull();
  });

  it('uses alert role for error variant', () => {
    render(<InlineStateBanner variant="error" message="Could not load data" />);
    expect(document.querySelector('[data-inline-state="error"]')?.getAttribute('role')).toBe('alert');
  });
});

describe('SkeletonTable', () => {
  it('renders fixed number of skeleton rows', () => {
    const { container } = render(<SkeletonTable rows={3} />);
    expect(screen.getByTestId('skeleton-table')).toBeTruthy();
    expect(container.querySelectorAll('div.h-10').length).toBe(3);
  });
});
