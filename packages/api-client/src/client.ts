import {
  OutletPublicMenu,
  UserMe,
  TokenResponse,
  AdminOutletMenu,
  AdminMenuCategory,
  AdminMenuItem,
  AuditLogItem,
  CategoryPayload,
  ItemPayload,
  DiningTable,
  TableUpdatePayload,
  Order,
  OrderPayload,
  OrderStatus,
  PublicOrderPayload,
  PlatformBusiness,
  PlatformOutlet,
  PlatformBusinessCreatePayload,
  PlatformSubscriptionUpdatePayload,
  PlatformOutletCreatePayload,
  PlatformAssignOwnerPayload,
  PlatformAdminUser,
  PlatformAuditLogsResponse,
  PlatformBusinessEntitlementsResponse,
  PlatformBusinessOverridesResponse,
  PlatformOverrideCreatePayload,
  PlatformOverrideRevokePayload,
  PlatformOverrideInspectionItem,
  PlatformPlan,
  BusinessSubscriptionItem,
  PlatformBusinessProfileUpdatePayload,
  PlatformOutletProfileUpdatePayload,
  OwnerSubscriptionSummary,
  PlatformOperatorCreatePayload,
  PlatformOwnerTransferPayload,
  PlatformOutletDetail,
  PlatformApprovalRequestDetail,
  PlatformApprovalRequestsResponse,
  PlatformApprovalListParams,
  PlatformApprovalDecisionPayload,
} from '@roms/shared-types';


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

export async function submitPublicOrder(
  slug: string,
  payload: PublicOrderPayload,
  idempotencyKey?: string
): Promise<Order> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };

  const effectiveKey = idempotencyKey || payload.idempotency_key;
  if (effectiveKey) {
    headers['X-Idempotency-Key'] = effectiveKey;
  }

  const response = await fetch(`${API_BASE_URL}/public/outlets/${encodeURIComponent(slug)}/orders`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      ...payload,
      ...(effectiveKey ? { idempotency_key: effectiveKey } : {}),
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message =
      errorData?.detail?.error?.message ||
      errorData?.detail?.message ||
      (typeof errorData?.detail === 'string' ? errorData?.detail : null) ||
      `Failed to submit order (${response.status})`;
    const code = errorData?.detail?.error?.code || errorData?.detail?.code;
    const error = new Error(typeof message === 'string' ? message : JSON.stringify(message));
    (error as any).code = code;
    (error as any).status = response.status;
    throw error;
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
    const message =
      (typeof errorData?.detail === 'string' ? errorData.detail : errorData?.detail?.error?.message) ||
      'Invalid email or password';
    const error: any = new Error(message);
    error.status = response.status;
    error.code = errorData?.detail?.error?.code;
    throw error;
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
    const errorData = await response.json().catch(() => ({}));
    const message =
      (typeof errorData?.detail === 'string' ? errorData.detail : errorData?.detail?.error?.message) ||
      'UNAUTHORIZED';
    const error: any = new Error(message);
    error.status = response.status;
    error.code = errorData?.detail?.error?.code;
    throw error;
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

export async function updateTable(
  tableId: string,
  payload: TableUpdatePayload,
  token: string
): Promise<DiningTable> {
  const response = await fetch(`${API_BASE_URL}/tables/${tableId}`, {
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
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to update table (${response.status})`;
    throw new Error(message);
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
    const errData = await response.json().catch(() => ({}));
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to load platform businesses (${response.status})`;
    const error: any = new Error(message);
    error.status = response.status;
    error.code = errData?.detail?.error?.code;
    throw error;
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

export async function fetchPlatformPlans(token: string): Promise<PlatformPlan[]> {
  const response = await fetch(`${API_BASE_URL}/platform/plans`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message = errData?.detail?.error?.message || `Failed to fetch plans (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function fetchBusinessSubscriptions(
  businessId: string,
  token: string
): Promise<BusinessSubscriptionItem[]> {
  const response = await fetch(`${API_BASE_URL}/platform/businesses/${businessId}/subscriptions`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message = errData?.detail?.error?.message || `Failed to fetch business subscriptions (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function fetchPlatformAdmins(token: string): Promise<PlatformAdminUser[]> {
  const response = await fetch(`${API_BASE_URL}/platform/admins`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const code = errData?.detail?.error?.code;
    const message = (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) || `Failed to fetch platform admins (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function grantPlatformAdmin(userId: string, token: string): Promise<PlatformAdminUser> {
  const response = await fetch(`${API_BASE_URL}/platform/admins/${userId}/grant`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const code = errData?.detail?.error?.code;
    const message = (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) || `Failed to grant platform admin privilege (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function revokePlatformAdmin(userId: string, token: string): Promise<PlatformAdminUser> {
  const response = await fetch(`${API_BASE_URL}/platform/admins/${userId}/revoke`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const code = errData?.detail?.error?.code;
    const message = (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) || `Failed to revoke platform admin privilege (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function fetchPlatformAuditLogs(
  token: string,
  params?: {
    limit?: number;
    offset?: number;
    action?: string;
    business_id?: string;
  }
): Promise<PlatformAuditLogsResponse> {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) query.set('limit', String(params.limit));
  if (params?.offset !== undefined) query.set('offset', String(params.offset));
  if (params?.action) query.set('action', params.action);
  if (params?.business_id) query.set('business_id', params.business_id);

  const queryString = query.toString() ? `?${query.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/platform/audit-logs${queryString}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to fetch platform audit logs (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function fetchBusinessEntitlements(
  token: string,
  businessId: string,
  outletId?: string
): Promise<PlatformBusinessEntitlementsResponse> {
  const query = new URLSearchParams();
  if (outletId) query.set('outlet_id', outletId);

  const queryString = query.toString() ? `?${query.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/platform/businesses/${businessId}/entitlements${queryString}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to fetch business entitlements (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function fetchBusinessOverrides(
  token: string,
  businessId: string,
  includeExpired: boolean = true,
  includeRevoked: boolean = true
): Promise<PlatformBusinessOverridesResponse> {
  const query = new URLSearchParams();
  query.set('include_expired', String(includeExpired));
  query.set('include_revoked', String(includeRevoked));

  const response = await fetch(`${API_BASE_URL}/platform/businesses/${businessId}/overrides?${query.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to fetch business overrides (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function createBusinessOverride(
  token: string,
  businessId: string,
  payload: PlatformOverrideCreatePayload
): Promise<PlatformOverrideInspectionItem> {
  const response = await fetch(`${API_BASE_URL}/platform/businesses/${businessId}/overrides`, {
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
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to create entitlement override (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function revokeBusinessOverride(
  token: string,
  businessId: string,
  overrideId: string,
  reason: string
): Promise<{ status: string; message: string }> {
  const payload: PlatformOverrideRevokePayload = { reason };
  const response = await fetch(`${API_BASE_URL}/platform/businesses/${businessId}/overrides/${overrideId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to revoke entitlement override (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function fetchPlatformBusiness(businessId: string, token: string): Promise<PlatformBusiness> {
  const response = await fetch(`${API_BASE_URL}/platform/businesses/${businessId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to fetch business details (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function updatePlatformBusinessProfile(
  businessId: string,
  payload: PlatformBusinessProfileUpdatePayload,
  token: string
): Promise<PlatformBusiness> {
  const response = await fetch(`${API_BASE_URL}/platform/businesses/${businessId}`, {
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
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to update business profile (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function fetchPlatformOutlet(
  outletId: string,
  token: string
): Promise<PlatformOutletDetail> {
  const response = await fetch(`${API_BASE_URL}/platform/outlets/${outletId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to fetch outlet details (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function updatePlatformOutletProfile(
  outletId: string,
  payload: PlatformOutletProfileUpdatePayload,
  token: string
): Promise<PlatformOutletDetail> {
  const response = await fetch(`${API_BASE_URL}/platform/outlets/${outletId}`, {
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
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to update outlet profile (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}


// --- Owner Subscription Self-Inspection (OP-05) ---

export async function fetchOwnerSubscriptionSummary(token: string): Promise<OwnerSubscriptionSummary> {
  const response = await fetch(`${API_BASE_URL}/business/subscription`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to load subscription summary (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

// --- Platform Governance & Team Management ---

export async function fetchPlatformOperators(token: string): Promise<PlatformAdminUser[]> {
  const response = await fetch(`${API_BASE_URL}/platform/operators`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to fetch platform operators (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function createPlatformOperator(
  payload: PlatformOperatorCreatePayload,
  token: string
): Promise<PlatformAdminUser> {
  const response = await fetch(`${API_BASE_URL}/platform/operators`, {
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
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to create platform operator (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function revokePlatformOperator(userId: string, token: string): Promise<PlatformAdminUser> {
  const response = await fetch(`${API_BASE_URL}/platform/operators/${userId}/revoke`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to revoke platform operator (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function transferPlatformOwner(
  payload: PlatformOwnerTransferPayload,
  token: string
): Promise<PlatformAdminUser> {
  const response = await fetch(`${API_BASE_URL}/platform/owner/transfer`, {
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
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to transfer platform ownership (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function suspendPlatformUser(userId: string, token: string): Promise<PlatformAdminUser> {
  const response = await fetch(`${API_BASE_URL}/platform/users/${userId}/suspend`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to suspend user account (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

export async function reactivatePlatformUser(userId: string, token: string): Promise<PlatformAdminUser> {
  const response = await fetch(`${API_BASE_URL}/platform/users/${userId}/reactivate`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    const code = errData?.detail?.error?.code;
    const message =
      (typeof errData?.detail === 'string' ? errData.detail : errData?.detail?.error?.message) ||
      `Failed to reactivate user account (${response.status})`;
    const error = new Error(message) as Error & { status?: number; code?: string };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}

// --- Platform Approvals API ---

export async function fetchPlatformApprovals(
  token: string,
  params?: PlatformApprovalListParams
): Promise<PlatformApprovalRequestsResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (params?.request_type) query.set('request_type', params.request_type);
  if (params?.business_id) query.set('business_id', params.business_id);
  if (params?.limit !== undefined) query.set('limit', String(params.limit));
  if (params?.offset !== undefined) query.set('offset', String(params.offset));

  const qs = query.toString();
  const url = `${API_BASE_URL}/platform/approvals${qs ? `?${qs}` : ''}`;

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const message =
      errorData?.detail?.error?.message ||
      errorData?.detail?.message ||
      (typeof errorData?.detail === 'string' ? errorData?.detail : null) ||
      `Failed to load approvals (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function fetchPlatformApprovalDetail(
  token: string,
  requestId: string
): Promise<PlatformApprovalRequestDetail> {
  const response = await fetch(`${API_BASE_URL}/platform/approvals/${encodeURIComponent(requestId)}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Approval request not found.');
    }
    const errorData = await response.json().catch(() => ({}));
    const message =
      errorData?.detail?.error?.message ||
      errorData?.detail?.message ||
      (typeof errorData?.detail === 'string' ? errorData?.detail : null) ||
      `Failed to load approval request detail (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function decidePlatformApprovalRequest(
  token: string,
  requestId: string,
  payload: PlatformApprovalDecisionPayload
): Promise<PlatformApprovalRequestDetail> {
  const response = await fetch(`${API_BASE_URL}/platform/approvals/${encodeURIComponent(requestId)}/decide`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const code = errorData?.detail?.error?.code || (response.status === 503 ? 'COMMIT_OUTCOME_UNCERTAIN' : undefined);
    const message =
      errorData?.detail?.error?.message ||
      errorData?.detail?.message ||
      (typeof errorData?.detail === 'string' ? errorData?.detail : null) ||
      `Failed to submit decision (${response.status})`;
    const error = new Error(message);
    (error as any).status = response.status;
    (error as any).code = code;
    (error as any).details = errorData?.detail?.error?.details;
    throw error;
  }

  return response.json();
}
