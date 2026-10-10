export interface PlatformOutlet {
  id: string;
  business_id: string;
  name: string;
  public_slug: string;
  currency: string;
  timezone: string;
  address: string | null;
  status: string;
  logo_url?: string | null;
  cover_image_url?: string | null;
  primary_color?: string | null;
  accent_color?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlatformBusiness {
  id: string;
  name: string;
  status: string;
  subscription_status: string;
  plan_name: string | null;
  max_outlets: number | null;
  trial_ends_at: string | null;
  outlets: PlatformOutlet[];
  created_at: string;
  updated_at: string;
}

export interface PlatformBusinessCreatePayload {
  name: string;
  primary_outlet_name: string;
  public_slug: string;
  currency?: string;
  timezone?: string;
  address?: string;
  subscription_status?: string;
  plan_name?: string;
  max_outlets?: number | null;
  trial_ends_at?: string | null;
}

export interface PlatformSubscriptionUpdatePayload {
  subscription_status?: string;
  status?: string;
  plan_name?: string | null;
  max_outlets?: number | null;
  trial_ends_at?: string | null;
}

export interface PlatformOutletCreatePayload {
  name: string;
  public_slug: string;
  currency?: string;
  timezone?: string;
  address?: string;
}

export interface PlatformAssignOwnerPayload {
  outlet_id: string;
  user_id?: string;
  email?: string;
  password?: string;
  display_name?: string;
}

export interface PlatformAdminUser {
  id: string;
  email: string;
  display_name: string;
  status: string;
  is_platform_admin: boolean;
  created_at: string;
  updated_at: string;
}

export interface PlatformAuditLogItem {
  id: string;
  business_id: string | null;
  business_name: string | null;
  outlet_id: string | null;
  outlet_name: string | null;
  actor_user_id: string | null;
  actor_display_name: string | null;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  metadata_json: Record<string, any> | null;
  created_at: string;
}

export interface PlatformAuditLogsResponse {
  items: PlatformAuditLogItem[];
  total: number;
  limit: number;
  offset: number;
}


