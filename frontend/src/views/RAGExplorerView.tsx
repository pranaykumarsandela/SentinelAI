import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Upload,
  Trash2,
  Search,
  FileText,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Layers,
  ChevronRight,
  X,
  FileCheck,
  Send,
} from 'lucide-react';
import { DocumentItem, RAGQueryResponse } from '../types';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { EmptyState } from '../components/EmptyState';

export const RAGExplorerView: React.FC = () => {
  const { hasPermission } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selected document for chunk inspection
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [loadingChunks, setLoadingChunks] = useState(false);

  // Retrieval Testing state
  const [queryInput, setQueryInput] = useState('What encryption standard does the policy require?');
  const [querying, setQuerying] = useState(false);
  const [queryResponse, setQueryResponse] = useState<RAGQueryResponse | null>(null);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getDocuments('e2e_tenant', 1, 100);
      if (res && res.items) {
        setDocuments(res.items);
      } else if (Array.isArray(res)) {
        setDocuments(res);
      } else {
        setDocuments([]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch documents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      setError(null);
      await api.uploadDocument(file, 'e2e_tenant');
      await loadDocuments();
      e.target.value = '';
    } catch (err: any) {
      alert(`Upload error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!hasPermission('supervisor')) {
      alert('Only supervisors or administrators can delete documents.');
      return;
    }
    if (!confirm('Are you sure you want to delete this document and all indexed vector chunks?')) return;
    try {
      await api.deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      if (selectedDoc?.id === id) {
        setSelectedDoc(null);
      }
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const handleInspectChunks = async (doc: DocumentItem) => {
    try {
      setLoadingChunks(true);
      setSelectedDoc(doc);
      const fullDoc = await api.getDocument(doc.id, true);
      setSelectedDoc(fullDoc);
    } catch (err: any) {
      alert(`Failed to load chunks: ${err.message}`);
    } finally {
      setLoadingChunks(false);
    }
  };

  const handleRunRAGQuery = async () => {
    if (!queryInput.trim()) return;
    try {
      setQuerying(true);
      setQueryResponse(null);
      const res = await api.queryRAG(queryInput, 'e2e_tenant');
      setQueryResponse(res);
    } catch (err: any) {
      alert(`RAG query failed: ${err.message}`);
    } finally {
      setQuerying(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-400" />
            RAG Explorer & Document Knowledge Base
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Ingest enterprise documents (PDF, TXT, MD, DOCX), inspect vector chunks, and test agentic hybrid retrieval.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {hasPermission('analyst') && (
            <label className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-semibold text-white cursor-pointer transition-colors shadow-sm">
              <Upload className={`w-3.5 h-3.5 ${uploading ? 'animate-bounce' : ''}`} />
              <span>{uploading ? 'Chunking & Indexing...' : 'Upload Document'}</span>
              <input
                type="file"
                accept=".pdf,.txt,.md,.docx"
                onChange={handleFileUpload}
                disabled={uploading}
                className="hidden"
              />
            </label>
          )}

          <button
            onClick={loadDocuments}
            disabled={loading}
            className="p-1.5 rounded-lg bg-gray-900 border border-gray-800 text-gray-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Grid: Document List & Retrieval Tester */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Document Listing (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-gray-800 flex items-center justify-between">
              <div className="text-xs font-semibold text-white flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-400" />
                Indexed Corporate Documents ({documents.length})
              </div>
              <span className="text-[11px] text-gray-400">Qdrant Vector Database</span>
            </div>

            {loading ? (
              <div className="flex items-center justify-center h-48 text-gray-500 text-xs">
                <RefreshCw className="w-4 h-4 animate-spin mr-2 text-blue-500" />
                Loading indexed documents...
              </div>
            ) : documents.length === 0 ? (
              <div className="p-8 text-center">
                <EmptyState
                  title="No Documents Uploaded"
                  description="Upload a corporate policy, guidelines, or handbook (.txt, .md, .pdf, .docx) to index vectors into Qdrant."
                  icon={<BookOpen className="w-8 h-8 text-blue-400" />}
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-gray-950/70 text-gray-400 uppercase text-[10px] font-semibold border-b border-gray-800">
                    <tr>
                      <th className="py-2.5 px-3">Filename</th>
                      <th className="py-2.5 px-3">Format</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Chunks</th>
                      <th className="py-2.5 px-3">Size</th>
                      <th className="py-2.5 px-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/60 font-mono">
                    {documents.map((doc) => (
                      <tr key={doc.id} className="hover:bg-gray-800/30 transition-colors">
                        <td className="py-2 px-3 font-medium text-gray-200 flex items-center gap-2">
                          <FileText className="w-3.5 h-3.5 text-gray-400" />
                          <span className="truncate max-w-[200px]" title={doc.filename}>{doc.filename}</span>
                        </td>
                        <td className="py-2 px-3 text-gray-400 uppercase">{doc.file_type}</td>
                        <td className="py-2 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              doc.status === 'COMPLETED'
                                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                : doc.status === 'PROCESSING'
                                ? 'bg-blue-500/15 text-blue-400 border border-blue-500/30 animate-pulse'
                                : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                            }`}
                          >
                            {doc.status}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-gray-300 font-semibold">
                          {doc.total_chunks || doc.chunk_count || 0}
                        </td>
                        <td className="py-2 px-3 text-gray-400">
                          {(doc.file_size_bytes / 1024).toFixed(1)} KB
                        </td>
                        <td className="py-2 px-3 text-right space-x-1">
                          <button
                            onClick={() => handleInspectChunks(doc)}
                            className="px-2 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded text-[11px] transition-colors"
                          >
                            Chunks
                          </button>
                          {hasPermission('supervisor') && (
                            <button
                              onClick={() => handleDelete(doc.id)}
                              className="px-2 py-1 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 rounded text-[11px] transition-colors"
                            >
                              <Trash2 className="w-3 h-3 inline" />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Right: Retrieval Tester Playground */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-gray-800">
            <div className="flex items-center gap-2">
              <Search className="w-4 h-4 text-emerald-400" />
              <h3 className="text-xs font-semibold text-white">Hybrid Retrieval Tester</h3>
            </div>
            <span className="text-[10px] text-gray-400 font-mono">BM25 + 384d Dense</span>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-gray-300 mb-1">Retrieval Query</label>
            <textarea
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              rows={2}
              placeholder="e.g. What is the database password policy?"
              className="w-full px-3 py-2 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-200 focus:outline-none focus:border-blue-500 font-mono"
            />
          </div>

          <button
            onClick={handleRunRAGQuery}
            disabled={querying || !queryInput.trim()}
            className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-2"
          >
            {querying ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Executing LangGraph RAG Pipeline...
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5" />
                Run Retrieval & Grounding
              </>
            )}
          </button>

          {/* RAG Query Output */}
          {queryResponse && (
            <div className="p-3 bg-gray-950 border border-gray-800 rounded-lg space-y-3 text-xs">
              <div className="flex items-center justify-between font-mono text-[10px]">
                <span
                  className={`px-1.5 py-0.5 rounded font-bold ${
                    queryResponse.groundedness_verdict === 'GROUNDED'
                      ? 'bg-emerald-500/15 text-emerald-400'
                      : 'bg-amber-500/15 text-amber-400'
                  }`}
                >
                  {queryResponse.groundedness_verdict}
                </span>
                <span className="text-gray-400">
                  Grade: <strong className="text-gray-200">{queryResponse.retrieval_grade}</strong>
                </span>
              </div>

              {queryResponse.rewritten_query && queryResponse.rewritten_query !== queryResponse.query && (
                <div className="text-[11px] text-gray-400">
                  Rewritten: <span className="font-mono text-blue-300">{queryResponse.rewritten_query}</span>
                </div>
              )}

              <div>
                <span className="text-[10px] text-gray-400 block mb-0.5 uppercase tracking-wide">Synthesized Answer:</span>
                <div className="p-2 bg-gray-900 rounded font-mono text-gray-200 text-xs whitespace-pre-wrap">
                  {queryResponse.answer}
                </div>
              </div>

              {/* Citations */}
              <div>
                <span className="text-[10px] text-gray-400 block mb-1 uppercase tracking-wide">
                  Verified Citations ({queryResponse.citations?.length || 0}):
                </span>
                <div className="space-y-1.5 max-h-40 overflow-y-auto">
                  {queryResponse.citations && queryResponse.citations.length > 0 ? (
                    queryResponse.citations.map((c, i) => (
                      <div key={i} className="p-2 bg-gray-900 border border-gray-800 rounded font-mono text-[11px]">
                        <div className="text-blue-400 font-semibold flex items-center justify-between">
                          <span>{c.filename}</span>
                          <span className="text-gray-500 text-[10px]">{c.chunk_id.slice(0, 8)}...</span>
                        </div>
                        <div className="text-gray-400 text-[10px] mt-0.5 line-clamp-2">
                          "{c.relevant_source_text}"
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-[11px] text-gray-500">No citations produced.</div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Chunk Inspection Drawer */}
      {selectedDoc && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-2xl w-full space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-gray-800 pb-3">
              <div>
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <Layers className="w-4 h-4 text-blue-400" />
                  Chunk Inspection: {selectedDoc.filename}
                </h2>
                <div className="text-[11px] text-gray-400 font-mono mt-0.5">
                  ID: {selectedDoc.id} | Hash: {selectedDoc.content_hash.slice(0, 16)}...
                </div>
              </div>
              <button onClick={() => setSelectedDoc(null)} className="text-gray-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {loadingChunks ? (
                <div className="py-12 text-center text-xs text-gray-500">
                  <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2 text-blue-500" />
                  Loading chunk details...
                </div>
              ) : selectedDoc.chunks && selectedDoc.chunks.length > 0 ? (
                selectedDoc.chunks.map((ch) => (
                  <div key={ch.id} className="p-3 bg-gray-950 border border-gray-800 rounded-lg space-y-1 text-xs">
                    <div className="flex items-center justify-between text-[10px] text-gray-400 font-mono border-b border-gray-900 pb-1">
                      <span className="font-bold text-blue-400">Chunk #{ch.chunk_index}</span>
                      <span>Page: {ch.page_number ?? 'N/A'}</span>
                      <span>Tokens: {ch.token_count}</span>
                      <span>Chars: {ch.start_char} - {ch.end_char}</span>
                    </div>
                    <p className="text-gray-300 font-mono text-[11px] pt-1 whitespace-pre-wrap leading-relaxed">
                      {ch.content}
                    </p>
                  </div>
                ))
              ) : (
                <div className="py-12 text-center text-xs text-gray-500">
                  No individual chunk records located for this document.
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-gray-800">
              <button
                onClick={() => setSelectedDoc(null)}
                className="px-4 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded text-xs font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

