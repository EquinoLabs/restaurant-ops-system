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
import { DiningTable, Order, OrderPayload, OrderStatus } from '../types/orders';
import {
  PlatformBusiness,
  PlatformOutlet,
  PlatformBusinessCreatePayload,
  PlatformSubscriptionUpdatePayload,
  PlatformOutletCreatePayload,
  PlatformAssignOwnerPayload,
} from '../types/platform';


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

export async function uploadItemImage(
  outletId: string,
  itemId: string,
  file: File,
  token: string
): Promise<AdminMenuItem> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/outlets/${outletId}/items/${itemId}/image`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
    body: formData,
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message = errData?.detail?.error?.message || `Failed to upload image (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function deleteItemImage(
  outletId: string,
  itemId: string,
  token: string
): Promise<AdminMenuItem> {
  const response = await fetch(`${API_BASE_URL}/outlets/${outletId}/items/${itemId}/image`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message = errData?.detail?.error?.message || `Failed to delete image (${response.status})`;
    throw new Error(message);
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

// --- Tables & Staff Orders API ---

export async function fetchOutletTables(outletId: string, token: string): Promise<DiningTable[]> {
  const response = await fetch(`${API_BASE_URL}/outlets/${outletId}/tables`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to load dining tables (${response.status})`);
  }

  return response.json();
}

export async function createTable(
  outletId: string,
  tableNumber: string,
  capacity: number,
  token: string
): Promise<DiningTable> {
  const response = await fetch(`${API_BASE_URL}/outlets/${outletId}/tables`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ table_number: tableNumber, capacity }),
  });

  if (!response.ok) {
    throw new Error(`Failed to create table (${response.status})`);
  }

  return response.json();
}

export async function fetchOutletOrders(
  outletId: string,
  token: string,
  status?: string
): Promise<Order[]> {
  const url = status
    ? `${API_BASE_URL}/outlets/${outletId}/orders?status=${encodeURIComponent(status)}`
    : `${API_BASE_URL}/outlets/${outletId}/orders`;

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to load orders (${response.status})`);
  }

  return response.json();
}

export async function createOrder(
  outletId: string,
  payload: OrderPayload,
  token: string
): Promise<Order> {
  const response = await fetch(`${API_BASE_URL}/outlets/${outletId}/orders`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message = errData?.detail?.error?.message || `Failed to create order (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function updateOrderStatus(
  orderId: string,
  status: OrderStatus,
  token: string
): Promise<Order> {
  const response = await fetch(`${API_BASE_URL}/orders/${orderId}/status`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ status }),
  });

  if (!response.ok) {
    throw new Error(`Failed to update order status (${response.status})`);
  }

  return response.json();
}

// --- Platform Admin API ---

export async function fetchPlatformBusinesses(token: string): Promise<PlatformBusiness[]> {
  const response = await fetch(`${API_BASE_URL}/platform/businesses`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to load platform businesses (${response.status})`);
  }

  return response.json();
}

export async function createPlatformBusiness(
  payload: PlatformBusinessCreatePayload,
  token: string
): Promise<PlatformBusiness> {
  const response = await fetch(`${API_BASE_URL}/platform/businesses`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message = errData?.detail?.error?.message || `Failed to create business (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function createPlatformOutlet(
  businessId: string,
  payload: PlatformOutletCreatePayload,
  token: string
): Promise<PlatformOutlet> {
  const response = await fetch(`${API_BASE_URL}/platform/businesses/${businessId}/outlets`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message = errData?.detail?.error?.message || `Failed to create outlet (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function assignPlatformOwner(
  businessId: string,
  payload: PlatformAssignOwnerPayload,
  token: string
): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/platform/businesses/${businessId}/assign-owner`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message = errData?.detail?.error?.message || `Failed to assign owner (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function updatePlatformSubscription(
  businessId: string,
  payload: PlatformSubscriptionUpdatePayload,
  token: string
): Promise<PlatformBusiness> {
  const response = await fetch(`${API_BASE_URL}/platform/businesses/${businessId}/subscription`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message = errData?.detail?.error?.message || `Failed to update business subscription (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}


