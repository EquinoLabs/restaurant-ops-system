import { OutletPublicMenu } from '../types/menu';
import { UserMe, TokenResponse } from '../types/auth';
import {
  AdminOutletMenu,
  AdminMenuCategory,
  AdminMenuItem,
  AuditLogItem,
  CategoryPayload,
  ItemPayload,
} from '../types/adminMenu';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// --- Public API ---

export async function fetchPublicMenu(slug: string): Promise<OutletPublicMenu> {
  const response = await fetch(`${API_BASE_URL}/public/outlets/${encodeURIComponent(slug)}/menu`, {
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('OUTLET_NOT_FOUND');
    }
    throw new Error(`Failed to load menu (${response.status})`);
  }

  return response.json();
}

// --- Auth API ---

export async function loginStaff(email: string, password: string): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message = errorData?.detail?.error?.message || 'Invalid email or password';
    throw new Error(message);
  }

  return response.json();
}

export async function fetchCurrentUser(token: string): Promise<UserMe> {
  const response = await fetch(`${API_BASE_URL}/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('UNAUTHORIZED');
  }

  return response.json();
}

// --- Admin Menu API ---

export async function fetchAdminMenu(outletId: string, token: string): Promise<AdminOutletMenu> {
  const response = await fetch(`${API_BASE_URL}/outlets/${outletId}/admin/menu`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to load administrative menu (${response.status})`);
  }

  return response.json();
}

export async function createCategory(
  outletId: string,
  payload: CategoryPayload,
  token: string
): Promise<AdminMenuCategory> {
  const response = await fetch(`${API_BASE_URL}/outlets/${outletId}/categories`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Failed to create category (${response.status})`);
  }

  return response.json();
}

export async function updateCategory(
  categoryId: string,
  payload: CategoryPayload,
  token: string
): Promise<AdminMenuCategory> {
  const response = await fetch(`${API_BASE_URL}/categories/${categoryId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Failed to update category (${response.status})`);
  }

  return response.json();
}

export async function createMenuItem(
  outletId: string,
  payload: ItemPayload,
  token: string
): Promise<AdminMenuItem> {
  const response = await fetch(`${API_BASE_URL}/outlets/${outletId}/items`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Failed to create menu item (${response.status})`);
  }

  return response.json();
}

export async function updateMenuItem(
  itemId: string,
  payload: ItemPayload,
  token: string
): Promise<AdminMenuItem> {
  const response = await fetch(`${API_BASE_URL}/items/${itemId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Failed to update menu item (${response.status})`);
  }

  return response.json();
}

export async function toggleItemAvailability(
  itemId: string,
  isAvailable: boolean,
  token: string
): Promise<AdminMenuItem> {
  const response = await fetch(`${API_BASE_URL}/items/${itemId}/availability`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ is_available: isAvailable }),
  });

  if (!response.ok) {
    throw new Error(`Failed to toggle availability (${response.status})`);
  }

  return response.json();
}

export async function fetchAuditLogs(outletId: string, token: string): Promise<AuditLogItem[]> {
  const response = await fetch(`${API_BASE_URL}/outlets/${outletId}/audit-logs`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to load audit logs (${response.status})`);
  }

  return response.json();
}
