import React, { useState, useEffect } from 'react';
import {
  Activity,
  Layers,
  Clock,
  Cpu,
  Download,
  Search,
  ExternalLink,
  RefreshCw,
  AlertCircle,
  Network,
  Zap,
} from 'lucide-react';
import { ExecutionTraceItem } from '../types';
import { api } from '../api/client';
import { EmptyState } from '../components/EmptyState';

interface TraceExplorerViewProps {
  initialTraceId?: string | null;
}

export const TraceExplorerView: React.FC<TraceExplorerViewProps> = ({ initialTraceId }) => {
  const [traces, setTraces] = useState<ExecutionTraceItem[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<ExecutionTraceItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [search, setSearch] = useState('');

  const loadTraces = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getTraces(undefined, undefined, undefined, 50);
      setTraces(data);
      if (initialTraceId) {
        const found = data.find((t) => t.id === initialTraceId);
        if (found) {
          loadSingleTrace(initialTraceId);
        }
      } else if (data.length > 0 && !selectedTrace) {
        loadSingleTrace(data[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch traces');
    } finally {
      setLoading(false);
    }
  };

  const loadSingleTrace = async (id: string) => {
    try {
      const full = await api.getTrace(id);
      setSelectedTrace(full);
    } catch (err: any) {
      console.error('Error fetching trace details:', err);
    }
  };

  useEffect(() => {
    loadTraces();
  }, [initialTraceId]);

  const handleExport = async (id: string) => {
    try {
      setExporting(true);
      const exportData = await api.exportTrace(id);
      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportData, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute('href', dataStr);
      downloadAnchor.setAttribute('download', `sentinel-trace-${id}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    } catch (err: any) {
      alert(`Export failed: ${err.message}`);
    } finally {
      setExporting(false);
    }
  };

  const filteredTraces = traces.filter(
    (t) =>
      t.id.toLowerCase().includes(search.toLowerCase()) ||
      t.input_prompt.toLowerCase().includes(search.toLowerCase()) ||
      (t.provider && t.provider.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-400" />
            Execution Trace & Multi-LLM Span Explorer
          </h1>
          <p className="text-sm text-gray-400">
            OpenTelemetry & Langfuse-compatible span telemetry directly from persisted database records.
          </p>
        </div>
        <button
          onClick={loadTraces}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs font-medium text-gray-300 hover:text-white hover:border-gray-700 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-blue-400' : ''}`} />
          Refresh Traces
        </button>
      </div>

      {traces.length === 0 && !loading ? (
        <EmptyState
          title="No Execution Traces Recorded"
          description="Every query processed through the Agent Gateway records structured spans (guard input, context retrieval, tool policy evaluation, LLM calls, output guard). Traces will appear here once executed."
          icon={<Layers className="w-8 h-8 text-blue-400" />}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Trace List */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-gray-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search prompt, trace ID, provider..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-gray-950 border border-gray-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {filteredTraces.map((t) => {
                const isSelected = selectedTrace?.id === t.id;
                return (
                  <div
                    key={t.id}
                    onClick={() => loadSingleTrace(t.id)}
                    className={`p-3 rounded-lg border text-xs cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-blue-950/40 border-blue-500/50 text-white shadow-sm'
                        : 'bg-gray-950 border-gray-800 text-gray-400 hover:border-gray-700 hover:text-gray-200'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono text-[10px] text-gray-500">{t.id.slice(0, 8)}...</span>
                      <div className="flex items-center gap-1">
                        {t.provider && (
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-purple-950/60 text-purple-300 border border-purple-800 uppercase">
                            {t.provider}
                          </span>
                        )}
                        <span
                          className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${
                            t.status === 'SUCCESS'
                              ? 'bg-emerald-950/60 text-emerald-300 border-emerald-800'
                              : t.status === 'BLOCKED'
                              ? 'bg-rose-950/60 text-rose-300 border-rose-800'
                              : 'bg-amber-950/60 text-amber-300 border-amber-800'
                          }`}
                        >
                          {t.status}
                        </span>
                      </div>
                    </div>
                    <p className="line-clamp-2 text-gray-300 font-sans">{t.input_prompt}</p>
                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-800/60 text-[10px] text-gray-500 font-mono">
                      <span>{t.total_latency_ms} ms</span>
                      <span>{t.total_tokens} tokens</span>
                      <span>{t.fallback_occurred ? 'FALLBACK' : t.is_mock ? 'MOCK' : 'LIVE'}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Trace Detail & Spans Waterfall */}
          <div className="lg:col-span-2 space-y-4">
            {selectedTrace ? (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-800 pb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-semibold text-white">Trace Details</h3>
                      {selectedTrace.provider && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-purple-500/15 text-purple-300 border border-purple-500/30 uppercase">
                          {selectedTrace.provider}
                        </span>
                      )}
                      {selectedTrace.fallback_occurred && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1">
                          <Zap className="w-3 h-3" />
                          FALLBACK ENGAGED
                        </span>
                      )}
                    </div>
                    <span className="font-mono text-xs text-gray-400">{selectedTrace.id}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <a
                      href={`https://us.cloud.langfuse.com/project/cmw1pfxgz00fsad0eajchjmb3/traces/${selectedTrace.id.replace(/-/g, '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-600/20 hover:bg-orange-600/30 border border-orange-500/40 text-xs font-semibold text-orange-300 transition-colors"
                      title="Open trace in Langfuse Cloud dashboard"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      View in Langfuse
                    </a>
                    <button
                      onClick={() => handleExport(selectedTrace.id)}
                      disabled={exporting}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs font-medium text-white transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                      {exporting ? 'Exporting...' : 'Export OTel / Langfuse'}
                    </button>
                  </div>
                </div>

                {/* Fallback event banner if engaged */}
                {selectedTrace.fallback_occurred && (
                  <div className="p-3 bg-amber-950/30 border border-amber-500/30 rounded-lg text-amber-300 text-xs flex items-center gap-2">
                    <Zap className="w-4 h-4 shrink-0 text-amber-400" />
                    <span>
                      Automatic provider failover was executed for this request. Primary provider was unavailable or rate-limited; execution succeeded via fallback model.
                    </span>
                  </div>
                )}

                {/* Quick Info Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                  <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                    <span className="text-gray-500 block text-[10px]">PROVIDER & MODEL</span>
                    <strong className="text-white text-xs font-mono truncate block">
                      {selectedTrace.provider || (selectedTrace.is_mock ? 'MOCK' : 'DEFAULT')} /{' '}
                      {selectedTrace.model_name || 'N/A'}
                    </strong>
                  </div>
                  <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                    <span className="text-gray-500 block text-[10px]">TOTAL LATENCY</span>
                    <strong className="text-white text-sm">{selectedTrace.total_latency_ms} ms</strong>
                  </div>
                  <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                    <span className="text-gray-500 block text-[10px]">TOTAL TOKENS</span>
                    <strong className="text-white text-sm">{selectedTrace.total_tokens}</strong>
                  </div>
                  <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                    <span className="text-gray-500 block text-[10px]">ESTIMATED COST</span>
                    <strong className="text-white text-sm">${selectedTrace.estimated_cost_usd.toFixed(6)}</strong>
                  </div>
                  <div className="bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                    <span className="text-gray-500 block text-[10px]">TIMESTAMP</span>
                    <strong className="text-white text-xs font-mono">
                      {new Date(selectedTrace.started_at).toLocaleTimeString()}
                    </strong>
                  </div>
                </div>

                {/* Spans Waterfall */}
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3 flex items-center gap-2">
                    <Layers className="w-4 h-4 text-blue-400" />
                    Execution Spans Hierarchy ({(selectedTrace.spans || []).length} Spans)
                  </h4>
                  <div className="space-y-2">
                    {(selectedTrace.spans || []).map((span, idx) => {
                      const spansList = selectedTrace.spans || [];
                      const maxLat = Math.max(...spansList.map((s) => s.latency_ms), 1);
                      const widthPercent = Math.max(12, Math.round((span.latency_ms / maxLat) * 100));

                      return (
                        <div
                          key={span.id}
                          className="bg-gray-950 border border-gray-800 rounded-lg p-3 space-y-2"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                              <span className="text-gray-500 font-mono text-[10px]">#{idx + 1}</span>
                              <strong className="text-white">{span.name}</strong>
                              <span className="px-1.5 py-0.2 rounded text-[10px] bg-gray-800 text-gray-400">
                                {span.span_type}
                              </span>
                            </div>
                            <div className="flex items-center gap-3 text-xs text-gray-400">
                              <span>{span.tokens > 0 ? `${span.tokens} tok` : ''}</span>
                              <strong className="text-white font-mono">{span.latency_ms} ms</strong>
                            </div>
                          </div>

                          {/* Relative latency bar */}
                          <div className="h-1.5 w-full bg-gray-900 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500 rounded-full"
                              style={{ width: `${widthPercent}%` }}
                            />
                          </div>

                          {/* Diagnostic Payload snippet if available */}
                          {span.output_data && (
                            <details className="text-[11px] text-gray-400 pt-1">
                              <summary className="cursor-pointer hover:text-white font-mono text-[10px]">
                                Span Output Payload
                              </summary>
                              <pre className="mt-1 p-2 bg-gray-900 border border-gray-800/80 rounded font-mono text-[10px] text-gray-300 overflow-x-auto">
                                {JSON.stringify(span.output_data, null, 2)}
                              </pre>
                            </details>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-12 text-center text-gray-500 bg-gray-900 border border-gray-800 rounded-xl">
                Select a trace from the left panel to inspect its execution timeline.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
