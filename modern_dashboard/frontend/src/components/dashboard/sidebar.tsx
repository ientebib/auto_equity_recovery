'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { 
  BarChart3, 
  Home, 
  Users, 
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const navigationItems = [
  { icon: Home, label: 'Dashboard', href: '/', count: null },
  { icon: Users, label: 'All Leads', href: '/leads', count: 1247 },
]

export function DashboardSidebar() {
  const pathname = usePathname()

  return (
    <aside className="fixed left-0 top-16 h-[calc(100vh-4rem)] w-64 bg-white border-r border-slate-200 overflow-y-auto">
      <div className="p-6 space-y-6">
        {/* Navigation */}
        <nav className="space-y-2">
          {navigationItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname === item.href
            
            return (
              <Link key={item.label} href={item.href}>
                <Button
                  variant={isActive ? "default" : "ghost"}
                  className={`w-full justify-start h-10 ${
                    isActive 
                      ? 'bg-blue-600 text-white hover:bg-blue-700' 
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  }`}
                >
                  <Icon className="mr-3 h-4 w-4" />
                  <span className="flex-1 text-left">{item.label}</span>
                  {item.count && (
                    <Badge 
                      variant={isActive ? "secondary" : "outline"} 
                      className={`ml-auto ${
                        isActive 
                          ? 'bg-blue-500 text-white border-blue-400' 
                          : 'text-slate-500'
                      }`}
                    >
                      {item.count}
                    </Badge>
                  )}
                </Button>
              </Link>
            )
          })}
        </nav>

        {/* Quick Stats */}
        <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-blue-900">Today's Progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-blue-700">Completed</span>
              <span className="font-semibold text-blue-900">23/89</span>
            </div>
            <div className="w-full bg-blue-200 rounded-full h-2">
              <div className="bg-blue-600 h-2 rounded-full" style={{ width: '26%' }}></div>
            </div>
            <div className="flex items-center justify-between text-xs text-blue-600">
              <span>26% complete</span>
              <span>66 remaining</span>
            </div>
          </CardContent>
        </Card>

        {/* Campaign Selector */}
        <div className="space-y-3">
          <label className="text-sm font-medium text-slate-700 flex items-center">
            Campaign
            <Badge variant="destructive" className="ml-2 text-xs">
              Not Functional
            </Badge>
          </label>
          <Select defaultValue="simulation_to_handoff" disabled>
            <SelectTrigger className="w-full bg-red-50/30 border-red-200">
              <SelectValue placeholder="Select campaign" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="simulation_to_handoff">Simulation to Handoff</SelectItem>
              <SelectItem value="marzo_cohorts">Marzo Cohorts</SelectItem>
              <SelectItem value="top_up_may">Top Up May</SelectItem>
              <SelectItem value="demo_leads">Demo Leads</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </aside>
  )
} 