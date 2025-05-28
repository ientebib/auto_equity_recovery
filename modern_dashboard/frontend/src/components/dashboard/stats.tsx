'use client'

import { useState, useEffect } from 'react'
import { TrendingUp, Users, AlertTriangle, Clock, Zap, MessageSquare, Phone, CheckCircle, XCircle, Timer } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'

interface RealStats {
  totalLeads: number
  highPriority: number
  mediumPriority: number
  lowPriority: number
  actionDistribution: Record<string, number>
  stallReasons: Record<string, number>
  completionRate: number
  conversionRate: number
}

// Action code mappings for better display
const ACTION_LABELS: Record<string, string> = {
  'LLAMAR_LEAD': 'Call Lead',
  'CONTACTO_PRIORITARIO': 'Priority Contact',
  'MANEJAR_OBJECION': 'Handle Objection',
  'INSISTIR': 'Insist/Follow Up',
  'ENVIAR_PLANTILLA_RECUPERACION': 'Send Recovery Template',
  'CERRAR': 'Close Lead',
  'ESPERAR': 'Wait',
  '': 'Unknown Action'
}

// Stall reason mappings for better display  
const STALL_LABELS: Record<string, string> = {
  'NUNCA_RESPONDIO': 'Never Responded',
  'GHOSTING': 'Ghosting',
  'DESINTERES_EXPLICITO': 'Explicit Disinterest',
  'FINANCIAMIENTO_ACTIVO': 'Active Financing',
  'PROCESO_EN_CURSO': 'Process in Progress',
  'NO_PROPIETARIO': 'Not Owner',
  'PROBLEMA_TERMINOS': 'Terms Issue',
  'PROBLEMA_SEGUNDA_LLAVE': 'Second Key Issue',
  'ZONA_NO_CUBIERTA': 'Uncovered Zone',
  'OTRO_PROCESO_DE_NEGOCIO': 'Other Business Process',
  'ERROR_PROCESO_INTERNO': 'Internal Process Error',
  'RECHAZADO_POR_KUNA': 'Rejected by Kuna',
  'USUARIO_SIN_AUTO': 'User Without Car',
  'ADEUDO_VEHICULAR_MULTAS': 'Vehicle Debt/Fines',
  'PRODUCTO_INCORRECTO_COMPRADOR': 'Wrong Product/Buyer',
  'VIN_EXTRANJERO': 'Foreign VIN',
  'VEHICULO_ANTIGUO_KM': 'Old Vehicle/High KM',
  'OTRO': 'Other',
  '': 'Unknown Reason'
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function DashboardStats() {
  const [stats, setStats] = useState<RealStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await fetch(`${API_URL}/stats/simulation_to_handoff`)
        if (response.ok) {
          const data = await response.json()
          setStats(data)
        }
      } catch (error) {
        console.error('Failed to fetch stats:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
  }, [])

  if (loading) {
    return <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1,2,3,4].map(i => (
          <div key={i} className="h-32 bg-white rounded-lg animate-pulse" />
        ))}
      </div>
    </div>
  }

  if (!stats) {
    return <div className="text-center py-8 text-slate-500">Failed to load dashboard stats</div>
  }

  // Calculate top actions and stall reasons
  const topActions = Object.entries(stats.actionDistribution)
    .sort(([,a], [,b]) => b - a)
    .slice(0, 4)
    .filter(([action]) => action !== '')

  const topStallReasons = Object.entries(stats.stallReasons)
    .sort(([,a], [,b]) => b - a)
    .slice(0, 4)
    .filter(([reason]) => reason !== '')

  const mainStats = [
    {
      title: 'Total Leads',
      value: stats.totalLeads.toLocaleString(),
      change: 'Real Data',
      icon: Users,
      color: 'blue',
      description: 'From simulation_to_handoff analysis',
      functional: true
    },
    {
      title: 'High Priority',
      value: stats.highPriority.toLocaleString(),
      change: `${Math.round((stats.highPriority / stats.totalLeads) * 100)}%`,
      icon: AlertTriangle,
      color: 'red',
      description: 'Need immediate action (LLAMAR_LEAD, CONTACTO_PRIORITARIO)',
      functional: true
    },
    {
      title: 'Recovery Templates',
      value: stats.actionDistribution['ENVIAR_PLANTILLA_RECUPERACION']?.toLocaleString() || '0',
      change: `${Math.round(((stats.actionDistribution['ENVIAR_PLANTILLA_RECUPERACION'] || 0) / stats.totalLeads) * 100)}%`,
      icon: MessageSquare,
      color: 'green',
      description: 'Need recovery message templates',
      functional: true
    },
    {
      title: 'Completion Rate',
      value: `${Math.round(stats.completionRate * 100)}%`,
      change: 'Placeholder',
      icon: TrendingUp,
      color: 'purple',
      description: 'Lead completion tracking (placeholder)',
      functional: false
    }
  ]

  return (
    <div className="space-y-6">
      {/* Main Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {mainStats.map((stat) => {
          const Icon = stat.icon
          
          return (
            <Card key={stat.title} className={`relative overflow-hidden group hover:shadow-lg transition-all duration-300 ${!stat.functional ? 'border-red-200 bg-red-50/30' : ''}`}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-slate-600">
                  {stat.title}
                  {!stat.functional && (
                    <Badge variant="destructive" className="ml-2 text-xs">
                      Not Functional
                    </Badge>
                  )}
                </CardTitle>
                <div className={`p-2 rounded-lg bg-${stat.color}-100`}>
                  <Icon className={`h-4 w-4 text-${stat.color}-600`} />
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex items-baseline space-x-2">
                    <div className="text-2xl font-bold text-slate-900">
                      {stat.value}
                    </div>
                    <Badge 
                      variant={stat.functional ? "default" : "outline"}
                      className={`text-xs ${
                        stat.functional 
                          ? 'bg-green-100 text-green-700 hover:bg-green-100' 
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-100'
                      }`}
                    >
                      {stat.change}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500">
                    {stat.description}
                  </p>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Next Action Distribution */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-slate-900 flex items-center">
            <Phone className="w-5 h-5 mr-2 text-blue-600" />
            Next Action Distribution (Real Data)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {topActions.map(([actionCode, count]) => {
              const percentage = Math.round((count / stats.totalLeads) * 100)
              const actionLabel = ACTION_LABELS[actionCode] || actionCode
              
              return (
                <div key={actionCode} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">
                      {actionLabel}
                    </span>
                    <span className="text-xs text-slate-500">
                      {count.toLocaleString()}
                    </span>
                  </div>
                  
                  <Progress 
                    value={percentage} 
                    className="h-2"
                  />
                  
                  <div className="flex items-center justify-between">
                    <span className="text-lg font-bold text-slate-900">
                      {percentage}%
                    </span>
                    <span className="text-sm text-slate-500">
                      of total
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Primary Stall Reasons */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-slate-900 flex items-center">
            <XCircle className="w-5 h-5 mr-2 text-red-600" />
            Top Stall Reasons (Real Data)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {topStallReasons.map(([reasonCode, count]) => {
              const percentage = Math.round((count / stats.totalLeads) * 100)
              const reasonLabel = STALL_LABELS[reasonCode] || reasonCode
              
              return (
                <div key={reasonCode} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">
                      {reasonLabel}
                    </span>
                    <span className="text-xs text-slate-500">
                      {count.toLocaleString()}
                    </span>
                  </div>
                  
                  <Progress 
                    value={percentage} 
                    className="h-2"
                  />
                  
                  <div className="flex items-center justify-between">
                    <span className="text-lg font-bold text-slate-900">
                      {percentage}%
                    </span>
                    <span className="text-sm text-slate-500">
                      of total
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Priority Breakdown */}
      <Card className="bg-gradient-to-r from-slate-50 to-slate-100 border-slate-200">
        <CardHeader>
          <CardTitle className="text-lg font-semibold text-slate-900">
            Priority Distribution (Real Data)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-6">
            <div className="text-center">
              <div className="flex items-center justify-center w-12 h-12 mx-auto mb-2 bg-red-100 rounded-full">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">{stats.highPriority.toLocaleString()}</div>
              <div className="text-sm text-slate-600">High Priority</div>
              <div className="text-xs text-slate-500">{Math.round((stats.highPriority / stats.totalLeads) * 100)}% of total</div>
            </div>
            
            <div className="text-center">
              <div className="flex items-center justify-center w-12 h-12 mx-auto mb-2 bg-orange-100 rounded-full">
                <Clock className="w-6 h-6 text-orange-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">{stats.mediumPriority.toLocaleString()}</div>
              <div className="text-sm text-slate-600">Medium Priority</div>
              <div className="text-xs text-slate-500">{Math.round((stats.mediumPriority / stats.totalLeads) * 100)}% of total</div>
            </div>
            
            <div className="text-center">
              <div className="flex items-center justify-center w-12 h-12 mx-auto mb-2 bg-green-100 rounded-full">
                <Timer className="w-6 h-6 text-green-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">{stats.lowPriority.toLocaleString()}</div>
              <div className="text-sm text-slate-600">Low Priority</div>
              <div className="text-xs text-slate-500">{Math.round((stats.lowPriority / stats.totalLeads) * 100)}% of total</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
} 