export type TableStatus = 'available' | 'occupied' | 'reserved';

export interface DiningTable {
  id: string;
  outlet_id: string;
  table_number: string;
  capacity: number;
  status: TableStatus;
  created_at: string;
  updated_at: string;
}

export type OrderStatus =
  | 'pending'
  | 'confirmed'
  | 'in_kitchen'
  | 'served'
  | 'completed'
  | 'cancelled';

export interface OrderItem {
  id: string;
  menu_item_id: string | null;
  item_name: string;
  unit_price: number | string;
  quantity: number;
  subtotal: number | string;
  special_instructions: string | null;
}

export interface Order {
  id: string;
  outlet_id: string;
  table_id: string | null;
  table_number: string | null;
  waiter_user_id: string | null;
  waiter_name: string | null;
  order_number: string;
  status: OrderStatus;
  order_type: string;
  total_amount: number | string;
  notes: string | null;
  items: OrderItem[];
  created_at: string;
  updated_at: string;
}

export interface OrderItemPayload {
  menu_item_id: string;
  quantity: number;
  special_instructions?: string | null;
}

export interface OrderPayload {
  table_id?: string | null;
  order_type?: string;
  items: OrderItemPayload[];
  notes?: string | null;
}
