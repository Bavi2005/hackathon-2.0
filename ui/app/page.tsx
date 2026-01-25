"use client";

import React, { useState } from 'react';
import dynamic from 'next/dynamic';
import { PortalMode } from './lib/types';
import HeroSection from './components/HeroSection';

// Dynamic imports to split code and improve initial load performance
const CustomerPortal = dynamic(() => import('./components/CustomerPortal'), {
  loading: () => <div className="min-h-screen bg-[#0f1225] flex items-center justify-center text-cyan-400 font-bold">Loading Portal...</div>
});

const EmployeeDashboard = dynamic(() => import('./components/EmployeeDashboard'), {
  loading: () => <div className="min-h-screen bg-[#0f1225] flex items-center justify-center text-cyan-400 font-bold">Loading Dashboard...</div>
});

export default function XAIDashboard() {
  const [portalMode, setPortalMode] = useState<PortalMode>(null);

  if (portalMode === 'customer') {
    return <CustomerPortal onBack={() => setPortalMode(null)} />;
  }

  if (portalMode === 'employee') {
    return <EmployeeDashboard onBack={() => setPortalMode(null)} />;
  }

  return <HeroSection setPortalMode={setPortalMode} />;
}