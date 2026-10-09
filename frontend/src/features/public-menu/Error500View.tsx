import React from 'react';
import { ServerCrash, RefreshCw } from 'lucide-react';

interface Error500ViewProps {
  onRetry?: () => void;
  message?: string;
}

export const Error500View: React.FC<Error500ViewProps> = ({ onRetry, message }) => {
  return (
    <div className="max-w-md mx-auto min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6 text-center">
      <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center text-red-600 mb-4 shadow-sm">
        <ServerCrash className="w-8 h-8" />
      </div>

      <h1 className="text-xl font-bold text-gray-900 mb-2">
        System Temporarily Unavailable
      </h1>
      <p className="text-sm text-gray-600 mb-6 max-w-xs leading-relaxed">
        {message || "We encountered a temporary server or network issue while fetching the menu. Please check your internet connection or try again."}
      </p>

      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-xl transition-all shadow-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Try Again
        </button>
      )}
    </div>
  );
};
