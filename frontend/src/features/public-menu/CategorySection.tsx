import React from 'react';
import { MenuCategory } from '../../types/menu';
import { MenuItemCard } from './MenuItemCard';

interface CategorySectionProps {
  category: MenuCategory;
  currency: string;
  cartQuantities?: Record<string, number>;
  onAddToCart?: (item: any) => void;
  onIncrement?: (itemId: string) => void;
  onDecrement?: (itemId: string) => void;
  primaryColor?: string;
}

export const CategorySection: React.FC<CategorySectionProps> = ({
  category,
  currency,
  cartQuantities,
  onAddToCart,
  onIncrement,
  onDecrement,
  primaryColor,
}) => {
  if (category.items.length === 0) return null;

  return (
    <section id={`category-${category.id}`} className="scroll-mt-36 mb-8">
      <div className="mb-3 px-1">
        <h2 className="text-lg font-bold text-gray-900 tracking-tight">
          {category.name}
        </h2>
        {category.description && (
          <p className="text-xs text-gray-500 mt-0.5">{category.description}</p>
        )}
      </div>

      <div className="flex flex-col gap-3">
        {category.items.map((item) => (
          <MenuItemCard
            key={item.id}
            item={item}
            currency={currency}
            quantity={cartQuantities?.[item.id] || 0}
            onAddToCart={onAddToCart}
            onIncrement={onIncrement}
            onDecrement={onDecrement}
            primaryColor={primaryColor}
          />
        ))}
      </div>
    </section>
  );
};
