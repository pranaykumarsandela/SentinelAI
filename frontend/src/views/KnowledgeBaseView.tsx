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
} from 'lucide-react';
import { DocumentItem } from '../types';
import { api } from '../api/client';
import { EmptyState } from '../components/EmptyState';

export const KnowledgeBaseView: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Search Tester state
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<any | null>(null);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const docs = await api.getDocuments();
      setDocuments(docs);
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
      await api.uploadDocument(file);
      await loadDocuments();
      e.target.value = '';
    } catch (err: any) {
      setError(err.message || 'Failed to upload document');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this document and all indexed chunks?')) return;
    try {
      await api.deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const handleHybridSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      setSearching(true);
      const res = await api.queryRAG(searchQuery);
      setSearchResults(res);
    } catch (err: any) {
      alert(`Search error: ${err.message}`);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-400" />
            Knowledge Base & Document Indexing
          </h1>
          <p className="text-sm text-gray-400">
            Ingest and index enterprise documents (PDF, TXT, MD, DOCX) into Qdrant & SQLite/Postgres.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-xs font-semibold text-white cursor-pointer shadow-sm transition-colors">
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
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Hybrid Search Sandbox Tester */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Search className="w-4 h-4 text-blue-400" />
          Hybrid Retrieval & Cross-Encoder Tester
        </h3>
        <p className="text-xs text-gray-400">
          Executes dense vector search (Qdrant) + BM25 keyword search + Reciprocal Rank Fusion + Cross-Encoder reranking.
        </p>

        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleHybridSearch()}
            placeholder="Search knowledge corpus (e.g. 'encryption algorithms', 'security compliance')..."
            className="flex-1 bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleHybridSearch}
            disabled={searching || !searchQuery.trim()}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition-colors"
          >
            {searching ? 'Retrieving...' : 'Hybrid Query'}
          </button>
        </div>

        {searchResults && (
          <div className="mt-4 pt-4 border-t border-gray-800 space-y-3">
            <div className="flex items-center justify-between text-xs text-gray-400">
              <span>
                Retrieved Chunks: <strong className="text-white">{searchResults.retrieved_chunks?.length || 0}</strong>
              </span>
              <span>
                Grade: <strong className="text-emerald-400">{searchResults.retrieval_grade || 'SUFFICIENT'}</strong>
              </span>
            </div>

            <div className="space-y-2">
              {searchResults.retrieved_chunks?.map((chunk: any, i: number) => (
                <div key={i} className="p-3 bg-gray-950 border border-gray-800 rounded-lg text-xs space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-gray-500">
                    <span className="font-semibold text-blue-400">
                      {chunk.filename} (Page {chunk.page_number ?? '1'})
                    </span>
                    <span className="font-mono">Rerank Score: {(chunk.score || 0).toFixed(4)}</span>
                  </div>
                  <p className="text-gray-300 font-sans leading-relaxed">{chunk.content}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Document Library Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">Indexed Documents ({documents.length})</h3>
          <button
            onClick={loadDocuments}
            disabled={loading}
            className="text-xs text-gray-400 hover:text-white flex items-center gap-1"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {documents.length === 0 && !loading ? (
          <EmptyState
            title="Knowledge Corpus is Clean (0 Documents)"
            description="Upload PDF, TXT, MD, or DOCX documents to index them for hybrid retrieval. Embeddings will be normalized and indexed in Qdrant."
            icon={<FileText className="w-8 h-8 text-blue-400" />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-950 text-gray-400 uppercase tracking-wider text-[10px] border-b border-gray-800">
                <tr>
                  <th className="py-3 px-4">Filename</th>
                  <th className="py-3 px-4">Format</th>
                  <th className="py-3 px-4">Size</th>
                  <th className="py-3 px-4">Chunks Indexed</th>
                  <th className="py-3 px-4">Ingestion Status</th>
                  <th className="py-3 px-4">Uploaded</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 font-sans text-gray-300">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="py-3 px-4 font-semibold text-white flex items-center gap-2">
                      <FileText className="w-3.5 h-3.5 text-blue-400" />
                      <span>{doc.filename}</span>
                    </td>
                    <td className="py-3 px-4 font-mono uppercase text-gray-400">{doc.file_type}</td>
                    <td className="py-3 px-4 text-gray-400">{(doc.file_size_bytes / 1024).toFixed(1)} KB</td>
                    <td className="py-3 px-4 font-mono font-semibold text-white">{doc.chunk_count}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950/60 text-emerald-300 border border-emerald-800">
                        {doc.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-400">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="p-1 rounded text-gray-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                        title="Delete Document & Chunks"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
