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
  subscription_status?: string;
  plan_name?: string | null;
  max_outlets?: number | null;
  trial_ends_at?: string | null;
  outlets: PlatformOutlet[];
  created_at: string;
  updated_at: string;
}

export interface PlatformBusinessCreatePayload {
  name: string;
  owner_email: string;
  owner_password: string;
  owner_display_name: string;
  public_slug: string;
  currency?: string;
  timezone?: string;
  address?: string;
}

export interface PlatformBusinessProfileUpdatePayload {
  name: string;
}

export interface PlatformOutletProfileUpdatePayload {
  name?: string;
  address?: string | null;
  timezone?: string;
  currency?: string;
  primary_color?: string | null;
  accent_color?: string | null;
}

export interface PlatformPlan {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface BusinessSubscriptionItem {
  id: string;
  business_id: string;
  plan_id: string;
  status: string;
  is_current: boolean;
  trial_ends_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  cancelled_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  plan: PlatformPlan | null;
}

export interface PlatformSubscriptionUpdatePayload {
  action_type?: string;
  plan_code?: string;
  plan_name?: string | null;
  subscription_status?: string;
  status?: string;
  max_outlets?: number | null;
  trial_ends_at?: string | null;
  current_period_start?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end?: boolean;
  reason?: string;
}

export interface PlatformOutletCreatePayload {
  name: string;
  public_slug: string;
  currency?: string;
  timezone?: string;
  address?: string;
  plan_code?: string;
  manager?: PlatformOutletManagerPayload | null;
}

export interface PlatformAssignOwnerPayload {
  user_id?: string;
  email?: string;
  password?: string;
  display_name?: string;
}

export interface PlatformOutletManagerPayload {
  user_id: string;
}

export type PlatformUserRole = 'owner' | 'admin' | 'operator';

export interface PlatformAdminUser {
  id: string;
  email: string;
  display_name: string;
  status: string;
  is_platform_admin: boolean;
  platform_role?: PlatformUserRole | string | null;
  created_at: string;
  updated_at: string;
}

export interface PlatformOperatorCreatePayload {
  user_id?: string;
  email?: string;
  password?: string;
  display_name?: string;
}

export interface PlatformOwnerTransferPayload {
  target_user_id: string;
  current_password: string;
}

export interface PlatformOutletDetail extends PlatformOutlet {
  business_name?: string | null;
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

export interface PlatformSubscriptionSummary {
  id: string | null;
  status: string;
  resolved_status: string;
  plan_code: string;
  plan_name: string;
  plan_is_active: boolean;
  trial_ends_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  cancelled_at: string | null;
}

export interface PlatformFeatureInspectionItem {
  feature_code: string;
  feature_name: string;
  category: string;
  authorized: boolean;
  limit_value: number | null;
  limit_type: 'none' | 'numeric' | 'unlimited';
  reason: string;
  source: string;
  scope: string;
}

export interface PlatformBusinessEntitlementsResponse {
  business_id: string;
  business_name: string;
  business_status: string;
  outlet_id: string | null;
  outlet_name: string | null;
  subscription: PlatformSubscriptionSummary;
  features: PlatformFeatureInspectionItem[];
}

export interface PlatformOverrideInspectionItem {
  id: string;
  business_id: string;
  outlet_id: string | null;
  outlet_name: string | null;
  feature_code: string;
  feature_name: string;
  override_type: 'grant' | 'restrict';
  limit_value: number | null;
  reason: string | null;
  expires_at: string | null;
  is_active: boolean;
  created_by_user_id: string | null;
  created_by_email: string | null;
  created_at: string;
}

export interface PlatformRevocationAuditItem {
  audit_log_id: string;
  revoked_override_id: string | null;
  feature_code: string | null;
  override_type: string | null;
  actor_user_id: string | null;
  actor_email: string | null;
  revoked_at: string;
  reason: string | null;
}

export interface PlatformBusinessOverridesResponse {
  business_id: string;
  overrides: PlatformOverrideInspectionItem[];
  revocation_history: PlatformRevocationAuditItem[];
}

export interface PlatformOverrideCreatePayload {
  feature_code: string;
  override_type: 'grant' | 'restrict';
  outlet_id?: string | null;
  limit_value?: number | null;
  reason: string;
  expires_at?: string | null;
}

export interface PlatformOverrideRevokePayload {
  reason: string;
}




