export interface MenuItem {
  id: string;
  name: string;
  description: string | null;
  price: number;
  image_url: string | null;
  is_available: boolean;
  sort_order: number;
}

export interface MenuCategory {
  id: string;
  name: string;
  description: string | null;
  sort_order: number;
  items: MenuItem[];
}

export interface OutletPublicMenu {
  outlet_id: string;
  outlet_name: string;
  public_slug: string;
  currency: string;
  timezone: string;
  address: string | null;
  categories: MenuCategory[];
}

export interface APIErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
