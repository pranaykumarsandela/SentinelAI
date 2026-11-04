import React from 'react';
import { Shield, Activity, RefreshCw } from 'lucide-react';

interface NavbarProps {
  systemHealth: string;
  isMockFilter?: boolean;
  onToggleMockFilter?: (val?: boolean) => void;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  systemHealth,
  isMockFilter,
  onToggleMockFilter,
  onRefresh,
  isRefreshing,
}) => {
  return (
    <header className="h-16 border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-30 px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-600/10 border border-blue-500/20 rounded-lg text-blue-500 flex items-center justify-center">
          <Shield className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-base tracking-tight text-white">SentinelAI</span>
            <span className="px-1.5 py-0.2 bg-blue-500/10 border border-blue-500/30 text-blue-400 text-[10px] font-semibold rounded">
              ENTERPRISE
            </span>
          </div>
          <span className="text-[11px] text-gray-400 block -mt-0.5">Agent Security & Evaluation Platform</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Mock Filter Toggle */}
        {onToggleMockFilter && (
          <div className="flex items-center bg-gray-900 border border-gray-800 rounded-lg p-0.5 text-xs">
            <button
              onClick={() => onToggleMockFilter(undefined)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                isMockFilter === undefined
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              All Data
            </button>
            <button
              onClick={() => onToggleMockFilter(false)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                isMockFilter === false
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Live Only
            </button>
            <button
              onClick={() => onToggleMockFilter(true)}
              className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                isMockFilter === true
                  ? 'bg-amber-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Mock Telemetry
            </button>
          </div>
        )}

        {/* Health Indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="text-gray-300 font-medium">Gateway: {systemHealth}</span>
        </div>

        {/* Refresh Button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-lg bg-gray-900 border border-gray-800 text-gray-400 hover:text-white hover:border-gray-700 transition-colors disabled:opacity-50"
            title="Refresh authentic data"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-blue-400' : ''}`} />
          </button>
        )}
      </div>
    </header>
  );
};

