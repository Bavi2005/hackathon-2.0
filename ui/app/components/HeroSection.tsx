import React, { useState } from 'react';
import { Shield, ArrowRight } from 'lucide-react';
import { PortalMode } from '../lib/types';

interface HeroSectionProps {
	setPortalMode: (mode: PortalMode) => void;
}

export default function HeroSection({ setPortalMode }: HeroSectionProps) {
	return (
		<div className="relative min-h-screen flex items-center justify-center overflow-hidden bg-[#1a100e]">
			{/* BACKGROUND */}
			<div
				className="absolute inset-0 bg-cover bg-center transition-opacity duration-1000"
				style={{ backgroundImage: 'url(/hero_brown.png)', opacity: 0.8 }}
			/>
			<div className="absolute inset-0 bg-gradient-to-b from-[#1a100e]/70 via-[#291d1a]/50 to-[#1a100e]" />

			<div className="relative z-10 text-center px-6 max-w-5xl mx-auto">
				<div className="mb-4 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/10 border border-amber-500/30 backdrop-blur-md">
					<span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
					<span className="text-amber-200 text-xs font-bold tracking-[0.2em] uppercase">AI Decision Core v2.0</span>
				</div>

				<h1 className="text-7xl md:text-9xl font-black text-transparent bg-clip-text bg-gradient-to-b from-amber-100 via-amber-200 to-amber-600 mb-2 tracking-tighter drop-shadow-2xl">
					TRISHADES<br />Ai
				</h1>
				<p className="text-sm md:text-base text-amber-500/80 font-bold uppercase tracking-[0.3em] mb-8">
					POWERED BY 3 SHADES OF BROWN
				</p>

				<p className="text-xl md:text-2xl text-amber-100/80 max-w-2xl mx-auto mb-12 font-light leading-relaxed">
					Next-generation transparent auditing. <strong className="text-amber-300 font-bold">Explainable AI</strong> that bridges the gap between decision and trust.
				</p>

				<div className="flex flex-col md:flex-row gap-6 justify-center items-center">
					<button
						onClick={() => setPortalMode('customer')}
						className="group relative px-8 py-5 bg-gradient-to-r from-amber-600 to-yellow-600 rounded-2xl overflow-hidden shadow-[0_0_40px_-10px_rgba(217,119,6,0.6)] hover:shadow-[0_0_60px_-10px_rgba(217,119,6,0.8)] transition-all transform hover:-translate-y-1"
					>
						<div className="absolute inset-0 bg-white/20 group-hover:bg-white/30 transition-colors" />
						<div className="relative flex items-center gap-3 text-white font-black tracking-wide text-lg">
							<span>I AM A CUSTOMER</span>
							<ArrowRight className="group-hover:translate-x-1 transition-transform" />
						</div>
					</button>

					<button
						onClick={() => setPortalMode('employee')}
						className="group px-8 py-5 rounded-2xl border border-amber-500/30 bg-[#1a100e]/60 backdrop-blur-md hover:bg-amber-900/40 text-amber-100 font-bold tracking-wide transition-all flex items-center gap-3"
					>
						<Shield size={20} className="text-amber-500" />
						<span>EMPLOYEE AUDIT</span>
					</button>
				</div>
			</div>
		</div>
	);
}
