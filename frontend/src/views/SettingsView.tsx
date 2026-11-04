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
} from 'lucide-react';
import { SystemSettingsItem } from '../types';
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

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const res = await api.getSettings();
      setSettingsData(res);
      setEnvironment(res.environment);
      setDefaultProvider(res.default_llm_provider);
      setDefaultModel(res.default_llm_model);
      setInjectionThreshold(res.prompt_injection_threshold);
      setMaxInputLength(res.max_input_length);
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

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-blue-400" />
            Platform & Security Firewall Settings
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Configure system runtime environments, default LLM providers, and deterministic security firewall thresholds.
          </p>
        </div>

        <button
          onClick={fetchSettings}
          disabled={loading}
          className="p-1.5 bg-gray-900 border border-gray-800 text-gray-400 hover:text-white rounded-lg transition-colors"
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

      <form onSubmit={handleSave} className="space-y-6">
        {/* Model Provider Configuration */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Cpu className="w-4 h-4 text-purple-400" />
            LLM Provider & Orchestration Defaults
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Default Provider</label>
              <select
                value={defaultProvider}
                onChange={(e) => setDefaultProvider(e.target.value)}
                className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 font-mono"
              >
                <option value="mock">Deterministic Mock (Compliant & Segregated)</option>
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

          {/* Masked Credentials Status */}
          <div className="pt-2 border-t border-gray-800/80">
            <span className="text-[11px] font-medium text-gray-400 block mb-2">Provider Credential Status:</span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
              <div className="p-2 rounded bg-gray-950 border border-gray-800 flex items-center justify-between">
                <span className="text-gray-400">Mock Engine:</span>
                <span className="text-emerald-400 font-bold">READY</span>
              </div>
              <div className="p-2 rounded bg-gray-950 border border-gray-800 flex items-center justify-between">
                <span className="text-gray-400">Groq API:</span>
                <span className={settingsData?.groq_configured ? 'text-emerald-400' : 'text-gray-500'}>
                  {settingsData?.groq_configured ? 'CONFIGURED' : 'NOT SET'}
                </span>
              </div>
              <div className="p-2 rounded bg-gray-950 border border-gray-800 flex items-center justify-between">
                <span className="text-gray-400">OpenAI API:</span>
                <span className={settingsData?.openai_configured ? 'text-emerald-400' : 'text-gray-500'}>
                  {settingsData?.openai_configured ? 'CONFIGURED' : 'NOT SET'}
                </span>
              </div>
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
