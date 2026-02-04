import React, { useState, useEffect } from 'react';
import { ArrowLeft, Loader2, Download, Clock, CheckCircle2, XCircle } from 'lucide-react';
import { CATEGORIES, FORM_FIELDS } from '../lib/constants';
import { ApplicationType, AiResultType } from '../lib/types';
import AiResult from './AiResult';
import { api } from '../lib/api';

interface CustomerPortalProps {
	onBack: () => void;
}

export default function CustomerPortal({ onBack }: CustomerPortalProps) {
	const [applicationType, setApplicationType] = useState<ApplicationType>(null);
	const [formData, setFormData] = useState<any>({});
	const [isSubmitting, setIsSubmitting] = useState(false);

	// Polling State
	const [submittedId, setSubmittedId] = useState<string | null>(null);
	const [pollStatus, setPollStatus] = useState<'idle' | 'waiting' | 'completed'>('idle');
	const [aiResult, setAiResult] = useState<AiResultType | null>(null);

	// Polling Effect
	useEffect(() => {
		let interval: NodeJS.Timeout;
		if (pollStatus === 'waiting' && submittedId && applicationType) {
			interval = setInterval(async () => {
				try {
					const status = await api.getApplicationStatus(submittedId, applicationType);
					if (status && status.model_output.label !== 'Pending') {
						// Job Done!
						setAiResult({
							decision: status.model_output.label,
							summary: status.explanation.summary,
							counterfactuals: status.ai_result?.counterfactuals
						});
						setPollStatus('completed');
					}
				} catch (e) { console.error("Polling Error", e); }
			}, 2000); // Check every 2 seconds
		}
		return () => clearInterval(interval);
	}, [pollStatus, submittedId, applicationType]);


	const handleFormSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setIsSubmitting(true);
		try {
			// Convert numeric fields based on FORM_FIELDS config
			const cleanedData = { ...formData };
			const fields = FORM_FIELDS[applicationType || 'loan'] || [];
			fields.forEach(field => {
				if (field.type === 'number' && cleanedData[field.name]) {
					cleanedData[field.name] = Number(cleanedData[field.name]);
				}
			});

			const response = await api.submitApplication(applicationType, cleanedData);
			setSubmittedId(response.id);
			setPollStatus('waiting');
			setIsSubmitting(false);
		} catch (e) {
			console.error("Submission error:", e);
			alert("Submission failed. Please try again.");
			setIsSubmitting(false);
		}
	};

	// --- SUCCESS / RESULT SCREEN ---
	if (aiResult) {
		return <AiResult result={aiResult} onReset={() => {
			setAiResult(null);
			setApplicationType(null);
			setFormData({});
			setSubmittedId(null);
			setPollStatus('idle');
		}} />;
	}

	// --- WAITING SCREEN (New Requirement) ---
	if (pollStatus === 'waiting') {
		return (
			<div className="min-h-screen bg-[#1a100e] flex flex-col items-center justify-center p-8 relative overflow-hidden">
				<div className="absolute inset-0 bg-gradient-to-b from-[#291d1a]/50 to-[#1a100e]" />
				<div className="relative z-10 text-center max-w-xl p-10 bg-amber-900/10 backdrop-blur-xl rounded-[3rem] border border-amber-500/20 shadow-2xl">
					<Loader2 size={80} className="text-amber-400 animate-spin mx-auto mb-8" />
					<h1 className="text-4xl font-black text-amber-50 mb-4">Application Submitted</h1>
					<p className="text-xl text-amber-200/80 font-medium mb-8 leading-relaxed">
						Thank you for applying. Your application <span className="text-amber-400 font-mono font-bold">#{submittedId?.slice(0, 8)}</span> is currently under review by our AI Auditing System.
					</p>
					<div className="bg-black/30 rounded-xl p-4 flex items-center justify-center gap-3 text-sm text-amber-400 font-bold uppercase tracking-widest">
						<Clock size={16} /> Live Status: Pending Review
					</div>
					<p className="text-xs text-amber-500/50 mt-6">Please do not close this window.</p>
				</div>
			</div>
		);
	}

	if (applicationType) {
		return (
			<div className="min-h-screen bg-[#1a100e] text-amber-100 p-8 relative overflow-hidden flex flex-col items-center">
				{/* BACKDROP FOR FORM */}
				<div className="absolute inset-0 bg-cover bg-center opacity-40" style={{ backgroundImage: 'url(/app_bg.png)' }} />
				<div className="absolute inset-0 bg-gradient-to-b from-[#1a100e]/80 via-[#1a100e]/50 to-[#1a100e]" />

				<div className="w-full max-w-2xl relative z-10">
					<button onClick={() => setApplicationType(null)} className="mb-8 flex items-center gap-2 text-amber-400 hover:text-amber-300 font-bold"><ArrowLeft size={20} /> Back</button>
					<div className="bg-white/5 backdrop-blur-2xl rounded-[2.5rem] p-10 border border-amber-500/20 shadow-2xl">
						<h1 className="text-4xl font-black text-white mb-2 capitalize">{applicationType} Application</h1>
						<p className="text-amber-400/70 mb-8">AI Assisted Submission Engine</p>
						<form onSubmit={handleFormSubmit} className="space-y-6">
							{FORM_FIELDS[applicationType].map(field => (
								<div key={field.name}>
									<label className="block text-sm font-bold text-amber-200/80 mb-2">{field.label}</label>
									{field.type === 'select' ? (
										<select required onChange={e => setFormData({ ...formData, [field.name]: e.target.value })} className="w-full bg-black/40 backdrop-blur-md border border-amber-500/20 rounded-xl px-4 py-3 text-white focus:border-amber-400 outline-none">
											<option value="">Select...</option>
											{field.options?.map(opt => <option key={opt} value={opt} className="bg-[#1a100e]">{opt}</option>)}
										</select>
									) : (
										<input required type={field.type} onChange={e => setFormData({ ...formData, [field.name]: e.target.value })} className="w-full bg-black/40 backdrop-blur-md border border-amber-500/20 rounded-xl px-4 py-3 text-white focus:border-amber-400 outline-none" />
									)}
								</div>
							))}
							<button disabled={isSubmitting} type="submit" className="w-full bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-500 hover:to-yellow-500 text-white font-black py-4 rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg">
								{isSubmitting ? <Loader2 className="animate-spin" /> : <Download size={20} />} Submit Application
							</button>
						</form>
					</div>
				</div>
			</div>
		);
	}

	// CUSTOMER PORTAL SELECTION
	return (
		<div className="min-h-screen bg-[#1a100e] flex flex-col items-center justify-center p-8 relative overflow-hidden">
			{/* BACKDROP FOR SELECTION */}
			<div className="absolute inset-0 bg-cover bg-center opacity-60" style={{ backgroundImage: 'url(/customer_selection_bg.png)' }} />
			<div className="absolute inset-0 bg-gradient-to-b from-[#1a100e]/40 via-transparent to-[#1a100e]" />

			<button onClick={onBack} className="absolute top-8 left-8 flex items-center gap-2 text-amber-400 hover:text-amber-300 z-20 font-bold"><ArrowLeft size={20} /> Back</button>
			<div className="relative z-10 text-center max-w-4xl">
				<h1 className="text-5xl font-black text-white mb-4">What are you applying for?</h1>
				<div className="grid grid-cols-2 gap-6 max-w-3xl mx-auto">
					{CATEGORIES.map(cat => (
						<button key={cat.id} onClick={() => setApplicationType(cat.id as ApplicationType)} className="bg-white/5 backdrop-blur-xl border border-white/10 hover:border-amber-500 hover:bg-amber-900/20 rounded-3xl p-8 transition-all group">
							<cat.icon size={48} className="mx-auto mb-4 text-amber-400 group-hover:scale-110 transition-transform" />
							<h2 className="text-2xl font-bold text-white">{cat.title}</h2>
						</button>
					))}
				</div>
			</div>
		</div>
	);
}
