export interface AdminMenuItem {
  id: string;
  outlet_id: string;
  category_id: string;
  name: string;
  description: string | null;
  price: number | string;
  image_url: string | null;
  is_available: boolean;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface AdminMenuCategory {
  id: string;
  outlet_id: string;
  name: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
  items: AdminMenuItem[];
  created_at: string;
  updated_at: string;
}

export interface AdminOutletMenu {
  outlet_id: string;
  outlet_name: string;
  public_slug: string;
  business_id: string;
  currency: string;
  categories: AdminMenuCategory[];
}

export interface AuditLogItem {
  id: string;
  actor_user_id: string | null;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  metadata_json: Record<string, any> | null;
  created_at: string;
}

export interface CategoryPayload {
  name: string;
  description?: string | null;
  sort_order?: number;
  is_active?: boolean;
}

export interface ItemPayload {
  category_id?: string;
  name?: string;
  description?: string | null;
  price?: number | string;
  image_url?: string | null;
  is_available?: boolean;
  is_active?: boolean;
  sort_order?: number;
}
