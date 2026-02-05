"use client";

import React, { useState, useEffect } from 'react';
import { ArrowLeft, CheckCircle, XCircle, Clock, Search, Filter, Download } from 'lucide-react';
import Link from 'next/link';

interface AuditEntry {
    application_id: string;
    domain: string;
    submitted_at: string;
    applicant_data: Record<string, any>;
    ai_decision: string;
    ai_confidence: number;
    ai_reasoning: string;
    final_status: string;
    final_decision: string;
    reviewed_at: string | null;
    reviewer_comment: string | null;
    is_override: boolean;
    override_explanation: string | null;
}

export default function AuditTrailPage() {
    const [auditData, setAuditData] = useState<AuditEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [filterStatus, setFilterStatus] = useState<'all' | 'approved' | 'rejected'>('all');
    const [filterDomain, setFilterDomain] = useState<string>('all');

    useEffect(() => {
        fetchAuditLog();
    }, []);

    const fetchAuditLog = async () => {
        try {
            const response = await fetch('http://localhost:8000/audit-log');
            const data = await response.json();
            setAuditData(data);
        } catch (err) {
            console.error('Failed to fetch audit log:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = () => {
        const blob = new Blob([JSON.stringify(auditData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit_trail_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const filteredData = auditData.filter(entry => {
        const matchesSearch = 
            entry.application_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            entry.applicant_data?.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            entry.domain?.toLowerCase().includes(searchQuery.toLowerCase());
        
        const matchesStatus = filterStatus === 'all' || 
            entry.final_decision === filterStatus || 
            entry.final_status === filterStatus ||
            (filterStatus === 'approved' && entry.ai_decision?.toUpperCase() === 'APPROVED') ||
            (filterStatus === 'rejected' && entry.ai_decision?.toUpperCase() === 'REJECTED');
        
        const matchesDomain = filterDomain === 'all' || entry.domain === filterDomain;
        
        return matchesSearch && matchesStatus && matchesDomain;
    });

    const getStatusIcon = (entry: AuditEntry) => {
        const status = entry.final_decision || entry.final_status || entry.ai_decision;
        if (status?.toLowerCase() === 'approved') {
            return <CheckCircle className="w-5 h-5 text-green-400" />;
        } else if (status?.toLowerCase() === 'rejected' || status?.toLowerCase() === 'denied') {
            return <XCircle className="w-5 h-5 text-red-400" />;
        }
        return <Clock className="w-5 h-5 text-amber-400" />;
    };

    const getStatusBadge = (entry: AuditEntry) => {
        const status = entry.final_decision || entry.final_status || entry.ai_decision;
        const isOverride = entry.is_override;
        
        if (status?.toLowerCase() === 'approved') {
            return (
                <span className={`px-3 py-1 rounded-full text-xs font-bold ${isOverride ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-green-500/20 text-green-400'}`}>
                    {isOverride ? 'OVERRIDE → APPROVED' : 'APPROVED'}
                </span>
            );
        } else if (status?.toLowerCase() === 'rejected' || status?.toLowerCase() === 'denied') {
            return (
                <span className={`px-3 py-1 rounded-full text-xs font-bold ${isOverride ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-red-500/20 text-red-400'}`}>
                    {isOverride ? 'OVERRIDE → REJECTED' : 'REJECTED'}
                </span>
            );
        }
        return (
            <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400">
                PENDING
            </span>
        );
    };

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return '-';
        return new Date(dateStr).toLocaleString();
    };

    const domains = [...new Set(auditData.map(e => e.domain).filter(Boolean))];

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <div className="text-cyan-400 text-xl animate-pulse">Loading Audit Trail...</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200 font-sans">
            {/* Ambient Background */}
            <div className="fixed inset-0 pointer-events-none">
                <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-500/5 rounded-full blur-3xl" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/5 rounded-full blur-3xl" />
            </div>

            <div className="relative z-10 max-w-[1600px] mx-auto p-6">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-4">
                        <Link href="/employee" className="p-2 hover:bg-slate-800 rounded-lg transition-colors">
                            <ArrowLeft className="w-5 h-5 text-slate-400" />
                        </Link>
                        <div>
                            <h1 className="text-3xl font-bold text-white">Audit Trail</h1>
                            <p className="text-slate-500 text-sm">Complete history of all application decisions</p>
                        </div>
                    </div>
                    <button
                        onClick={handleDownload}
                        className="flex items-center gap-2 px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 font-semibold rounded-lg transition-all"
                    >
                        <Download className="w-4 h-4" />
                        Export JSON
                    </button>
                </div>

                {/* Filters */}
                <div className="flex flex-wrap gap-4 mb-6 bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-slate-800">
                    <div className="relative flex-1 min-w-[200px]">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <input
                            type="text"
                            placeholder="Search by ID or applicant name..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full bg-slate-950/50 border border-slate-700 rounded-lg pl-10 pr-4 py-2 text-sm focus:border-cyan-500/50 outline-none"
                        />
                    </div>
                    <select
                        value={filterStatus}
                        onChange={(e) => setFilterStatus(e.target.value as any)}
                        className="bg-slate-950/50 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:border-cyan-500/50 outline-none"
                    >
                        <option value="all">All Status</option>
                        <option value="approved">Approved</option>
                        <option value="rejected">Rejected</option>
                    </select>
                    <select
                        value={filterDomain}
                        onChange={(e) => setFilterDomain(e.target.value)}
                        className="bg-slate-950/50 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:border-cyan-500/50 outline-none"
                    >
                        <option value="all">All Domains</option>
                        {domains.map(d => (
                            <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                        ))}
                    </select>
                </div>

                {/* Stats Summary */}
                <div className="grid grid-cols-4 gap-4 mb-6">
                    <div className="bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-slate-800">
                        <div className="text-2xl font-bold text-white">{auditData.length}</div>
                        <div className="text-slate-500 text-sm">Total Applications</div>
                    </div>
                    <div className="bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-green-500/20">
                        <div className="text-2xl font-bold text-green-400">
                            {auditData.filter(e => (e.final_decision || e.ai_decision)?.toLowerCase() === 'approved').length}
                        </div>
                        <div className="text-slate-500 text-sm">Approved</div>
                    </div>
                    <div className="bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-red-500/20">
                        <div className="text-2xl font-bold text-red-400">
                            {auditData.filter(e => ['rejected', 'denied'].includes((e.final_decision || e.ai_decision)?.toLowerCase())).length}
                        </div>
                        <div className="text-slate-500 text-sm">Rejected</div>
                    </div>
                    <div className="bg-slate-900/60 backdrop-blur-md p-4 rounded-xl border border-blue-500/20">
                        <div className="text-2xl font-bold text-blue-400">
                            {auditData.filter(e => e.is_override).length}
                        </div>
                        <div className="text-slate-500 text-sm">Overrides</div>
                    </div>
                </div>

                {/* Audit Trail Table */}
                <div className="bg-slate-900/60 backdrop-blur-md rounded-xl border border-slate-800 overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="bg-slate-800/50 border-b border-slate-700">
                                    <th className="text-left px-6 py-4 text-xs font-bold uppercase text-slate-400 tracking-wider">Status</th>
                                    <th className="text-left px-6 py-4 text-xs font-bold uppercase text-slate-400 tracking-wider">Application ID</th>
                                    <th className="text-left px-6 py-4 text-xs font-bold uppercase text-slate-400 tracking-wider">Domain</th>
                                    <th className="text-left px-6 py-4 text-xs font-bold uppercase text-slate-400 tracking-wider">Applicant</th>
                                    <th className="text-left px-6 py-4 text-xs font-bold uppercase text-slate-400 tracking-wider">AI Decision</th>
                                    <th className="text-left px-6 py-4 text-xs font-bold uppercase text-slate-400 tracking-wider">Confidence</th>
                                    <th className="text-left px-6 py-4 text-xs font-bold uppercase text-slate-400 tracking-wider">Submitted</th>
                                    <th className="text-left px-6 py-4 text-xs font-bold uppercase text-slate-400 tracking-wider">Reviewed</th>
                                    <th className="text-left px-6 py-4 text-xs font-bold uppercase text-slate-400 tracking-wider">Comment</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredData.length === 0 ? (
                                    <tr>
                                        <td colSpan={9} className="text-center py-12 text-slate-500">
                                            No audit entries found matching your criteria.
                                        </td>
                                    </tr>
                                ) : (
                                    filteredData.map((entry, idx) => (
                                        <tr 
                                            key={entry.application_id || idx} 
                                            className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
                                        >
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-2">
                                                    {getStatusIcon(entry)}
                                                    {getStatusBadge(entry)}
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className="font-mono text-sm text-cyan-400">{entry.application_id || '-'}</span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={`px-2 py-1 rounded-md text-xs font-semibold uppercase ${
                                                    entry.domain === 'loan' ? 'bg-blue-500/10 text-blue-400' :
                                                    entry.domain === 'insurance' ? 'bg-purple-500/10 text-purple-400' :
                                                    entry.domain === 'credit' ? 'bg-amber-500/10 text-amber-400' :
                                                    entry.domain === 'job' ? 'bg-green-500/10 text-green-400' :
                                                    'bg-slate-700 text-slate-300'
                                                }`}>
                                                    {entry.domain || '-'}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="text-sm text-white font-medium">
                                                    {entry.applicant_data?.full_name || entry.applicant_data?.name || 'Anonymous'}
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={`text-sm font-semibold ${
                                                    entry.ai_decision?.toUpperCase() === 'APPROVED' ? 'text-green-400' : 'text-red-400'
                                                }`}>
                                                    {entry.ai_decision || '-'}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                {entry.ai_confidence ? (
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-16 h-2 bg-slate-800 rounded-full overflow-hidden">
                                                            <div 
                                                                className="h-full bg-cyan-500 rounded-full"
                                                                style={{ width: `${Math.round(entry.ai_confidence * 100)}%` }}
                                                            />
                                                        </div>
                                                        <span className="text-xs text-slate-400">
                                                            {Math.round(entry.ai_confidence * 100)}%
                                                        </span>
                                                    </div>
                                                ) : (
                                                    <span className="text-slate-500">-</span>
                                                )}
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className="text-xs text-slate-400">{formatDate(entry.submitted_at)}</span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className="text-xs text-slate-400">{formatDate(entry.reviewed_at)}</span>
                                            </td>
                                            <td className="px-6 py-4 max-w-[200px]">
                                                <span className="text-xs text-slate-400 truncate block" title={entry.reviewer_comment || ''}>
                                                    {entry.reviewer_comment || '-'}
                                                </span>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Footer */}
                <div className="mt-4 text-center text-slate-600 text-sm">
                    Showing {filteredData.length} of {auditData.length} entries
                </div>
            </div>
        </div>
    );
}
