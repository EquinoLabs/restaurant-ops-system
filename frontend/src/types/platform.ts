export interface PlatformOutlet {
  id: string;
  business_id: string;
  name: string;
  public_slug: string;
  currency: string;
  timezone: string;
  address: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface PlatformBusiness {
  id: string;
  name: string;
  status: string;
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
