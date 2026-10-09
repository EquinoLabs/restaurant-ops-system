import React from 'react';

export const MenuSkeleton: React.FC = () => {
  return (
    <div className="max-w-md mx-auto min-h-screen bg-gray-50 p-4 space-y-6 animate-pulse">
      {/* Header Skeleton */}
      <div className="bg-white p-5 rounded-2xl shadow-sm space-y-3">
        <div className="h-6 bg-gray-200 rounded-md w-3/4"></div>
        <div className="h-4 bg-gray-100 rounded-md w-1/2"></div>
      </div>

      {/* Categories Tabs Skeleton */}
      <div className="flex gap-2 overflow-x-hidden">
        <div className="h-8 bg-gray-200 rounded-full w-24 flex-shrink-0"></div>
        <div className="h-8 bg-gray-200 rounded-full w-28 flex-shrink-0"></div>
        <div className="h-8 bg-gray-200 rounded-full w-20 flex-shrink-0"></div>
      </div>

      {/* Menu Cards Skeleton */}
      <div className="space-y-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white p-4 rounded-xl border border-gray-100 flex gap-4">
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-gray-200 rounded w-2/3"></div>
              <div className="h-3 bg-gray-100 rounded w-full"></div>
              <div className="h-4 bg-amber-100 rounded w-1/4 mt-4"></div>
            </div>
            <div className="w-20 h-20 bg-gray-200 rounded-lg flex-shrink-0"></div>
          </div>
        ))}
      </div>
    </div>
  );
};
