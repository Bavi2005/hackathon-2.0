"use client";

import React, { useState, useEffect } from 'react';
import {
    ArrowLeft, Search, Download, Loader2, TrendingUp, CheckCircle2, XCircle,
    AlertTriangle, Clock, Filter
} from 'lucide-react';
import Link from 'next/link';
import { getApplications, reviewApplication, Application } from '../../lib/api';

export default function EmployeeDashboard() {
    const [activeTab, setActiveTab] = useState<'pending' | 'history'>('pending');
    const [applications, setApplications] = useState<Application[]>([]);
    const [selectedApp, setSelectedApp] = useState<Application | null>(null);
    const [loading, setLoading] = useState(true);
    const [processingId, setProcessingId] = useState<string | null>(null);

    useEffect(() => {
        console.log("EmployeeDashboard mounted");
        fetchApplications();
        // Add polling to refresh data every 5 seconds
        const interval = setInterval(fetchApplications, 5000);
        return () => {
            console.log("EmployeeDashboard unmounting");
            clearInterval(interval);
        };
    }, [activeTab]);

    const fetchApplications = async () => {
        // Only show loading on initial fetch
        if (applications.length === 0) setLoading(true);
        try {
            const status = activeTab === 'pending' ? 'pending_human' : 'completed';
            console.log(`[API] Fetching ${activeTab} applications from http://localhost:8000...`);
            const data = await getApplications(status);
            console.log(`[API] Success! Received ${data.length} applications`);
            setApplications(data);
        } catch (err) {
            console.error("[API] Error fetching applications:", err);
        } finally {
            setLoading(false);
        }
    };

    const handleDecision = async (decision: 'approved' | 'rejected') => {
        if (!selectedApp) return;
        setProcessingId(selectedApp.id);
        try {
            await reviewApplication(selectedApp.id, decision, "Manual review by employee");
            // Remove from list or move to history
            setApplications(prev => prev.filter(app => app.id !== selectedApp.id));
            setSelectedApp(null);
        } catch (err) {
            console.error(err);
            alert("Failed to submit decision");
        } finally {
            setProcessingId(null);
        }
    };

    const getConfidenceColor = (conf: number) => {
        if (conf >= 0.8) return 'text-green-400';
        if (conf >= 0.6) return 'text-amber-400';
        return 'text-red-400';
    };

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
                        className={`w-full text-left px-4 py-3 rounded-xl transition-all font-medium flex items-center justify-between ${activeTab === 'history'
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
                                ? 'AI-processed applications awaiting human validation'
                                : 'Archive of past decisions'}
                        </p>
                    </div>
                    <div className="flex space-x-3">
                        <button className="p-2 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors">
                            <Filter className="w-5 h-5 text-slate-400" />
                        </button>
                        <button onClick={fetchApplications} className="p-2 bg-slate-800 rounded-lg hover:bg-slate-700 transition-colors">
                            <Clock className="w-5 h-5 text-slate-400" />
                        </button>
                    </div>
                </header>

                <div className="flex-1 grid grid-cols-12 gap-6 overflow-hidden">
                    {/* List View */}
                    <div className="col-span-4 bg-slate-900/50 rounded-2xl border border-slate-800 flex flex-col overflow-hidden">
                        <div className="p-4 border-b border-slate-800">
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                <input
                                    type="text"
                                    placeholder="Search applicants..."
                                    className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-10 pr-4 py-2 text-sm focus:ring-1 focus:ring-blue-500 outline-none"
                                />
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto p-2 space-y-2">
                            {loading ? (
                                <div className="flex justify-center p-8"><Loader2 className="animate-spin text-slate-500" /></div>
                            ) : applications.length === 0 ? (
                                <div className="p-8 text-center text-slate-500">No applications found.</div>
                            ) : (
                                applications.map((app) => (
                                    <div
                                        key={app.id}
                                        onClick={() => setSelectedApp(app)}
                                        className={`p-4 rounded-xl border cursor-pointer transition-all ${selectedApp?.id === app.id
                                            ? 'bg-blue-600/10 border-blue-500/50 ring-1 ring-blue-500/50'
                                            : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                                            }`}
                                    >
                                        <div className="flex justify-between items-start mb-1">
                                            <span className="font-mono text-xs text-slate-500">#{app.id}</span>
                                            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">{app.domain}</span>
                                        </div>
                                        <div className="font-semibold truncate">
                                            Applicant Data...
                                        </div>
                                        <div className="text-xs text-slate-400 mt-2 flex justify-between items-center">
                                            <span>{new Date(app.timestamp).toLocaleDateString()}</span>
                                            {app.ai_result && (
                                                <span className={`flex items-center ${getConfidenceColor(app.ai_result.decision.confidence)}`}>
                                                    {(app.ai_result.decision.confidence * 100).toFixed(0)}% AI Conf.
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Detail View */}
                    <div className="col-span-8 bg-slate-900 rounded-2xl border border-slate-800 overflow-y-auto p-8">
                        {selectedApp ? (
                            <div className="space-y-8 animate-in fade-in slide-in-from-right-4">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <div className="flex items-center space-x-3 mb-2">
                                            <h2 className="text-3xl font-bold">Application #{selectedApp.id}</h2>
                                            <span className="px-3 py-1 rounded-full bg-slate-800 text-slate-300 text-sm font-medium uppercase">{selectedApp.domain}</span>
                                        </div>
                                        <p className="text-slate-400">Submitted on {new Date(selectedApp.timestamp).toLocaleString()}</p>
                                    </div>
                                    {selectedApp.ai_result && (
                                        <div className={`px-4 py-2 rounded-lg border ${selectedApp.ai_result.decision.status.includes('APPROVED')
                                            ? 'bg-green-500/10 border-green-500/30 text-green-400'
                                            : 'bg-red-500/10 border-red-500/30 text-red-400'
                                            }`}>
                                            <div className="text-xs font-bold uppercase tracking-wider mb-1">AI Recommendation</div>
                                            <div className="font-bold text-lg">{selectedApp.ai_result.decision.status}</div>
                                        </div>
                                    )}
                                </div>

                                <div className="grid grid-cols-2 gap-6">
                                    <div className="space-y-6">
                                        <section>
                                            <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">Applicant Data</h3>
                                            <div className="bg-slate-950 rounded-xl border border-slate-800 p-4 space-y-2">
                                                {Object.entries(selectedApp.data).map(([key, value]) => (
                                                    <div key={key} className="flex justify-between py-1 border-b border-slate-900 last:border-0">
                                                        <span className="text-slate-400 capitalize">{key.replace('_', ' ')}</span>
                                                        <span className="font-medium text-slate-200">{String(value)}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </section>
                                    </div>

                                    <div className="space-y-6">
                                        {selectedApp.ai_result && (
                                            <section>
                                                <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center">
                                                    <TrendingUp className="w-4 h-4 mr-2" /> AI Insights
                                                </h3>
                                                <div className="bg-slate-950 rounded-xl border border-slate-800 p-6 space-y-4">
                                                    <div>
                                                        <div className="text-slate-400 text-sm mb-1">Reasoning</div>
                                                        <p className="text-slate-200 leading-relaxed">{selectedApp.ai_result.decision.reasoning}</p>
                                                    </div>

                                                    {selectedApp.ai_result.fairness && (
                                                        <div className="pt-4 border-t border-slate-900">
                                                            <div className="flex justify-between items-center mb-1">
                                                                <span className="text-slate-400 text-sm">Fairness Check</span>
                                                                <span className="text-green-400 text-sm font-medium">{selectedApp.ai_result.fairness.assessment}</span>
                                                            </div>
                                                            <p className="text-xs text-slate-500">{selectedApp.ai_result.fairness.concerns}</p>
                                                        </div>
                                                    )}

                                                    {selectedApp.ai_result.counterfactuals && selectedApp.ai_result.counterfactuals.length > 0 && (
                                                        <div className="pt-4 border-t border-slate-900">
                                                            <div className="text-slate-400 text-sm mb-2">Counterfactuals</div>
                                                            <ul className="text-xs text-slate-300 space-y-1 list-disc list-inside">
                                                                {selectedApp.ai_result.counterfactuals.map((c: any, i: number) => (
                                                                    <li key={i}>{JSON.stringify(c)}</li>
                                                                ))}
                                                            </ul>
                                                        </div>
                                                    )}
                                                </div>
                                            </section>
                                        )}
                                    </div>
                                </div>

                                {activeTab === 'pending' && (
                                    <div className="pt-8 border-t border-slate-800 flex justify-end space-x-4">
                                        <button
                                            onClick={() => handleDecision('rejected')}
                                            disabled={!!processingId}
                                            className="px-6 py-3 rounded-xl border border-red-500/30 text-red-400 hover:bg-red-500/10 font-medium transition-colors disabled:opacity-50"
                                        >
                                            Reject Application
                                        </button>
                                        <button
                                            onClick={() => handleDecision('approved')}
                                            disabled={!!processingId}
                                            className="px-8 py-3 rounded-xl bg-green-600 hover:bg-green-500 text-white font-bold shadow-lg shadow-green-500/20 transition-all disabled:opacity-50 flex items-center"
                                        >
                                            {processingId === selectedApp.id ? <Loader2 className="animate-spin mr-2" /> : <CheckCircle2 className="mr-2" />}
                                            Approve Application
                                        </button>
                                    </div>
                                )}

                                {activeTab === 'history' && (
                                    <div className="pt-8 border-t border-slate-800">
                                        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex items-center space-x-4">
                                            <div className={`p-2 rounded-full ${selectedApp.final_decision === 'approved' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'}`}>
                                                {selectedApp.final_decision === 'approved' ? <CheckCircle2 /> : <XCircle />}
                                            </div>
                                            <div>
                                                <div className="font-bold text-lg capitalize">{selectedApp.final_decision}</div>
                                                <div className="text-slate-400 text-sm">Reviewed on {selectedApp.reviewed_at ? new Date(selectedApp.reviewed_at).toLocaleString() : 'N/A'}</div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="h-full flex flex-col items-center justify-center text-slate-500 opacity-50">
                                <Search size={48} className="mb-4" />
                                <p className="text-xl font-medium">Select an application to view details</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
