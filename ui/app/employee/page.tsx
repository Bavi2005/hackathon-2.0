"use client";

import React, { useState, useEffect } from 'react';
import {
    ArrowLeft, Search, Loader2, CheckCircle2, XCircle,
    AlertTriangle, Clock, Edit2, ChevronDown, ChevronUp
} from 'lucide-react';
import Link from 'next/link';
import { getApplications, reviewApplication, updateExplanation, Application } from '../../lib/api';

// Constants
const AGREE_WITH_AI_COMMENT = 'Agreed with AI recommendation';

// Utility function to format field names
const formatFieldName = (key: string): string => {
    return key.replace(/_/g, ' ').split(' ').map(word => 
        word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
};

export default function EmployeeDashboard() {
    const [activeTab, setActiveTab] = useState<'pending' | 'history'>('pending');
    const [applications, setApplications] = useState<Application[]>([]);
    const [selectedApp, setSelectedApp] = useState<Application | null>(null);
    const [loading, setLoading] = useState(true);
    const [processingId, setProcessingId] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    
    // Override modal state
    const [showOverrideModal, setShowOverrideModal] = useState(false);
    const [overrideDecision, setOverrideDecision] = useState<'approved' | 'rejected'>('approved');
    const [overrideExplanation, setOverrideExplanation] = useState('');

    useEffect(() => {
        fetchApplications();
        const interval = setInterval(fetchApplications, 5000);
        return () => clearInterval(interval);
    }, [activeTab]);

    const fetchApplications = async () => {
        if (applications.length === 0) setLoading(true);
        try {
            const status = activeTab === 'pending' ? 'pending_human' : 'completed';
            const data = await getApplications(status);
            setApplications(data);
        } catch (err) {
            console.error("[API] Error fetching applications:", err);
        } finally {
            setLoading(false);
        }
    };

    const handleInstantDecision = async (decision: 'approved' | 'rejected') => {
        if (!selectedApp) return;
        
        const aiDecision = selectedApp.ai_result?.decision?.status?.toLowerCase();
        const isOverride = aiDecision !== decision;
        
        if (isOverride) {
            // Show override modal with pre-generated alternative reasoning
            setOverrideDecision(decision);
            setOverrideExplanation(selectedApp.ai_result?.alternative_reasoning || '');
            setShowOverrideModal(true);
        } else {
            // Instant approval/rejection - agrees with AI
            setProcessingId(selectedApp.id);
            try {
                await reviewApplication(selectedApp.id, decision, AGREE_WITH_AI_COMMENT);
                setApplications(prev => prev.filter(app => app.id !== selectedApp.id));
                setSelectedApp(null);
            } catch (err) {
                console.error(err);
                alert("Failed to submit decision");
            } finally {
                setProcessingId(null);
            }
        }
    };

    const submitOverride = async () => {
        if (!selectedApp) return;
        
        setProcessingId(selectedApp.id);
        try {
            await reviewApplication(selectedApp.id, overrideDecision, overrideExplanation);
            setApplications(prev => prev.filter(app => app.id !== selectedApp.id));
            setSelectedApp(null);
            setShowOverrideModal(false);
        } catch (err) {
            console.error(err);
            alert("Failed to submit override");
        } finally {
            setProcessingId(null);
        }
    };

    const filteredApplications = applications.filter(app => {
        if (!searchQuery) return true;
        const name = app.data?.full_name || '';
        const id = app.id || '';
        return name.toLowerCase().includes(searchQuery.toLowerCase()) ||
               id.toLowerCase().includes(searchQuery.toLowerCase());
    });

    return (
        <div className="min-h-screen bg-slate-950 text-white flex">
            {/* Sidebar */}
            <div className="w-64 border-r border-slate-800 p-6 flex flex-col bg-slate-900/50">
                <div className="mb-10">
                    <Link href="/" className="flex items-center text-slate-400 hover:text-white transition-colors">
                        <ArrowLeft className="w-4 h-4 mr-2" /> Exit Dashboard
                    </Link>
                </div>

                <div className="space-y-2">
                    <button
                        onClick={() => { setActiveTab('pending'); setSelectedApp(null); }}
                        className={`w-full text-left px-4 py-3 rounded-xl transition-all font-medium flex items-center justify-between ${activeTab === 'pending'
                            ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                            : 'text-slate-400 hover:text-white hover:bg-slate-800'
                            }`}
                    >
                        <span>Pending Review</span>
                        {activeTab === 'pending' && <span className="bg-white/20 text-xs px-2 py-0.5 rounded-full">{applications.length}</span>}
                    </button>
                    <button
                        onClick={() => { setActiveTab('history'); setSelectedApp(null); }}
                        className={`w-full text-left px-4 py-3 rounded-xl transition-all font-medium ${activeTab === 'history'
                            ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/20'
                            : 'text-slate-400 hover:text-white hover:bg-slate-800'
                            }`}
                    >
                        <span>History</span>
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-8 h-screen overflow-hidden flex flex-col">
                <header className="flex justify-between items-center mb-8 shrink-0">
                    <div>
                        <h1 className="text-3xl font-bold">
                            {activeTab === 'pending' ? 'Pending Reviews' : 'Case History'}
                        </h1>
                        <p className="text-slate-400">
                            {activeTab === 'pending'
                                ? 'AI-processed applications with instant pre-generated explanations'
                                : 'Archive of past decisions'}
                        </p>
                    </div>
                    <button onClick={fetchApplications} className="p-2 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors">
                        <Clock className="w-5 h-5 text-slate-400" />
                    </button>
                </header>

                {/* Search Bar */}
                <div className="mb-6 shrink-0">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                        <input
                            type="text"
                            placeholder="Search by name or ID..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full bg-slate-900/50 border border-slate-800 rounded-xl pl-12 pr-4 py-3 text-white focus:ring-2 focus:ring-blue-500 outline-none"
                        />
                    </div>
                </div>

                {/* Single-Column Scrollable List */}
                <div className="flex-1 overflow-y-auto space-y-3">
                    {loading ? (
                        <div className="flex justify-center p-16"><Loader2 className="animate-spin text-slate-500 w-8 h-8" /></div>
                    ) : filteredApplications.length === 0 ? (
                        <div className="p-16 text-center text-slate-500">No applications found.</div>
                    ) : (
                        filteredApplications.map((app) => (
                            <ApplicationRow
                                key={app.id}
                                app={app}
                                isSelected={selectedApp?.id === app.id}
                                onSelect={() => setSelectedApp(selectedApp?.id === app.id ? null : app)}
                                onInstantDecision={handleInstantDecision}
                                isProcessing={processingId === app.id}
                                activeTab={activeTab}
                            />
                        ))
                    )}
                </div>
            </div>

            {/* Override Modal */}
            {showOverrideModal && (
                <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-8">
                    <div className="bg-slate-900 rounded-2xl border border-slate-700 p-8 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-2xl font-bold flex items-center">
                                <AlertTriangle className="w-6 h-6 mr-3 text-amber-500" />
                                Override AI Recommendation
                            </h2>
                            <button onClick={() => setShowOverrideModal(false)} className="text-slate-400 hover:text-white">
                                <XCircle className="w-6 h-6" />
                            </button>
                        </div>
                        
                        <div className="mb-6 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
                            <p className="text-amber-400 text-sm">
                                You are overriding the AI decision. The pre-generated explanation below justifies the <strong>{overrideDecision.toUpperCase()}</strong> decision.
                            </p>
                        </div>

                        <div className="mb-6">
                            <label className="block text-slate-400 mb-2 font-medium">Explanation (Editable)</label>
                            <textarea
                                value={overrideExplanation}
                                onChange={(e) => setOverrideExplanation(e.target.value)}
                                rows={10}
                                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-white focus:ring-2 focus:ring-blue-500 outline-none resize-none"
                            />
                        </div>

                        <div className="flex justify-end space-x-4">
                            <button
                                onClick={() => setShowOverrideModal(false)}
                                className="px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 font-medium transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={submitOverride}
                                disabled={!!processingId}
                                className="px-8 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50 flex items-center"
                            >
                                {processingId ? <Loader2 className="animate-spin mr-2" /> : <CheckCircle2 className="mr-2" />}
                                Submit Override
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// Application Row Component - expandable
function ApplicationRow({
    app,
    isSelected,
    onSelect,
    onInstantDecision,
    isProcessing,
    activeTab
}: {
    app: Application;
    isSelected: boolean;
    onSelect: () => void;
    onInstantDecision: (decision: 'approved' | 'rejected') => void;
    isProcessing: boolean;
    activeTab: string;
}) {
    const aiDecision = app.ai_result?.decision?.status?.toUpperCase();
    const isApproved = aiDecision?.includes('APPROVED');

    return (
        <div className={`bg-slate-900/50 border rounded-2xl transition-all ${isSelected ? 'border-blue-500 ring-2 ring-blue-500/30' : 'border-slate-800 hover:border-slate-700'
            }`}>
            {/* Header Row - Always Visible */}
            <div
                onClick={onSelect}
                className="p-6 cursor-pointer flex items-center justify-between"
            >
                <div className="flex-1 grid grid-cols-4 gap-4 items-center">
                    <div>
                        <div className="text-xs text-slate-500 font-mono mb-1">#{app.id}</div>
                        <div className="font-bold text-lg text-white">{app.data?.full_name || 'Anonymous'}</div>
                    </div>
                    <div className="text-center">
                        <div className="text-xs text-slate-500 mb-1">Domain</div>
                        <div className="text-sm font-medium text-slate-300 uppercase">{app.domain}</div>
                    </div>
                    <div className="text-center">
                        <div className="text-xs text-slate-500 mb-1">AI Recommendation</div>
                        <div className={`inline-block px-3 py-1 rounded-full text-sm font-bold ${isApproved
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-red-500/20 text-red-400'
                            }`}>
                            {aiDecision || 'PENDING'}
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-xs text-slate-500 mb-1">Confidence</div>
                        <div className="text-sm font-bold text-slate-300">
                            {app.ai_result?.decision?.confidence ? `${(app.ai_result.decision.confidence * 100).toFixed(0)}%` : 'N/A'}
                        </div>
                    </div>
                </div>
                <div className="ml-6">
                    {isSelected ? <ChevronUp className="text-slate-400" /> : <ChevronDown className="text-slate-400" />}
                </div>
            </div>

            {/* Expanded Detail View */}
            {isSelected && (
                <div className="border-t border-slate-800 p-6 space-y-6 animate-in fade-in slide-in-from-top-2">
                    {/* Applicant Data */}
                    <section>
                        <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">Applicant Details</h3>
                        <div className="bg-slate-950 rounded-xl border border-slate-800 p-4 grid grid-cols-2 gap-3">
                            {Object.entries(app.data).map(([key, value]) => (
                                <div key={key} className="flex justify-between py-2 border-b border-slate-900 last:border-0">
                                    <span className="text-slate-400 text-sm">{formatFieldName(key)}</span>
                                    <span className="font-medium text-slate-200 text-sm">{String(value)}</span>
                                </div>
                            ))}
                        </div>
                    </section>

                    {/* Large Explanation Area */}
                    <section>
                        <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center">
                            AI Explanation for {aiDecision}
                        </h3>
                        <div className="bg-slate-950 rounded-xl border border-slate-800 p-6 min-h-[200px]">
                            <p className="text-slate-200 leading-relaxed whitespace-pre-wrap">
                                {app.ai_result?.decision?.reasoning || 'No explanation available'}
                            </p>
                        </div>
                    </section>

                    {/* Large Counterfactual / Alternative Reasoning Area */}
                    <section>
                        <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">
                            {aiDecision?.includes('APPROVED') ? 'Risk Mitigation Steps' : 'Steps to Get Approved'}
                        </h3>
                        <div className="bg-slate-950 rounded-xl border border-slate-800 p-6 min-h-[200px]">
                            {app.ai_result?.counterfactuals && app.ai_result.counterfactuals.length > 0 ? (
                                <ul className="space-y-3 text-slate-200">
                                    {app.ai_result.counterfactuals.map((step, i) => (
                                        <li key={i} className="flex items-start">
                                            <span className="inline-block w-6 h-6 rounded-full bg-blue-500/20 text-blue-400 text-xs font-bold flex items-center justify-center mr-3 mt-0.5 shrink-0">
                                                {i + 1}
                                            </span>
                                            <span className="leading-relaxed">{step}</span>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-slate-400 italic">No counterfactuals available</p>
                            )}
                        </div>
                    </section>

                    {/* Fairness & Metrics */}
                    {app.ai_result?.fairness && (
                        <section>
                            <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">Fairness Assessment</h3>
                            <div className="bg-slate-950 rounded-xl border border-slate-800 p-4">
                                <div className="flex justify-between items-center">
                                    <span className="text-slate-400">Assessment</span>
                                    <span className="text-green-400 font-medium">{app.ai_result.fairness.assessment}</span>
                                </div>
                                <p className="text-xs text-slate-500 mt-2">{app.ai_result.fairness.concerns}</p>
                            </div>
                        </section>
                    )}

                    {/* Action Buttons (Pending only) */}
                    {activeTab === 'pending' && (
                        <div className="pt-6 border-t border-slate-800 flex justify-end space-x-4">
                            <button
                                onClick={() => onInstantDecision('rejected')}
                                disabled={isProcessing}
                                className="px-8 py-4 rounded-xl border border-red-500/30 text-red-400 hover:bg-red-500/10 font-bold transition-colors disabled:opacity-50 flex items-center text-lg"
                            >
                                <XCircle className="mr-2 w-5 h-5" />
                                Deny
                            </button>
                            <button
                                onClick={() => onInstantDecision('approved')}
                                disabled={isProcessing}
                                className="px-10 py-4 rounded-xl bg-green-600 hover:bg-green-500 text-white font-bold shadow-lg shadow-green-500/20 transition-all disabled:opacity-50 flex items-center text-lg"
                            >
                                {isProcessing ? <Loader2 className="animate-spin mr-2 w-5 h-5" /> : <CheckCircle2 className="mr-2 w-5 h-5" />}
                                Approve
                            </button>
                        </div>
                    )}

                    {/* History View */}
                    {activeTab === 'history' && app.final_decision && (
                        <div className="pt-6 border-t border-slate-800">
                            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex items-center space-x-4">
                                <div className={`p-3 rounded-full ${app.final_decision === 'approved' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'}`}>
                                    {app.final_decision === 'approved' ? <CheckCircle2 className="w-6 h-6" /> : <XCircle className="w-6 h-6" />}
                                </div>
                                <div>
                                    <div className="font-bold text-xl capitalize">{app.final_decision}</div>
                                    <div className="text-slate-400 text-sm">
                                        Reviewed on {app.reviewed_at ? new Date(app.reviewed_at).toLocaleString() : 'N/A'}
                                    </div>
                                    {app.is_override && (
                                        <div className="text-amber-400 text-xs mt-1 font-medium">⚠️ AI Decision Overridden</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
