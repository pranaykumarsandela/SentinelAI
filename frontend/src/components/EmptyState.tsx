import React from 'react';
import { Database, AlertCircle } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionLabel,
  onAction,
  icon,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-10 border border-dashed border-gray-800 rounded-xl bg-gray-900/40 text-center my-4">
      <div className="p-3 bg-gray-800/80 rounded-full text-gray-400 mb-4">
        {icon || <Database className="w-8 h-8" />}
      </div>
      <h3 className="text-lg font-semibold text-gray-200 mb-1">{title}</h3>
      <p className="text-sm text-gray-400 max-w-md mb-6">{description}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
        >
          {actionLabel}
        </button>
      )}
      <div className="mt-4 flex items-center text-xs text-gray-500 gap-1.5">
        <AlertCircle className="w-3.5 h-3.5" />
        <span>Mandatory Data Integrity Policy: zero synthetic values generated.</span>
      </div>
    </div>
  );
};

