import { Suspense } from 'react'
import { DashboardHeader } from '@/components/dashboard/header'
import { DashboardSidebar } from '@/components/dashboard/sidebar'
import { LeadGrid } from '@/components/leads/lead-grid'
import { DashboardStats } from '@/components/dashboard/stats'

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <DashboardHeader />
      
      <div className="flex">
        {/* Sidebar */}
        <DashboardSidebar />
        
        {/* Main Content */}
        <main className="flex-1 p-6 ml-64">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Page Title */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-slate-900 mb-2">
                Lead Recovery Dashboard
              </h1>
              <p className="text-slate-600">
                AI-powered lead management for your sales team
              </p>
            </div>
            
            {/* Stats Overview */}
            <Suspense fallback={<div className="h-32 bg-white rounded-lg animate-pulse" />}>
              <DashboardStats />
            </Suspense>
            
            {/* Leads Grid */}
            <Suspense fallback={<div className="h-96 bg-white rounded-lg animate-pulse" />}>
              <LeadGrid />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  )
}
