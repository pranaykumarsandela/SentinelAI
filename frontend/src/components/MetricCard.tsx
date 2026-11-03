import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number | null;
  unit?: string;
  subtitle?: string;
  icon?: React.ReactNode;
  badge?: string;
  badgeColor?: 'blue' | 'green' | 'amber' | 'red' | 'gray';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  subtitle,
  icon,
  badge,
  badgeColor = 'blue',
}) => {
  const badgeClasses = {
    blue: 'bg-blue-900/40 text-blue-400 border-blue-800',
    green: 'bg-emerald-900/40 text-emerald-400 border-emerald-800',
    amber: 'bg-amber-900/40 text-amber-400 border-amber-800',
    red: 'bg-rose-900/40 text-rose-400 border-rose-800',
    gray: 'bg-gray-800 text-gray-400 border-gray-700',
  }[badgeColor];

  const displayValue = value === null || value === undefined ? 'N/A' : value;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-sm hover:border-gray-700 transition-all">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium uppercase tracking-wider text-gray-400">{title}</span>
        {icon && <div className="text-gray-400">{icon}</div>}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold tracking-tight text-white">{displayValue}</span>
        {unit && value !== null && <span className="text-sm font-medium text-gray-400">{unit}</span>}
      </div>
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-800/60 text-xs text-gray-400">
        <span>{subtitle || 'Persisted DB telemetry'}</span>
        {badge && (
          <span className={`px-2 py-0.5 rounded-full border text-[10px] font-medium ${badgeClasses}`}>
            {badge}
          </span>
        )}
      </div>
    </div>
  );
};
