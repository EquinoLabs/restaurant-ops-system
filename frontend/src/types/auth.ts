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
  is_platform_admin?: boolean;
  memberships: OutletMembership[];
}


export interface TokenResponse {
  access_token: string;
  token_type: string;
}
