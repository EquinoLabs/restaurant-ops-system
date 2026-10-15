export interface OwnerPlanSummary {
  code: string;
  name: string;
  description: string | null;
}

export interface OwnerSubscriptionDetail {
  status: string;
  is_current: boolean;
  trial_ends_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

export interface OwnerOutletUsage {
  current_count: number;
  max_allowed: number | null;
  is_limit_reached: boolean;
}

export interface OwnerFeatureItem {
  code: string;
  name: string;
  category: string;
  authorized: boolean;
  limit_value: number | null;
}

export interface OwnerSupportAction {
  requires_action: boolean;
  reason: string | null;
  support_email: string;
  message: string | null;
}

export interface OwnerSubscriptionSummary {
  business_id: string;
  business_name: string;
  business_status: string;
  plan: OwnerPlanSummary;
  subscription: OwnerSubscriptionDetail;
  outlets: OwnerOutletUsage;
  features: OwnerFeatureItem[];
  support_cta: OwnerSupportAction;
}
