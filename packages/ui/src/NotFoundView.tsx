import React from 'react';
import { UtensilsCrossed, AlertTriangle } from 'lucide-react';

interface NotFoundViewProps {
  message?: string;
}

export const NotFoundView: React.FC<NotFoundViewProps> = ({ message }) => {
  return (
    <div className="max-w-md mx-auto min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6 text-center">
      <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center text-amber-700 mb-4 shadow-sm">
        <UtensilsCrossed className="w-8 h-8" />
      </div>

      <h1 className="text-xl font-bold text-gray-900 mb-2">
        Menu Not Found
      </h1>
      <p className="text-sm text-gray-600 mb-6 max-w-xs leading-relaxed">
        {message || "The restaurant menu you scanned could not be found or is currently inactive. Please check with restaurant staff."}
      </p>

      <div className="inline-flex items-center gap-2 px-4 py-2 bg-amber-50 text-amber-800 text-xs font-medium rounded-lg border border-amber-200">
        <AlertTriangle className="w-4 h-4 text-amber-600" />
        Invalid or Expired QR Code
      </div>
    </div>
  );
};
