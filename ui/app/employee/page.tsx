"use client";

import React, { useState, useEffect, useRef } from 'react';
import {
    ArrowLeft, Search, Download, Loader2, TrendingUp, CheckCircle2, XCircle,
    AlertTriangle, Clock, Filter, Upload, FileText, Zap, ChevronRight, User
} from 'lucide-react';
import Link from 'next/link';
import { getApplications, reviewApplication, Application } from '../../lib/api';

const DOMAINS = ['loan', 'credit', 'insurance', 'job'];

export default function EmployeeDashboard() {
    const [activeTab, setActiveTab] = useState<'pending' | 'history'>('pending');
    const [applications, setApplications] = useState<Application[]>([]);
    const [selectedApp, setSelectedApp] = useState<Application | null>(null);
    const [loading, setLoading] = useState(true);
    const [processingId, setProcessingId] = useState<string | null>(null);
    const [filterDomain, setFilterDomain] = useState<string>('all');
    
    // Batch Upload State
    const [isUploading, setIsUploading] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        fetchApplications();
        const interval = setInterval(fetchApplications, 5000); // Polling for background updates
        return () => clearInterval(interval);
    }, [activeTab]);

    const fetchApplications = async () => {
        if (applications.length === 0) setLoading(true);
        try {
            const status = activeTab === 'pending' ? 'pending_human' : 'completed';
            const data = await getApplications(status);
            setApplications(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleDecision = async (decision: 'approved' | 'rejected') => {
        if (!selectedApp) return;
        
        const appId = selectedApp.id;
        
        // Optimistic UI Update: Remove immediately
        setApplications(prev => prev.filter(app => app.id !== appId));
        setSelectedApp(null);
        
        try {
            await reviewApplication(appId, decision, "Manual review by employee");
        } catch (err) {
            console.error("Decision failed", err);
            // Revert on error (optional, skipping for demo speed)
            alert("Failed to submit decision. Please refresh.");
        }
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || !e.target.files[0]) return;
        
        const file = e.target.files[0];
        setIsUploading(true);
        
        const formData = new FormData();
        formData.append('file', file);
        // Default to 'loan' or let user select. For demo, we'll ask or default.
        // Let's prompt purely via JS for simplicity or default to loan.
        const type = prompt("Enter domain type (loan, credit, insurance, job):", "loan") || "loan";
        
        try {
            // We need a direct fetch here because it's a new endpoint not in api.ts yet
            await fetch(`http://localhost:8000/applications/batch_upload?decision_type=${type}`, {
                method: 'POST',
                body: formData
            });
            alert("Batch processed successfully!");
            fetchApplications();
        } catch (err) {
            console.error(err);
            alert("Upload failed");
        } finally {
            setIsUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const filteredApps = applications.filter(app => 
        filterDomain === 'all' ? true : app.domain === filterDomain
    );

    const getScoreColor = (score: number) => {
        if (score >= 80) return 'text-green-400';
        if (score >= 50) return 'text-amber-400';
        return 'text-red-400';
    };

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-cyan-500/30">
            {/* Ambient Background */}
            <div className="fixed inset-0 pointer-events-none">
                <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-500/5 rounded-full blur-3xl" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/5 rounded-full blur-3xl" />
            </div>

            <div className="relative z-10 flex h-screen overflow-hidden max-w-[1600px] mx-auto border-x border-slate-800/50 shadow-2xl">
                
                {/* Compact Sidebar */}
                <div className="w-80 flex-shrink-0 border-r border-slate-800 bg-slate-900/60 backdrop-blur-md flex flex-col">
                    <div className="p-6 border-b border-slate-800/50">
                        <div className="flex items-center justify-between mb-6">
                            <div className="flex items-center space-x-2 text-cyan-400">
                                <Zap className="w-6 h-6 fill-current" />
                                <span className="font-bold text-lg tracking-tight text-white">XAI Cortex</span>
                            </div>
                            <Link 
                                href="/audit-trail"
                                className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 text-xs font-semibold rounded-lg transition-all"
                            >
                                <FileText className="w-3.5 h-3.5" />
                                Audit Trail
                            </Link>
                        </div>
                        
                        <div className="flex bg-slate-800/50 p-1 rounded-lg mb-6">
                            {(['pending', 'history'] as const).map(tab => (
                                <button
                                    key={tab}
                                    onClick={() => { setActiveTab(tab); setSelectedApp(null); }}
                                    className={`flex-1 py-2 text-xs font-semibold uppercase tracking-wider rounded-md transition-all ${
                                        activeTab === tab 
                                        ? 'bg-slate-700 text-white shadow-lg' 
                                        : 'text-slate-500 hover:text-slate-300'
                                    }`}
                                >
                                    {tab}
                                </button>
                            ))}
                        </div>

                        <div className="flex space-x-2">
                             <div className="relative flex-1">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                                <input 
                                    placeholder="Search..." 
                                    className="w-full bg-slate-950/50 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm focus:border-cyan-500/50 outline-none transition-colors"
                                />
                            </div>
                            <button 
                                onClick={() => fileInputRef.current?.click()}
                                disabled={isUploading}
                                className="p-2 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 text-slate-400 hover:text-white transition-colors"
                                title="Upload Batch CSV"
                            >
                                {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                            </button>
                            <input type="file" ref={fileInputRef} hidden accept=".csv" onChange={handleFileUpload} />
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 scrollbar-thin scrollbar-thumb-slate-800">
                        {loading && <div className="text-center p-4"><Loader2 className="w-6 h-6 animate-spin mx-auto text-cyan-500" /></div>}
                        
                        {!loading && filteredApps.length === 0 && (
                            <div className="text-center p-8 text-slate-600 text-sm">No applications found.</div>
                        )}

                        {filteredApps.map(app => (
                            <div
                                key={app.id}
                                onClick={() => setSelectedApp(app)}
                                className={`group p-4 rounded-xl border cursor-pointer transition-all duration-200 relative overflow-hidden ${
                                    selectedApp?.id === app.id
                                    ? 'bg-cyan-900/10 border-cyan-500/50 shadow-[0_0_20px_rgba(6,182,212,0.1)]'
                                    : 'bg-slate-900/40 border-slate-800 hover:border-slate-700 hover:bg-slate-800/40'
                                }`}
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <span className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded-full ${
                                        app.domain === 'loan' ? 'bg-blue-500/10 text-blue-400' :
                                        app.domain === 'insurance' ? 'bg-purple-500/10 text-purple-400' :
                                        'bg-slate-700 text-slate-300'
                                    }`}>
                                        {app.domain}
                                    </span>
                                    <span className="text-[10px] font-mono text-slate-600">{app.id}</span>
                                </div>
                                <h3 className="font-semibold text-slate-200 group-hover:text-white transition-colors truncate">
                                    {app.data.full_name || 'Anonymous Applicant'}
                                </h3>
                                <div className="mt-3 flex items-center justify-between">
                                    <div className="flex items-center space-x-2 text-xs text-slate-500">
                                        <Clock className="w-3 h-3" />
                                        <span>{new Date(app.timestamp).toLocaleDateString()}</span>
                                    </div>
                                    {app.ai_result && (
                                        <div className={`text-xs font-bold ${
                                            app.ai_result.decision.status.toUpperCase() === 'APPROVED' ? 'text-green-400' : 'text-red-400'
                                        }`}>
                                            {app.ai_result.decision.confidence ? Math.round(app.ai_result.decision.confidence * 100) : 0}% Conf.
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Main Detail Area */}
                <div className="flex-1 flex flex-col bg-slate-950/80 backdrop-blur-sm">
                    {selectedApp ? (
                        <>
                            <header className="px-8 py-6 border-b border-slate-800/50 flex justify-between items-start bg-slate-900/20">
                                <div>
                                    <div className="flex items-center space-x-3 mb-1">
                                        <h1 className="text-2xl font-bold text-white tracking-tight">{selectedApp.data.full_name || 'Applicant'}</h1>
                                        <span className="text-slate-500 text-sm font-mono">#{selectedApp.id}</span>
                                    </div>
                                    <div className="flex items-center space-x-2 text-sm text-slate-400">
                                        <User className="w-4 h-4" />
                                        <span>{selectedApp.data.email || 'No contact info'}</span>
                                    </div>
                                </div>
                                
                                <div className="flex items-center space-x-4">
                                     {selectedApp.ai_result && (
                                        <div className={`flex flex-col items-end px-4 py-2 rounded-lg border ${
                                            selectedApp.ai_result.decision.status.toUpperCase() === 'APPROVED' 
                                            ? 'bg-green-500/5 border-green-500/20' 
                                            : 'bg-red-500/5 border-red-500/20'
                                        }`}>
                                            <span className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">AI Rec.</span>
                                            <span className={`text-lg font-bold ${
                                                selectedApp.ai_result.decision.status.toUpperCase() === 'APPROVED' ? 'text-green-400' : 'text-red-400'
                                            }`}>
                                                {selectedApp.ai_result.decision.status}
                                            </span>
                                        </div>
                                     )}
                                </div>
                            </header>

                            <div className="flex-1 overflow-y-auto p-8">
                                <div className="grid grid-cols-12 gap-8">
                                    
                                    {/* Left Column: Data */}
                                    <div className="col-span-12 lg:col-span-5 space-y-6">
                                        <div className="bg-slate-900/40 rounded-2xl border border-slate-800 p-6">
                                            <h3 className="text-sm font-bold text-cyan-400 uppercase tracking-wider mb-6 flex items-center">
                                                <FileText className="w-4 h-4 mr-2" /> Application Data
                                            </h3>
                                            <div className="space-y-4">
                                                {Object.entries(selectedApp.data).map(([k, v]) => {
                                                    if (typeof v === 'object') return null;
                                                    return (
                                                        <div key={k} className="flex justify-between items-center py-2 border-b border-slate-800/50 last:border-0">
                                                            <span className="text-slate-500 capitalize text-sm">{k.replace(/_/g, ' ')}</span>
                                                            <span className="text-slate-200 font-medium text-sm text-right px-2">{String(v)}</span>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Right Column: AI Analysis */}
                                    <div className="col-span-12 lg:col-span-7 space-y-6">
                                        {selectedApp.ai_result && (
                                            <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500">
                                                
                                                {/* Reasoning Card */}
                                                <div className="bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800 rounded-2xl border border-slate-700/50 p-6 shadow-xl relative overflow-hidden">
                                                    <div className="absolute top-0 right-0 p-3 opacity-10">
                                                        <Zap className="w-24 h-24 text-cyan-500" />
                                                    </div>
                                                    
                                                    <h3 className="text-sm font-bold text-purple-400 uppercase tracking-wider mb-4">Decision Reasoning</h3>
                                                    <p className="text-lg leading-relaxed text-slate-200 font-light">
                                                        {selectedApp.ai_result.decision.reasoning}
                                                    </p>
                                                </div>

                                                {/* Metrics & Fairness */}
                                                <div className="grid grid-cols-2 gap-4">
                                                    <div className="bg-slate-900/40 rounded-xl border border-slate-800 p-5">
                                                        <div className="text-slate-500 text-xs font-bold uppercase mb-2">Fairness Check</div>
                                                        <div className="text-green-400 font-medium mb-1">
                                                            {selectedApp.ai_result.fairness.assessment}
                                                        </div>
                                                        <p className="text-xs text-slate-500 leading-tight">
                                                            {selectedApp.ai_result.fairness.concerns}
                                                        </p>
                                                    </div>
                                                    
                                                    <div className="bg-slate-900/40 rounded-xl border border-slate-800 p-5">
                                                        <div className="text-slate-500 text-xs font-bold uppercase mb-2">Risk Score</div>
                                                        <div className="flex items-end">
                                                            <span className="text-3xl font-bold text-white">
                                                                {selectedApp.ai_result.key_metrics?.risk_score || 50}
                                                            </span>
                                                            <span className="text-slate-500 mb-1 ml-1">/100</span>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Counterfactuals */}
                                                {selectedApp.ai_result.counterfactuals?.length > 0 && (
                                                    <div className="bg-slate-900/40 rounded-2xl border border-slate-800 p-6">
                                                       <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">Steps to Approval</h3>
                                                       <ul className="space-y-3">
                                                           {selectedApp.ai_result.counterfactuals.map((step: any, i: number) => (
                                                               <li key={i} className="flex items-start text-sm text-slate-300">
                                                                   <span className="flex-shrink-0 w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-xs mr-3 mt-0.5 text-slate-500">{i+1}</span>
                                                                   <span>{typeof step === 'string' ? step : JSON.stringify(step)}</span>
                                                               </li>
                                                           ))}
                                                       </ul>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Sticky Footer for Actions */}
                            {activeTab === 'pending' && (
                                <div className="p-6 border-t border-slate-800/50 bg-slate-900/80 backdrop-blur-md flex justify-between items-center">
                                    <div className="text-xs text-slate-500">
                                        Decisions are final and logged in the immutable ledger.
                                    </div>
                                    <div className="flex space-x-4">
                                        <button 
                                            onClick={() => handleDecision('rejected')}
                                            className="px-6 py-2.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 hover:border-red-500/40 transition-all font-medium text-sm focus:ring-2 focus:ring-red-500/20"
                                        >
                                            Reject Case
                                        </button>
                                        <button 
                                            onClick={() => handleDecision('approved')}
                                            className="px-8 py-2.5 rounded-lg bg-green-500 hover:bg-green-400 text-black font-bold shadow-[0_0_20px_rgba(34,197,94,0.2)] hover:shadow-[0_0_30px_rgba(34,197,94,0.4)] transition-all transform hover:-translate-y-0.5 text-sm flex items-center focus:ring-2 focus:ring-green-500/50"
                                        >
                                            <CheckCircle2 className="w-4 h-4 mr-2" />
                                            Approve Case
                                        </button>
                                    </div>
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-slate-600">
                            <div className="w-24 h-24 bg-slate-900/50 rounded-full flex items-center justify-center mb-6">
                                <Search className="w-10 h-10 opacity-50" />
                            </div>
                            <p className="text-lg font-medium text-slate-400">Select an application to begin review</p>
                            <p className="text-sm mt-2">Use the sidebar to filter or search applications</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}