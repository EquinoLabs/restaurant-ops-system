export interface PlatformOutletSubscriptionUpdatePayload {
  action_type:
    | 'activate'
    | 'renew'
    | 'change_plan'
    | 'change_plan_new_term'
    | 'extend_trial'
    | 'schedule_cancellation'
    | 'revoke_scheduled_cancellation'
    | 'cancel_immediately'
    | 'mark_past_due'
    | 'mark_past_due_with_extension';
  plan_code?: string;
  plan_name?: string;
  trial_ends_at?: string | null;
  current_period_start?: string | null;
  current_period_end?: string | null;
  reason?: string;
}

export interface PlatformOutletSubscriptionResult {
  id: string;
  outlet_id: string;
  business_id: string;
  plan_id: string;
  status: string;
  is_current: boolean;
  trial_ends_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
  plan?: {
    id: string;
    code: string;
    name: string;
    tier: string;
  } | null;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export async function updatePlatformOutletSubscription(
  outletId: string,
  payload: PlatformOutletSubscriptionUpdatePayload,
  token: string
): Promise<PlatformOutletSubscriptionResult> {
  const response = await fetch(`${API_BASE_URL}/platform/outlets/${outletId}/subscription`, {
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
      errData?.detail?.error?.message ||
      errData?.detail?.message ||
      (typeof errData?.detail === 'string' ? errData.detail : null) ||
      `Failed to update outlet subscription (${response.status})`;
    const code = errData?.detail?.error?.code || errData?.detail?.code;
    const error = new Error(typeof message === 'string' ? message : JSON.stringify(message)) as Error & {
      status?: number;
      code?: string;
    };
    error.status = response.status;
    error.code = code;
    throw error;
  }

  return response.json();
}
