import { Suspense } from 'react'
import { DashboardHeader } from '@/components/dashboard/header'
import { DashboardSidebar } from '@/components/dashboard/sidebar'
import { LeadsTable } from '@/components/leads/leads-table'

export default function AllLeadsPage() {
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
                All Leads
              </h1>
              <p className="text-slate-600">
                Manage and track all your assigned leads in one place
              </p>
            </div>
            
            {/* Leads Table */}
            <Suspense fallback={<div className="h-96 bg-white rounded-lg animate-pulse" />}>
              <LeadsTable />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  )
} 