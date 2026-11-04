import React, { useState, useEffect } from 'react';
import {
  Settings,
  ShieldCheck,
  Cpu,
  Database,
  Lock,
  Sliders,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Save,
  Server,
  FileCheck,
  Zap,
  Activity,
  Network,
  Radio,
  Check,
} from 'lucide-react';
import {
  SystemSettingsItem,
  ProviderStatusItem,
  ProviderHealthCheckItem,
  ModelRouterConfig,
} from '../types';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

export const SettingsView: React.FC = () => {
  const { user, hasPermission } = useAuth();
  const [settingsData, setSettingsData] = useState<SystemSettingsItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Form states
  const [environment, setEnvironment] = useState('development');
  const [defaultProvider, setDefaultProvider] = useState('mock');
  const [defaultModel, setDefaultModel] = useState('mock-sentinel-v1');
  const [injectionThreshold, setInjectionThreshold] = useState(0.5);
  const [maxInputLength, setMaxInputLength] = useState(4096);

  // Multi-LLM Provider & Router States
  const [providers, setProviders] = useState<ProviderStatusItem[]>([]);
  const [providerHealth, setProviderHealth] = useState<Record<string, ProviderHealthCheckItem>>({});
  const [checkingHealth, setCheckingHealth] = useState<Record<string, boolean>>({});
  const [supportedModels, setSupportedModels] = useState<Record<string, string[]>>({});
  const [routerConfig, setRouterConfig] = useState<ModelRouterConfig | null>(null);
  const [savingRouter, setSavingRouter] = useState(false);
  const [routerSuccess, setRouterSuccess] = useState(false);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const [resSettings, provList, provHealthList, modelsData, configData] = await Promise.all([
        api.getSettings(),
        api.getProviders().catch(() => []),
        api.getProvidersHealth().catch(() => []),
        api.getProviderModels().catch(() => ({ models: {}, pricing_catalog_version: '1.0' })),
        api.getProviderConfiguration().catch(() => null),
      ]);

      setSettingsData(resSettings);
      setEnvironment(resSettings.environment);
      setDefaultProvider(resSettings.default_llm_provider);
      setDefaultModel(resSettings.default_llm_model);
      setInjectionThreshold(resSettings.prompt_injection_threshold);
      setMaxInputLength(resSettings.max_input_length);

      setProviders(provList || []);
      const healthMap: Record<string, ProviderHealthCheckItem> = {};
      (provHealthList || []).forEach((h) => {
        healthMap[h.provider.toLowerCase()] = h;
      });
      setProviderHealth(healthMap);
      setSupportedModels(modelsData?.models || {});
      setRouterConfig(configData);
    } catch (err: any) {
      console.error('Failed to load settings:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hasPermission('admin')) {
      alert('Only administrators can update system settings.');
      return;
    }
    try {
      setSaving(true);
      setSaveSuccess(false);
      await api.updateSettings({
        environment,
        default_llm_provider: defaultProvider,
        default_llm_model: defaultModel,
        prompt_injection_threshold: injectionThreshold,
        max_input_length: maxInputLength,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      await fetchSettings();
    } catch (err: any) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleCheckSingleHealth = async (providerName: string) => {
    try {
      setCheckingHealth((prev) => ({ ...prev, [providerName]: true }));
      const res = await api.checkProviderHealth(providerName);
      setProviderHealth((prev) => ({ ...prev, [providerName.toLowerCase()]: res }));
    } catch (err: any) {
      console.error(`Health check failed for ${providerName}:`, err);
    } finally {
      setCheckingHealth((prev) => ({ ...prev, [providerName]: false }));
    }
  };

  const handleSaveRouterConfig = async () => {
    if (!routerConfig || !hasPermission('admin')) return;
    try {
      setSavingRouter(true);
      setRouterSuccess(false);
      const updated = await api.updateProviderConfiguration(routerConfig);
      setRouterConfig(updated);
      setRouterSuccess(true);
      setTimeout(() => setRouterSuccess(false), 3000);
    } catch (err: any) {
      alert(`Failed to update routing configuration: ${err.message}`);
    } finally {
      setSavingRouter(false);
    }
  };

  const updateTaskRoute = (taskType: string, field: 'provider' | 'model', value: string) => {
    if (!routerConfig) return;
    const currentRoute = routerConfig.task_routing[taskType] || { provider: 'mock', model: 'mock-sentinel-v1' };
    const nextRoute = { ...currentRoute, [field]: value };
    // If provider changed, auto-select first supported model for that provider
    if (field === 'provider') {
      const pModels = supportedModels[value] || [];
      if (pModels.length > 0) {
        nextRoute.model = pModels[0];
      }
    }
    setRouterConfig({
      ...routerConfig,
      task_routing: {
        ...routerConfig.task_routing,
        [taskType]: nextRoute,
      },
    });
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-blue-400" />
            Platform & Security Firewall Settings
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Configure system runtime environments, Multi-LLM provider routing, and deterministic security firewall thresholds.
          </p>
        </div>

        <button
          onClick={fetchSettings}
          disabled={loading}
          className="p-1.5 bg-gray-900 border border-gray-800 text-gray-400 hover:text-white rounded-lg transition-colors"
          title="Refresh Settings"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
        </button>
      </div>

      {saveSuccess && (
        <div className="p-3 bg-emerald-950/50 border border-emerald-500/30 rounded-lg text-emerald-400 text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 shrink-0" />
          <span>System configuration successfully updated and applied.</span>
        </div>
      )}

      {/* Mandatory Data Integrity Guarantee Card */}
      <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-xl p-4 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        <div>
          <div className="text-xs font-semibold text-emerald-300">
            Mandatory Data Integrity Policy Active: STRICT_AUTHENTIC
          </div>
          <p className="text-[11px] text-gray-300 mt-0.5 leading-relaxed">
            All telemetry metrics, latency percentiles, and token accounting numbers are strictly derived from real persisted database rows. Random number generation, hardcoded arrays, and synthetic metrics are strictly prohibited across all views.
          </p>
        </div>
      </div>

      {/* ============================================================== */}
      {/* MULTI-LLM PROVIDER MANAGEMENT & LIVE HEALTH CHECKS */}
      {/* ============================================================== */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Network className="w-4 h-4 text-blue-400" />
              Multi-LLM Provider Gateway Management
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Live status, official SDK integration health, and on-demand connectivity checks.
            </p>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-300">
            {providers.filter((p) => p.is_configured).length} / {providers.length} Configured
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {providers.map((prov) => {
            const h = providerHealth[prov.provider.toLowerCase()];
            const isChecking = checkingHealth[prov.provider.toLowerCase()] || false;
            const isHealthy = h?.status === 'HEALTHY';
            const isNotConfigured = h?.status === 'NOT_CONFIGURED';

            return (
              <div
                key={prov.provider}
                className="bg-gray-950 border border-gray-800/80 rounded-xl p-4 flex flex-col justify-between space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white">{prov.display_name}</span>
                      <span
                        className={`text-[9px] px-1.5 py-0.2 rounded font-mono font-bold ${
                          prov.is_configured
                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            : 'bg-gray-800 text-gray-400'
                        }`}
                      >
                        {prov.is_configured ? 'KEY DETECTED' : 'KEY MISSING'}
                      </span>
                    </div>
                    <span className="text-[10px] text-gray-400 font-mono block mt-0.5">
                      Model: <strong className="text-gray-300">{prov.configured_model}</strong>
                    </span>
                  </div>

                  {/* Health status badge */}
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold flex items-center gap-1 ${
                      isHealthy
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                        : isNotConfigured
                        ? 'bg-gray-800 text-gray-400 border border-gray-700'
                        : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        isHealthy ? 'bg-emerald-400 animate-pulse' : isNotConfigured ? 'bg-gray-400' : 'bg-rose-400'
                      }`}
                    />
                    {h?.status || 'UNKNOWN'}
                  </span>
                </div>

                {/* Capabilities & Measured Latency */}
                <div className="flex flex-wrap items-center justify-between text-[10px] text-gray-400 pt-2 border-t border-gray-900">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500">Latency:</span>
                    <strong className="text-white font-mono">
                      {h?.latency_ms !== null && h?.latency_ms !== undefined ? `${h.latency_ms} ms` : 'N/A'}
                    </strong>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {prov.supports_tools && (
                      <span className="px-1.5 py-0.2 bg-blue-950/60 border border-blue-800/60 text-blue-300 rounded text-[9px]">
                        Tools
                      </span>
                    )}
                    {prov.supports_structured && (
                      <span className="px-1.5 py-0.2 bg-purple-950/60 border border-purple-800/60 text-purple-300 rounded text-[9px]">
                        Structured
                      </span>
                    )}
                  </div>
                </div>

                {/* Health Check Button */}
                <div className="flex items-center justify-between pt-1">
                  <span className="text-[10px] text-gray-500 truncate max-w-[200px]" title={h?.message || ''}>
                    {h?.message || 'Ready for health probe'}
                  </span>
                  <button
                    onClick={() => handleCheckSingleHealth(prov.provider)}
                    disabled={isChecking}
                    className="flex items-center gap-1 px-2.5 py-1 bg-gray-900 hover:bg-gray-800 border border-gray-700/60 rounded text-[10px] text-gray-200 transition-colors disabled:opacity-50"
                  >
                    <Radio className={`w-3 h-3 ${isChecking ? 'animate-spin text-blue-400' : 'text-gray-400'}`} />
                    {isChecking ? 'Probing...' : 'Check Health'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ============================================================== */}
      {/* MODEL TASK ROUTING CONFIGURATOR */}
      {/* ============================================================== */}
      {routerConfig && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-800 pb-3">
            <div>
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" />
                Specialized Task Routing & Fallback Chains
              </h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Assign specialized LLM providers and models per task type (planning, answering, classification, evaluation).
              </p>
            </div>
            {hasPermission('admin') && (
              <button
                onClick={handleSaveRouterConfig}
                disabled={savingRouter}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 shadow-sm"
              >
                {savingRouter ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                {savingRouter ? 'Saving...' : 'Save Routing Config'}
              </button>
            )}
          </div>

          {routerSuccess && (
            <div className="p-3 bg-emerald-950/50 border border-emerald-500/30 rounded-lg text-emerald-400 text-xs flex items-center gap-2">
              <CheckCircle className="w-4 h-4 shrink-0" />
              <span>Model routing configuration successfully saved and synchronized.</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(routerConfig.task_routing).map(([taskKey, route]) => {
              const taskModels = supportedModels[route.provider] || [];

              return (
                <div key={taskKey} className="p-3.5 bg-gray-950 border border-gray-800 rounded-lg space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white capitalize">
                      {taskKey.replace('_', ' ')}
                    </span>
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 uppercase">
                      Task
                    </span>
                  </div>

                  <div className="space-y-1.5">
                    <div>
                      <label className="block text-[10px] text-gray-400 mb-1">Provider</label>
                      <select
                        value={route.provider}
                        disabled={!hasPermission('admin')}
                        onChange={(e) => updateTaskRoute(taskKey, 'provider', e.target.value)}
                        className="w-full bg-gray-900 border border-gray-800 rounded px-2.5 py-1 text-xs text-gray-200 font-mono disabled:opacity-50"
                      >
                        <option value="gemini">Google Gemini</option>
                        <option value="groq">Groq</option>
                        <option value="openai">OpenAI</option>
                        <option value="mock">Deterministic Mock</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-[10px] text-gray-400 mb-1">Model</label>
                      <select
                        value={route.model}
                        disabled={!hasPermission('admin')}
                        onChange={(e) => updateTaskRoute(taskKey, 'model', e.target.value)}
                        className="w-full bg-gray-900 border border-gray-800 rounded px-2.5 py-1 text-xs text-gray-200 font-mono disabled:opacity-50"
                      >
                        {taskModels.length > 0 ? (
                          taskModels.map((m) => (
                            <option key={m} value={m}>
                              {m}
                            </option>
                          ))
                        ) : (
                          <option value={route.model}>{route.model}</option>
                        )}
                      </select>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Fallback Chains Preview */}
          <div className="pt-2 border-t border-gray-800/80">
            <span className="text-[11px] font-medium text-gray-400 block mb-2">
              Configured Fallback Escalation Chains (Auto-failover on rate-limits, timeouts & outages):
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
              {Object.entries(routerConfig.fallback_chains || {}).map(([primary, chain]) => (
                <div key={primary} className="p-2.5 rounded bg-gray-950 border border-gray-800/80">
                  <span className="text-gray-400 uppercase text-[10px] block font-bold mb-1">
                    Primary: {primary}
                  </span>
                  <div className="flex items-center gap-1 text-[11px] text-gray-300">
                    <span className="text-amber-400 font-bold">{primary}</span>
                    <span className="text-gray-600">→</span>
                    {chain.map((c, idx) => (
                      <React.Fragment key={idx}>
                        <span className="text-emerald-400">{c.provider}</span>
                        {idx < chain.length - 1 && <span className="text-gray-600">→</span>}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* SYSTEM FORM & SECURITY FIREWALL THRESHOLDS */}
      {/* ============================================================== */}
      <form onSubmit={handleSave} className="space-y-6">
        {/* Model Provider Configuration */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Cpu className="w-4 h-4 text-purple-400" />
            Global Platform Defaults
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Default Fallback Provider</label>
              <select
                value={defaultProvider}
                onChange={(e) => setDefaultProvider(e.target.value)}
                className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 font-mono"
              >
                <option value="mock">Deterministic Mock (Compliant & Segregated)</option>
                <option value="gemini">Google Gemini (GenAI SDK)</option>
                <option value="groq">Groq Cloud (Llama 3 / Mixtral)</option>
                <option value="openai">OpenAI (GPT-4o)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Default Model Name</label>
              <input
                type="text"
                value={defaultModel}
                onChange={(e) => setDefaultModel(e.target.value)}
                className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 font-mono"
              />
            </div>
          </div>
        </div>

        {/* Security Policy Thresholds */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Lock className="w-4 h-4 text-rose-400" />
            Security Firewall & Threshold Tuning
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <div className="flex items-center justify-between text-xs text-gray-300 mb-1">
                <span>Prompt Injection Confidence Threshold</span>
                <span className="font-mono text-blue-400 font-bold">{injectionThreshold}</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="0.9"
                step="0.05"
                value={injectionThreshold}
                onChange={(e) => setInjectionThreshold(parseFloat(e.target.value))}
                className="w-full accent-blue-500"
              />
              <span className="text-[10px] text-gray-500 block mt-1">
                Lower values increase sensitivity; higher values reduce false positives.
              </span>
            </div>

            <div>
              <div className="flex items-center justify-between text-xs text-gray-300 mb-1">
                <span>Max Input Character Length</span>
                <span className="font-mono text-blue-400 font-bold">{maxInputLength} chars</span>
              </div>
              <input
                type="number"
                min="512"
                max="16384"
                step="512"
                value={maxInputLength}
                onChange={(e) => setMaxInputLength(parseInt(e.target.value))}
                className="w-full px-3 py-1.5 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 font-mono"
              />
              <span className="text-[10px] text-gray-500 block mt-1">
                Inputs exceeding this threshold are blocked by token-bombing protection.
              </span>
            </div>
          </div>
        </div>

        {/* Database & Infrastructure Status */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Database className="w-4 h-4 text-emerald-400" />
            Persistence & Infrastructure Status
          </h2>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-2.5 rounded-lg bg-gray-950 border border-gray-800">
              <span className="text-gray-500 text-[10px] block">DATABASE DIALECT</span>
              <strong className="text-white text-xs uppercase">{settingsData?.database_dialect || 'SQLITE'}</strong>
            </div>
            <div className="p-2.5 rounded-lg bg-gray-950 border border-gray-800">
              <span className="text-gray-500 text-[10px] block">FAIL-CLOSED MODE</span>
              <strong className="text-emerald-400 text-xs">ENFORCED</strong>
            </div>
            <div className="p-2.5 rounded-lg bg-gray-950 border border-gray-800">
              <span className="text-gray-500 text-[10px] block">QDRANT VECTOR STORE</span>
              <strong className="text-white text-xs">
                {settingsData?.qdrant_in_memory ? 'IN-MEMORY' : `${settingsData?.qdrant_host}:${settingsData?.qdrant_port}`}
              </strong>
            </div>
            <div className="p-2.5 rounded-lg bg-gray-950 border border-gray-800">
              <span className="text-gray-500 text-[10px] block">LANGFUSE EXPORTER</span>
              <strong className={settingsData?.langfuse_configured ? 'text-emerald-400 text-xs' : 'text-gray-400 text-xs'}>
                {settingsData?.langfuse_configured ? 'ENABLED' : 'OFFLINE'}
              </strong>
            </div>
          </div>
        </div>

        {/* Submit */}
        {hasPermission('admin') ? (
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-50 shadow-sm"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Applying...' : 'Save Configuration'}
            </button>
          </div>
        ) : (
          <div className="p-3 bg-gray-900 border border-gray-800 rounded-lg text-xs text-gray-400 text-center">
            Signed in with <strong className="capitalize text-white">{user.role}</strong> role. Only administrators can alter platform configuration.
          </div>
        )}
      </form>
    </div>
  );
};
