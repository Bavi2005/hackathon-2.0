import React, { useState, useEffect, useMemo, useRef } from 'react';
import { ArrowLeft, Search, CheckCircle2, AlertCircle, User, Hash, Clock, Check, X, Settings, Edit, Upload, Loader2, FileText } from 'lucide-react';
import Link from 'next/link';
import { CaseData } from '../lib/types';
import { CATEGORIES, CATEGORY_CONFIG } from '../lib/constants';
import DonutChart from './DonutChart';
import { api } from '../lib/api';
import PolicyManager from './PolicyManager';
import ExplanationEditor from './ExplanationEditor';

interface EmployeeDashboardProps {
	onBack: () => void;
}

type FilterType = 'All' | 'Approved' | 'Denied' | 'Pending';

type CategoryState = {
	searchQuery: string;
	activeCase: CaseData | null;
	filter: FilterType;
};

export default function EmployeeDashboard({ onBack }: EmployeeDashboardProps) {
	const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
	const [showPolicyManager, setShowPolicyManager] = useState(false);

	const [explanationEditorState, setExplanationEditorState] = useState<{
		isOpen: boolean;
		mode: 'edit' | 'override';
		initialText: string;
		action?: 'Approved' | 'Denied';
	}>({ isOpen: false, mode: 'edit', initialText: '' });

	// Per-category state persistence
	const [categoryStates, setCategoryStates] = useState<Record<string, CategoryState>>({});

	const [realData, setRealData] = useState<{ [key: string]: CaseData[] }>({ loan: [], job: [], insurance: [], credit: [] });
	const [loading, setLoading] = useState(true);

	// CSV Upload State
	const [isUploading, setIsUploading] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);

	const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
		if (!e.target.files || !e.target.files[0]) return;
		
		const file = e.target.files[0];
		if (!file.name.endsWith('.csv')) {
			alert('Please upload a CSV file');
			return;
		}
		
		setIsUploading(true);
		
		const formData = new FormData();
		formData.append('file', file);
		
		// Use current selected category or ask user
		const type = selectedCategory || prompt("Enter domain type (loan, credit, insurance, job):", "loan") || "loan";
		
		try {
			const response = await fetch(`http://localhost:8000/applications/batch_csv?decision_type=${type}`, {
				method: 'POST',
				body: formData
			});
			
			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Upload failed');
			}
			
			const result = await response.json();
			alert(`Successfully processed ${result.count} applications from CSV!`);
			
			// Refresh data
			const newData = await api.getApplications();
			setRealData(newData);
		} catch (err: any) {
			console.error(err);
			alert(`Upload failed: ${err.message}`);
		} finally {
			setIsUploading(false);
			if (fileInputRef.current) fileInputRef.current.value = '';
		}
	};

	// Poll for new data every 5 seconds (to catch new submissions)
	useEffect(() => {
		let interval: NodeJS.Timeout;
		const loadData = async () => {
			const data = await api.getApplications();
			setRealData(data);
			setLoading(false);
		};

		loadData();
		interval = setInterval(loadData, 5000); // Polling for live updates
		return () => clearInterval(interval);
	}, []);

	// Helper to determine specific colors and labels based on category
	const getStats = (data: CaseData[], categoryId: string) => {
		const positiveTerms = ['approved', 'hired', 'low risk', 'low_risk'];
		// "Pending" is distinct
		const pending = data.filter(d => d.model_output.label === 'Pending').length;
		const approved = data.filter(d => positiveTerms.includes(d.model_output.label?.toLowerCase())).length;
		const declined = data.length - approved - pending;
		return { pending, approved, declined, total: data.length };
	};

	const categoriesWithStats = useMemo(() => {
		return CATEGORIES.map(cat => ({
			...cat,
			...getStats(realData[cat.id as keyof typeof realData] || [], cat.id)
		}));
	}, [realData]);

	// Current State Accessors
	const getCurrentState = () => selectedCategory ? (categoryStates[selectedCategory] || { searchQuery: '', activeCase: null, filter: 'Pending' }) : { searchQuery: '', activeCase: null, filter: 'Pending' };

	const updateState = (updates: Partial<CategoryState>) => {
		if (!selectedCategory) return;
		setCategoryStates(prev => ({
			...prev,
			[selectedCategory]: { ...(prev[selectedCategory] || { searchQuery: '', activeCase: null, filter: 'Pending' }), ...updates }
		}));
	};

	const { searchQuery, activeCase, filter } = getCurrentState();

	const handleAction = async (action: 'Approved' | 'Denied') => {
		if (!selectedCategory || !activeCase) return;

		// INSTANT APPROVAL
		if (action === 'Approved') {
			let explanation = "Manually approved by auditor based on provided evidence.";

			// Use AI reasoning if available
			if (activeCase.ai_result) {
				if (activeCase.ai_result.decision.status.toLowerCase() === 'approved') {
					explanation = activeCase.ai_result.decision.reasoning;
				} else {
					explanation = activeCase.ai_result.alternative_reasoning || explanation;
				}
			}

			await api.updateApplicationStatus(activeCase.decision_id, selectedCategory, action, explanation);

			// Force reload locally to reflect change instantly
			const newData = await api.getApplications();
			setRealData(newData);

			const updatedCase = newData[selectedCategory].find(c => c.decision_id === activeCase.decision_id);
			if (updatedCase) updateState({ activeCase: updatedCase });
			return;
		}

		// DENY WITH OVERRIDE POPUP
		if (action === 'Denied') {
			let explanation = "Manually denied by auditor due to policy mismatch.";

			// Use AI reasoning if available
			if (activeCase.ai_result) {
				if (activeCase.ai_result.decision.status.toLowerCase() === 'rejected') {
					explanation = activeCase.ai_result.decision.reasoning;
				} else {
					explanation = activeCase.ai_result.alternative_reasoning || explanation;
				}
			}

			setExplanationEditorState({
				isOpen: true,
				mode: 'override',
				initialText: explanation,
				action: 'Denied'
			});
		}
	};


	const filteredCases = useMemo(() => {
		if (!selectedCategory) return [];

		let cases = realData[selectedCategory as keyof typeof realData] || [];

		// Filter Logic
		const positiveTerms = ['approved', 'hired', 'low risk', 'low_risk'];

		if (filter === 'Pending') {
			cases = cases.filter(c => c.model_output.label === 'Pending');
		} else if (filter !== 'All') {
			cases = cases.filter(c => {
				if (c.model_output.label === 'Pending') return false;
				const isPositive = positiveTerms.includes(c.model_output.label.toLowerCase());
				return filter === 'Approved' ? isPositive : !isPositive;
			});
		}

		// Search Logic
		return cases.filter((c: CaseData) =>
			(c.input_features?.applicant_id?.toString() || '').includes(searchQuery) ||
			(c.decision_id?.toLowerCase() || '').includes(searchQuery.toLowerCase())
		);
	}, [selectedCategory, realData, searchQuery, filter]);


	if (loading) return <div className="min-h-screen bg-[#1a100e] flex items-center justify-center text-amber-500 font-black tracking-widest animate-pulse">LOADING DASHBOARD DATA...</div>;



	// --- CATEGORY SELECTION VIEW ---
	if (!selectedCategory) {
		return (
			<div className="min-h-screen bg-[#1a100e] text-amber-50 flex flex-col items-center justify-center p-8 relative overflow-hidden">
				{/* BACKGROUND */}
				<div className="absolute inset-0 bg-cover bg-center opacity-40" style={{ backgroundImage: 'url(/employee_portal_bg.png)' }} />
				<div className="absolute inset-0 bg-gradient-to-b from-[#1a100e]/60 via-transparent to-[#1a100e]" />

				<button onClick={onBack} className="absolute top-8 left-8 flex items-center gap-2 text-amber-500 hover:text-amber-400 font-bold z-20"><ArrowLeft size={20} /> Back</button>
				
				{/* Audit Trail Link */}
				<Link 
					href="/audit-trail" 
					className="absolute top-8 right-8 flex items-center gap-2 px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-500 font-bold rounded-xl z-20 transition-all"
				>
					<FileText size={18} /> Audit Trail
				</Link>
				
				<h1 className="text-5xl font-black text-white mb-12">Employee Audit Portal</h1>
				<div className="grid grid-cols-4 gap-8 max-w-7xl w-full">
					{categoriesWithStats.map(cat => {
						const config = CATEGORY_CONFIG[cat.id] || CATEGORY_CONFIG.default;
						return (
							<button key={cat.id} onClick={() => setSelectedCategory(cat.id)} className="bg-white/5 hover:bg-white/10 border border-amber-900/50 hover:border-amber-500/50 rounded-[2rem] p-8 transition-all relative overflow-hidden group flex flex-col justify-between h-[320px]">
								<div className="relative z-10 w-full">
									<div className="flex justify-between items-start mb-6">
										<div className="p-4 bg-amber-500/10 rounded-2xl text-amber-500 group-hover:scale-110 transition-transform"><cat.icon size={32} /></div>
										<div className="text-right">
											<div className="text-4xl font-black text-white mb-1">{cat.total}</div>
											<div className="text-[10px] uppercase font-bold text-amber-500/50">Total Cases</div>
										</div>
									</div>
									<h2 className="text-2xl font-bold text-amber-50 text-left mb-2">{cat.title}</h2>
									<div className="text-xs text-amber-500/40 font-mono text-left mb-6">Last Active: {new Date().toLocaleTimeString()}</div>
								</div>

								{/* Mini Stats Bar */}
								<div className="flex gap-2 h-2 rounded-full overflow-hidden bg-black/20 relative z-10">
									{cat.total > 0 && (
										<>
											<div style={{ width: `${(cat.approved / cat.total) * 100}%`, backgroundColor: config.positive }} />
											<div style={{ width: `${(cat.declined / cat.total) * 100}%`, backgroundColor: config.negative }} />
										</>
									)}
								</div>
								<div className="flex justify-between text-[10px] font-bold uppercase mt-2 text-gray-500 relative z-10">
									<span style={{ color: config.positive }}>{cat.approved} {config.posLabel}</span>
									<span style={{ color: config.negative }}>{cat.declined} {config.negLabel}</span>
								</div>
							</button>
						);
					})}
				</div>
			</div>
		);
	}

	// --- DASHBOARD VIEW ---
	const currentCategory = categoriesWithStats.find(c => c.id === selectedCategory)!;
	const config = CATEGORY_CONFIG[currentCategory.id] || CATEGORY_CONFIG.default;

	// Aggregate Chart Data
	const chartData = [
		{ value: currentCategory.approved, color: config.positive, label: config.posLabel },
		{ value: currentCategory.declined, color: config.negative, label: config.negLabel },
		{ value: currentCategory.pending, color: '#f59e0b', label: 'Pending' }, // Amber-500 for pending
	];

	return (
		<div className="h-screen bg-[#1a100e] text-amber-50 flex flex-col overflow-hidden relative">
			{/* BACKGROUND */}
			<div className="absolute inset-0 bg-cover bg-center opacity-30 pointer-events-none" style={{ backgroundImage: 'url(/app_bg.png)' }} />
			<div className="absolute inset-0 bg-gradient-to-b from-[#1a100e]/80 to-[#1a100e]/90 pointer-events-none" />
			{/* TOP HEADER */}
			<div className="h-24 border-b border-amber-900/30 bg-[#291d1a]/80 backdrop-blur-md px-8 flex items-center justify-between z-50 transition-all">
				<div className="flex items-center gap-6">
					<button onClick={() => setSelectedCategory(null)} className="p-3 hover:bg-amber-900/40 rounded-full text-amber-500"><ArrowLeft size={24} /></button>
					<div>
						<h1 className="font-black text-2xl text-white tracking-tight">{currentCategory.title}</h1>
						<div className="text-xs text-amber-500/70 uppercase tracking-wider font-bold">Audit Console</div>
					</div>
				</div>

				{/* Filter & Search Bar */}
				<div className="flex items-center gap-4">
					{/* CSV Upload Button */}
					<button
						onClick={() => fileInputRef.current?.click()}
						disabled={isUploading}
						className="px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-500 font-bold rounded-xl transition-all flex items-center gap-2 disabled:opacity-50"
						title="Upload CSV file to batch process applications"
					>
						{isUploading ? <Loader2 size={18} className="animate-spin" /> : <Upload size={18} />}
						{isUploading ? 'Processing...' : 'Upload CSV'}
					</button>
					<input
						type="file"
						ref={fileInputRef}
						hidden
						accept=".csv"
						onChange={handleCsvUpload}
					/>

					{/* Manage Policies Button */}
					<button
						onClick={() => setShowPolicyManager(true)}
						className="px-4 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-500 font-bold rounded-xl transition-all flex items-center gap-2"
					>
						<Settings size={18} />
						Manage Policies
					</button>

					<div className="flex bg-[#1a100e] p-1 rounded-lg border border-amber-900/30">
						{['Pending', 'All', 'Approved', 'Denied'].map((f) => {
							const isActive = filter === f;
							// Dynamic color for active filter
							let activeClass = 'bg-amber-900/60 text-white';
							if (isActive) {
								if (f === 'Approved') activeClass = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50';
								else if (f === 'Denied') activeClass = 'bg-red-500/20 text-red-400 border border-red-500/50';
								else if (f === 'Pending') activeClass = 'bg-amber-500/20 text-amber-400 border border-amber-500/50';
								else activeClass = 'bg-amber-700 text-white';
							}
							return (
								<button
									key={f}
									onClick={() => updateState({ filter: f as FilterType })}
									className={`px-4 py-2 text-xs font-bold rounded-md transition-all ${isActive ? activeClass : 'text-amber-500/60 hover:text-amber-300'}`}
								>
									{f}
								</button>
							);
						})}
					</div>
					<div className="relative">
						<Search className="absolute left-3 top-1/2 -translate-y-1/2 text-amber-500/50" size={16} />
						<input
							value={searchQuery}
							onChange={e => updateState({ searchQuery: e.target.value })}
							placeholder="Search ID..."
							className="bg-[#1a100e] border border-amber-900/30 rounded-xl pl-10 pr-4 py-3 text-sm outline-none focus:border-amber-500 text-amber-100 w-64 transition-all focus:w-80 placeholder-amber-900"
						/>
					</div>
				</div>
			</div>

			<div className="flex flex-1 overflow-hidden">
				{/* LIST PANEL */}
				<div className="w-[400px] h-full overflow-y-auto border-r border-amber-900/30 bg-[#1a100e] flex-shrink-0 flex flex-col">
					<div className="p-4 border-b border-amber-900/30 flex-shrink-0">
						<div className="flex items-center gap-4 bg-[#291d1a] p-4 rounded-xl border border-amber-900/30 shadow-sm">
							<DonutChart data={chartData} size={80} thickness={6} />
							<div className="flex flex-col gap-1">
								<div className="flex items-center gap-2 text-xs font-bold text-white drop-shadow-md"><span className="w-2 h-2 rounded-full" style={{ backgroundColor: config.positive }} /> {currentCategory.approved} {config.posLabel}</div>
								<div className="flex items-center gap-2 text-xs font-bold text-gray-50 drop-shadow-md"><span className="w-2 h-2 rounded-full" style={{ backgroundColor: config.negative }} /> {currentCategory.declined} {config.negLabel}</div>
								{currentCategory.pending > 0 && <div className="flex items-center gap-2 text-xs font-bold text-amber-400 drop-shadow-md"><span className="w-2 h-2 rounded-full bg-amber-500" /> {currentCategory.pending} Pending</div>}
							</div>
						</div>
					</div>

					<div className="p-4 flex flex-col gap-2 overflow-y-auto">
						{filteredCases.length === 0 && (
							<div className="flex flex-col items-center justify-center py-10 opacity-30 text-center text-amber-500">
								<CheckCircle2 size={40} className="mb-2" />
								<span className="text-xs uppercase font-bold">No cases found</span>
							</div>
						)}
						{filteredCases.map((c, index) => {
							const isPending = c.model_output.label === 'Pending';
							const isPositive = ['approved', 'hired', 'low risk', 'low_risk'].includes(c.model_output.label.toLowerCase());

							const statusColor = isPending ? '#f59e0b' : (isPositive ? config.positive : config.negative);
							const isActive = activeCase?.decision_id === c.decision_id;

							// Dynamic Stylings
							const bgColor = isActive ? `${statusColor}30` : `${statusColor}08`;
							const borderColor = isActive ? statusColor : `${statusColor}20`; // Much subtler border when inactive

							return (
								<button
									key={c.decision_id}
									onClick={() => updateState({ activeCase: c })}
									className={`w-full min-h-[160px] p-6 rounded-2xl border transition-all text-left relative overflow-hidden flex flex-col justify-between group`}
									style={{
										backgroundColor: bgColor,
										borderColor: borderColor,
										boxShadow: isActive ? `0 0 20px -5px ${statusColor}40` : 'none'
									}}
								>

									{/* Row 1: Roll Index & Case ID */}
									<div className="flex justify-between items-center opacity-70">
										<div className="flex items-center gap-1 text-[10px] font-mono text-amber-500/70 uppercase">
											<Hash size={10} /> Roll: {(index + 1).toString().padStart(3, '0')}
										</div>
										<div className="text-[10px] font-black uppercase text-amber-500/70 tracking-wider">
											ID: {c.decision_id.slice(0, 6)}
										</div>
									</div>

									{/* Row 2: Applicant ID (Big) */}
									<div className="flex items-center gap-4 my-2">
										<div className="p-3 rounded-full bg-black/20 text-white">
											{isPending ? <Clock size={24} className="animate-pulse text-amber-500" /> : <User size={24} />}
										</div>
										<div>
											<div className="text-[10px] font-bold text-amber-500/60 uppercase">Applicant</div>
											<div className="text-xl font-black text-white leading-none group-hover:text-amber-200 transition-colors">
												{c.applicant_name || c.input_features?.applicant_id || "Unknown"}
											</div>
										</div>
									</div>

									{/* Row 3: Status Badge */}
									<div className="flex items-center justify-between border-t border-black/10 pt-3">
										<div className="text-[10px] text-amber-500/60 font-medium">{c.timestamp || '2023-10-24'}</div>
										<span
											className="px-3 py-1.5 rounded-full text-[10px] font-black uppercase tracking-wider shadow-lg"
											style={{ backgroundColor: statusColor, color: '#000' }}
										>
											{c.model_output.label}
										</span>
									</div>

								</button>
							);
						})}
					</div>
				</div>

				{/* DETAIL PANEL */}
				<div className="flex-1 h-full bg-[#150d0b] relative overflow-y-auto">
					{activeCase ? (
						<div className="flex flex-col h-full p-8 md:p-12">
							{/* Detail Header */}
							<div className="flex justify-between items-center mb-6">
								<div>
									<h2 className="text-4xl font-black text-white mb-2">Decision #DETAILS</h2>
									<div className="flex gap-4 items-center">
										<span className="text-amber-500 font-mono">{activeCase.decision_id}</span>
										<span className="bg-amber-900/50 text-amber-200 text-[10px] uppercase font-bold px-2 py-1 rounded">{activeCase.domain}</span>
										{/* Override Badge */}
										{(activeCase as any).is_override && (
											<span className="bg-orange-500/20 border border-orange-500 text-orange-500 text-[10px] uppercase font-bold px-3 py-1 rounded-full animate-pulse">
												⚠ Override
											</span>
										)}
										<div className="flex gap-2">
											<button
												onClick={() => {
													const dataStr = "data:text/plain;charset=utf-8," + encodeURIComponent(
														`Application History\n` +
														`ID: ${activeCase.decision_id}\n` +
														`Applicant: ${activeCase.applicant_name || activeCase.input_features?.applicant_id || "Unknown"}\n` +
														`Date: ${new Date().toLocaleString()}\n` +
														`----------------------------------------\n\n` +
														JSON.stringify(activeCase, null, 2)
													);
													const downloadAnchorNode = document.createElement('a');
													downloadAnchorNode.setAttribute("href", dataStr);
													downloadAnchorNode.setAttribute("download", `application_${activeCase.decision_id}.txt`);
													document.body.appendChild(downloadAnchorNode);
													downloadAnchorNode.click();
													downloadAnchorNode.remove();
												}}
												className="px-3 py-2 hover:bg-amber-500/20 rounded-lg text-amber-500 transition-all flex items-center gap-2 text-sm font-bold border border-amber-500/30"
												title="Download Text Summary"
											>
												<Download size={16} /> TXT
											</button>
											<button
												onClick={() => {
													const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(activeCase, null, 2));
													const downloadAnchorNode = document.createElement('a');
													downloadAnchorNode.setAttribute("href", dataStr);
													downloadAnchorNode.setAttribute("download", `application_${activeCase.decision_id}.json`);
													document.body.appendChild(downloadAnchorNode);
													downloadAnchorNode.click();
													downloadAnchorNode.remove();
												}}
												className="px-3 py-2 hover:bg-amber-500/20 rounded-lg text-amber-500 transition-all flex items-center gap-2 text-sm font-bold border border-amber-500/30"
												title="Download JSON Data"
											>
												<Download size={16} /> JSON
											</button>
										</div>
									</div>
								</div>

								{/* Centered Large-ish Confidence Donut, shifted right */}
								<div className="flex items-center gap-6 bg-[#291d1a] p-4 rounded-[2rem] border border-amber-900/30 pr-10">
									<DonutChart
										size={100} thickness={10}
										centerLabel={`${Math.round((activeCase.model_output.confidence || 0) * 100)}%`}
										centerSubLabel="CONF"
										data={[
											{ value: (activeCase.model_output.confidence || 0), color: '#f59e0b' }, // Amber confidence
											{ value: 1 - (activeCase.model_output.confidence || 0), color: '#1a100e' }
										]}
									/>
									<div className="text-right">
										<div className="text-sm text-amber-500/50 font-bold uppercase mb-1">Model Confidence</div>
										<div className="text-2xl font-black text-white">{activeCase.model_output.label}</div>
									</div>
								</div>
							</div>

							{/* PENDING ACTIONS */}
							{activeCase.model_output.label === 'Pending' && (
								<div className="mb-6 bg-amber-500/10 border border-amber-500/50 p-6 rounded-2xl flex items-center justify-between animate-pulse-slow">
									<div>
										<h3 className="text-xl font-bold text-amber-400 mb-1">Needs Review</h3>
										<p className="text-amber-100/70 text-sm">This application is awaiting human decision.</p>
									</div>
									<div className="flex gap-4">
										<button onClick={() => handleAction('Denied')} className="px-6 py-3 bg-red-500/20 hover:bg-red-500 hover:text-white border border-red-500 text-red-500 rounded-xl font-black uppercase transition-all flex items-center gap-2"><X size={18} /> Deny</button>
										<button onClick={() => handleAction('Approved')} className="px-6 py-3 bg-emerald-500/20 hover:bg-emerald-500 hover:text-white border border-emerald-500 text-emerald-500 rounded-xl font-black uppercase transition-all flex items-center gap-2"><Check size={18} /> Approve</button>
									</div>
								</div>
							)}

							{/* AI EXPLANATION - PROMINENT TOP SECTION */}
							<div className="mb-8">
								<div className="flex items-center justify-between mb-4">
									<h3 className="text-2xl font-black uppercase tracking-wide text-amber-400 flex items-center gap-3">
										<AlertCircle size={28} /> AI Explanation
									</h3>
									<button
										onClick={() => setExplanationEditorState({
											isOpen: true,
											mode: 'edit',
											initialText: activeCase.explanation.fullReasoning || activeCase.explanation.summary
										})}
										className="p-2 hover:bg-amber-500/20 rounded-lg text-amber-500 transition-all flex items-center gap-2 text-sm font-bold"
									>
										<Edit size={16} /> Edit Explanation
									</button>
								</div>
								<div className="bg-gradient-to-br from-[#291d1a] to-[#1a100e] rounded-3xl p-8 border-2 border-amber-500/40 shadow-2xl">
									<p className="text-lg text-gray-200 leading-relaxed mb-8 font-medium">"{activeCase.explanation.fullReasoning || activeCase.explanation.summary}"</p>

									{/* Counterfactuals Display - More Prominent */}
									{(activeCase as any).ai_result?.counterfactuals && (activeCase as any).ai_result.counterfactuals.length > 0 && (
										<div className="pt-6 border-t-2 border-amber-900/40">
											<p className="text-base text-amber-300 uppercase font-black mb-4 flex items-center gap-2">
												💡 Recommended Steps to Improve
											</p>
											<div className="space-y-3">
												{(activeCase as any).ai_result.counterfactuals.slice(0, 5).map((cf: any, i: number) => (
													<div key={i} className="text-base text-amber-100 leading-relaxed bg-amber-500/10 p-4 rounded-xl border border-amber-500/20 hover:bg-amber-500/15 transition-colors">
														{typeof cf === 'string' ? cf : JSON.stringify(cf)}
													</div>
												))}
											</div>
										</div>
									)}

									{/* Fallback if no structured counterfactuals */}
									{!(activeCase as any).ai_result?.counterfactuals?.length && activeCase.counterfactual && activeCase.counterfactual !== 'N/A' && (
										<div className="pt-6 border-t-2 border-amber-900/40">
											<p className="text-base text-amber-300 uppercase font-black mb-3">Alternative Recommendation</p>
											<p className="text-base text-amber-100 leading-relaxed">{activeCase.counterfactual}</p>
										</div>
									)}
								</div>
							</div>

							{/* Main Content Grid - SECONDARY POSITION */}
							<div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-auto">

								{/* Features (Takes up 2 cols) */}
								<div className="lg:col-span-2 space-y-6">
									<h3 className="text-sm font-black uppercase tracking-widest text-amber-500/70 mb-4">
										Application Data
									</h3>

									{/* Key Metrics Section */}
									{(activeCase as any).ai_result?.key_metrics && (
										<div>
											<h4 className="text-xs font-black uppercase tracking-widest text-amber-500/60 mb-4 flex items-center gap-2">
												📊 Key Metrics
											</h4>
											<div className="grid grid-cols-3 gap-4">
												<div className="bg-[#1a100e] p-4 rounded-2xl border border-amber-900/30">
													<div className="text-[10px] uppercase font-bold text-amber-500/60 mb-1">Risk Score</div>
													<div className="text-2xl font-black text-amber-100">
														{(activeCase as any).ai_result?.key_metrics?.risk_score || 'N/A'}
													</div>
												</div>
												<div className="bg-[#1a100e] p-4 rounded-2xl border border-amber-900/30">
													<div className="text-[10px] uppercase font-bold text-amber-500/60 mb-1">Approval Probability</div>
													<div className="text-2xl font-black text-amber-100">
														{((activeCase as any).ai_result?.key_metrics?.approval_probability * 100).toFixed(0) || 'N/A'}%
													</div>
												</div>
												<div className="bg-[#1a100e] p-4 rounded-2xl border border-amber-900/30">
													<div className="text-[10px] uppercase font-bold text-amber-500/60 mb-1">Critical Factors</div>
													<div className="text-sm font-medium text-amber-100">
														{(activeCase as any).ai_result?.key_metrics?.critical_factors?.length || 0}
													</div>
												</div>
											</div>
											{(activeCase as any).ai_result?.key_metrics?.critical_factors?.length > 0 && (
												<div className="mt-3 bg-[#1a100e]/50 p-4 rounded-xl border border-amber-900/20">
													<div className="text-[10px] uppercase font-bold text-amber-500/60 mb-2">Critical Factors:</div>
													<div className="flex flex-wrap gap-2">
														{(activeCase as any).ai_result.key_metrics.critical_factors.map((factor: string, i: number) => (
															<span key={i} className="px-3 py-1 bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs rounded-full">
																{factor}
															</span>
														))}
													</div>
												</div>
											)}
										</div>
									)}

									{/* Application Features */}
									<div className="grid grid-cols-2 gap-4">
										{Object.entries(activeCase.input_features).slice(0, 8).map(([key, val]) => (
											<div key={key} className="bg-[#1a100e] p-5 rounded-2xl border border-amber-900/30 hover:border-amber-500/30 transition-colors">
												<div className="text-[10px] uppercase font-bold text-amber-500/60 mb-1">{key.replace(/_/g, ' ')}</div>
												<div className="text-base font-medium text-amber-100 truncate" title={String(val)}>{String(val)}</div>
											</div>
										))}
									</div>
								</div>

								{/* Summary Panel - Right sidebar */}
								<div className="lg:col-span-1 space-y-6">
									<h3 className="text-sm font-black uppercase tracking-widest text-amber-500/70 mb-4">
										Quick Summary
									</h3>
									<div className="bg-[#1a100e] p-5 rounded-2xl border border-amber-900/30">
										<div className="text-xs uppercase font-bold text-amber-500/60 mb-2">Status</div>
										<div className="text-xl font-black text-amber-100">{activeCase.model_output.label}</div>
									</div>
									<div className="bg-[#1a100e] p-5 rounded-2xl border border-amber-900/30">
										<div className="text-xs uppercase font-bold text-amber-500/60 mb-2">Confidence</div>
										<div className="text-xl font-black text-amber-100">
											{Math.round((activeCase.model_output.confidence || 0) * 100)}%
										</div>
									</div>
									{(activeCase as any).ai_result?.fairness && (
										<div className="bg-[#1a100e] p-5 rounded-2xl border border-amber-900/30">
											<div className="text-xs uppercase font-bold text-amber-500/60 mb-2">Fairness</div>
											<div className="text-sm font-medium text-amber-100 mb-1">
												{(activeCase as any).ai_result.fairness.assessment}
											</div>
											{(activeCase as any).ai_result.fairness.concerns && (
												<div className="text-xs text-amber-300/60 mt-2">
													{(activeCase as any).ai_result.fairness.concerns}
												</div>
											)}
										</div>
									)}
								</div>
							</div>

						</div>
					) : (
						<div className="h-full flex flex-col items-center justify-center opacity-10">
							<CheckCircle2 size={120} className="mb-8 text-amber-500" />
							<div className="text-4xl font-black tracking-tighter text-amber-500 uppercase">Select Case</div>
						</div>
					)}
				</div>
			</div>

			{/* Modals */}
			{showPolicyManager && (
				<PolicyManager onClose={() => setShowPolicyManager(false)} />
			)}

			{explanationEditorState.isOpen && activeCase && (
				<ExplanationEditor
					applicationId={activeCase.decision_id}
					currentExplanation={explanationEditorState.initialText}
					isOverride={explanationEditorState.mode === 'override' || (activeCase as any).is_override}
					onClose={() => setExplanationEditorState(prev => ({ ...prev, isOpen: false }))}
					onSubmit={explanationEditorState.mode === 'override' ? async (text) => {
						if (explanationEditorState.action && selectedCategory) {
							await api.updateApplicationStatus(
								activeCase.decision_id,
								selectedCategory,
								explanationEditorState.action,
								text
							);
						}
					} : undefined}
					onSave={async () => {
						const newData = await api.getApplications();
						setRealData(newData);
						if (selectedCategory) {
							const updatedCase = newData[selectedCategory].find(c => c.decision_id === activeCase.decision_id);
							if (updatedCase) updateState({ activeCase: updatedCase });
						}
					}}
				/>
			)}
		</div>
	);
}
