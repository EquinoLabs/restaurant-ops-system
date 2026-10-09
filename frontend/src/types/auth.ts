export interface OutletMembership {
  outlet_id: string;
  outlet_name: string;
  public_slug: string;
  business_id: string;
  business_name: string;
  role: string;
}

export interface UserMe {
  id: string;
  email: string;
  display_name: string;
  status: string;
  memberships: OutletMembership[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
