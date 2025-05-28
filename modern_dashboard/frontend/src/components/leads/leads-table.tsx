'use client'

import { useState, useMemo, useEffect } from 'react'
import { 
  Phone, 
  Mail, 
  Copy, 
  CheckCircle, 
  Clock, 
  AlertTriangle,
  User,
  Calendar,
  MessageSquare,
  MoreHorizontal,
  Filter,
  Search,
  Download,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Eye,
  Edit,
  Trash2,
  RotateCcw
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'

// Lead interface with completion tracking
interface Lead {
  id: string
  name: string
  email: string
  phone: string
  action: string
  priority: 'high' | 'medium' | 'low'
  stallReason: string
  summary: string
  suggestedMessage: string
  lastContact: string
  createdAt: string
  status: 'pending' | 'completed'
  avatar: string
  assignedTo?: string
  campaign?: string
  leadScore?: number
  contactAttempts?: number
  responseRate?: number
  // Completion tracking fields
  completion_status?: 'ACTIVE' | 'COMPLETED' | 'REACTIVATED'
  is_completed?: boolean
  needs_reactivation?: boolean
  completion_info?: {
    completed_by?: string
    completed_ts?: string
    notes?: string
    previously_completed_by?: string
    previously_completed_ts?: string
    previous_notes?: string
    reactivation_reason?: string
  }
}

// API base URL (could be moved to env var)
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Remove mock data; we'll fetch from backend
const mockLeads: Lead[] = []  // placeholder, real data fetched on mount

// Random assignees for mock data
const MOCK_ASSIGNEES = [
  'Ana García',
  'Carlos Mendoza', 
  'Diana López',
  'Eduardo Silva',
  'Fernanda Torres'
]

// Enum values from meta.yml
const STALL_REASON_CODES = [
  "NUNCA_RESPONDIO", "FINANCIAMIENTO_ACTIVO", "VEHICULO_ANTIGUO_KM", "NO_PROPIETARIO", 
  "VIN_EXTRANJERO", "ZONA_NO_CUBIERTA", "USUARIO_SIN_AUTO", "RECHAZADO_POR_KUNA", 
  "PRODUCTO_INCORRECTO_COMPRADOR", "OTRO_PROCESO_DE_NEGOCIO", "DESINTERES_EXPLICITO", 
  "ADEUDO_VEHICULAR_MULTAS", "PROBLEMA_SEGUNDA_LLAVE", "PROBLEMA_TERMINOS", 
  "ERROR_PROCESO_INTERNO", "PROCESO_EN_CURSO", "GHOSTING", "OTRO"
]

const NEXT_ACTION_CODES = [
  "CERRAR", "ESPERAR", "LLAMAR_LEAD", "CONTACTO_PRIORITARIO", 
  "MANEJAR_OBJECION", "INSISTIR", "ENVIAR_PLANTILLA_RECUPERACION"
]

const getPriorityColor = (priority: string) => {
  switch (priority) {
    case 'high': return 'bg-red-100 text-red-800 border-red-200'
    case 'medium': return 'bg-orange-100 text-orange-800 border-orange-200'
    case 'low': return 'bg-green-100 text-green-800 border-green-200'
    default: return 'bg-gray-100 text-gray-800 border-gray-200'
  }
}

const getCompletionStatusColor = (status: string) => {
  switch (status) {
    case 'COMPLETED': return 'bg-green-100 text-green-800 border-green-200'
    case 'REACTIVATED': return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    case 'ACTIVE': 
    default: return 'bg-blue-100 text-blue-800 border-blue-200'
  }
}

const getActionColor = (action: string) => {
  switch (action) {
    case 'LLAMAR_LEAD':
    case 'CONTACTO_PRIORITARIO':
      return 'bg-red-500'
    case 'MANEJAR_OBJECION':
    case 'INSISTIR':
      return 'bg-orange-500'
    case 'CERRAR':
    case 'ESPERAR':
      return 'bg-green-500'
    default:
      return 'bg-gray-500'
  }
}

const getStallReasonColor = (reason: string) => {
  switch (reason) {
    case 'NUNCA_RESPONDIO':
    case 'GHOSTING':
      return 'bg-red-100 text-red-800 border-red-200'
    case 'DESINTERES_EXPLICITO':
    case 'CERRAR':
      return 'bg-gray-100 text-gray-800 border-gray-200'
    case 'PROCESO_EN_CURSO':
    case 'FINANCIAMIENTO_ACTIVO':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    default:
      return 'bg-blue-100 text-blue-800 border-blue-200'
  }
}

// Helper function to format stall reason for display
const formatStallReason = (reason: string) => {
  return reason.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())
}

// Helper function to format action code for display  
const formatActionCode = (action: string) => {
  return action.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())
}

type SortField = 'name' | 'priority' | 'lastContact' | 'leadScore' | 'contactAttempts' | 'responseRate'
type SortDirection = 'asc' | 'desc'

export function LeadsTable() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')
  const [filterPriority, setFilterPriority] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [filterStallReason, setFilterStallReason] = useState('all')
  const [filterNextAction, setFilterNextAction] = useState('all')
  const [filterAssignee, setFilterAssignee] = useState('all')
  const [sortField, setSortField] = useState<SortField>('priority')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [isCompleteDialogOpen, setIsCompleteDialogOpen] = useState(false)
  const [completionNotes, setCompletionNotes] = useState('')
  const [agentName, setAgentName] = useState('Current Agent') // In real app, get from auth

  // Fetch leads from backend on mount
  useEffect(() => {
    const fetchLeads = async () => {
      try {
        // For now default to simulation_to_handoff; later we can make campaign selectable
        const response = await fetch(`${API_URL}/leads/simulation_to_handoff?limit=1000`)
        if (response.ok) {
          const data = await response.json()
          // Add random assignees to leads that don't have them
          const leadsWithAssignees = data.leads.map((lead: Lead) => ({
            ...lead,
            assignedTo: lead.assignedTo || MOCK_ASSIGNEES[Math.floor(Math.random() * MOCK_ASSIGNEES.length)]
          }))
          setLeads(leadsWithAssignees)
        } else {
          console.error('Failed to fetch leads')
        }
      } catch (error) {
        console.error('Error fetching leads:', error)
      }
    }

    fetchLeads()
  }, [])

  // API functions for completion tracking
  const markLeadComplete = async (leadId: string, notes: string) => {
    try {
      const campaignId = selectedLead?.campaign || 'simulation_to_handoff'
      const response = await fetch(`${API_URL}/leads/${campaignId}/${leadId}/complete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          completed_by: agentName,
          notes: notes
        })
      })

      if (response.ok) {
        // Update local state
        setLeads(prevLeads => 
          prevLeads.map(lead => 
            lead.id === leadId 
              ? { 
                  ...lead, 
                  status: 'completed',
                  completion_status: 'COMPLETED',
                  is_completed: true,
                  completion_info: {
                    completed_by: agentName,
                    completed_ts: new Date().toISOString(),
                    notes: notes
                  }
                }
              : lead
          )
        )
        return true
      } else {
        console.error('Failed to mark lead complete')
        return false
      }
    } catch (error) {
      console.error('Error marking lead complete:', error)
      return false
    }
  }

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedLeads(new Set(filteredLeads.map((lead: Lead) => lead.id)))
    } else {
      setSelectedLeads(new Set())
    }
  }

  const handleSelectLead = (leadId: string, checked: boolean) => {
    const newSelected = new Set(selectedLeads)
    if (checked) {
      newSelected.add(leadId)
    } else {
      newSelected.delete(leadId)
    }
    setSelectedLeads(newSelected)
  }

  const handleBulkAction = (action: string) => {
    console.log(`Bulk action: ${action} on leads:`, Array.from(selectedLeads))
    // Implement bulk actions
  }

  const handleMarkComplete = (lead: Lead) => {
    setSelectedLead(lead)
    setCompletionNotes('')
    setIsCompleteDialogOpen(true)
  }

  const handleCompleteSubmit = async () => {
    if (selectedLead) {
      const success = await markLeadComplete(selectedLead.id, completionNotes)
      if (success) {
        setIsCompleteDialogOpen(false)
        setSelectedLead(null)
        setCompletionNotes('')
      }
    }
  }

  const handleCopyMessage = (message: string) => {
    navigator.clipboard.writeText(message)
    // Show toast notification in real app
  }

  const filteredLeads = useMemo(() => {
    let filtered = leads.filter(lead => {
      const matchesSearch = !searchTerm || 
        lead.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        lead.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
        lead.phone.includes(searchTerm)
      
      const matchesPriority = filterPriority === 'all' || lead.priority === filterPriority
      const matchesStallReason = filterStallReason === 'all' || lead.stallReason === filterStallReason
      const matchesNextAction = filterNextAction === 'all' || lead.action === filterNextAction
      const matchesAssignee = filterAssignee === 'all' || (lead.assignedTo && lead.assignedTo === filterAssignee)
      
      const isCompleted = lead.is_completed === true || lead.status === 'completed'
      const matchesStatus = filterStatus === 'all' || 
                          (filterStatus === 'completed' && isCompleted) ||
                          (filterStatus === 'pending' && !isCompleted)
      
      return matchesSearch && matchesPriority && matchesStallReason && matchesNextAction && matchesAssignee && matchesStatus
    })

    // Sort the filtered results
    filtered.sort((a, b) => {
      let aValue: any, bValue: any
      
      switch (sortField) {
        case 'name':
          aValue = a.name
          bValue = b.name
          break
        case 'priority':
          const priorityOrder = { high: 3, medium: 2, low: 1 }
          aValue = priorityOrder[a.priority]
          bValue = priorityOrder[b.priority]
          break
        case 'lastContact':
          aValue = a.lastContact
          bValue = b.lastContact
          break
        case 'leadScore':
          aValue = a.leadScore || 0
          bValue = b.leadScore || 0
          break
        case 'contactAttempts':
          aValue = a.contactAttempts || 0
          bValue = b.contactAttempts || 0
          break
        case 'responseRate':
          aValue = a.responseRate || 0
          bValue = b.responseRate || 0
          break
        default:
          return 0
      }

      if (sortDirection === 'asc') {
        return aValue > bValue ? 1 : -1
      } else {
        return aValue < bValue ? 1 : -1
      }
    })

    return filtered
  }, [leads, searchTerm, filterPriority, filterStatus, filterStallReason, filterNextAction, filterAssignee, sortField, sortDirection])

  const paginatedLeads = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize
    return filteredLeads.slice(startIndex, startIndex + pageSize)
  }, [filteredLeads, currentPage, pageSize])

  const totalPages = Math.ceil(filteredLeads.length / pageSize)

  const campaigns = [...new Set(leads.map(lead => lead.campaign).filter(Boolean))] as string[]
  const assignees = [...new Set(leads.map(lead => lead.assignedTo).filter(Boolean))] as string[]

  return (
    <div className="space-y-6">
      {/* Filters and Actions Bar */}
      <Card>
        <CardContent className="p-6">
          <div className="space-y-4">
            {/* Search and Quick Filters */}
            <div className="flex flex-col lg:flex-row gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 h-4 w-4" />
                  <Input
                    placeholder="Search leads by name, email, or phone..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>
              
              <div className="flex flex-wrap gap-2">
                <Select value={filterPriority} onValueChange={setFilterPriority}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Priorities</SelectItem>
                    <SelectItem value="high">High Priority</SelectItem>
                    <SelectItem value="medium">Medium Priority</SelectItem>
                    <SelectItem value="low">Low Priority</SelectItem>
                  </SelectContent>
                </Select>

                <Select value={filterStatus} onValueChange={setFilterStatus}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                  </SelectContent>
                </Select>

                <Select value={filterStallReason} onValueChange={setFilterStallReason}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Stall Reason" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Stall Reasons</SelectItem>
                    {STALL_REASON_CODES.map(reason => (
                      <SelectItem key={reason} value={reason}>
                        {formatStallReason(reason)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={filterNextAction} onValueChange={setFilterNextAction}>
                  <SelectTrigger className="w-48">
                    <SelectValue placeholder="Next Action" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Actions</SelectItem>
                    {NEXT_ACTION_CODES.map(action => (
                      <SelectItem key={action} value={action}>
                        {formatActionCode(action)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={filterAssignee} onValueChange={setFilterAssignee}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Assignee" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Agents</SelectItem>
                    {assignees.map(assignee => (
                      <SelectItem key={assignee} value={assignee}>
                        {assignee}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Button variant="outline" size="sm">
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              </div>
            </div>

            {/* Bulk Actions */}
            {selectedLeads.size > 0 && (
              <div className="flex items-center gap-2 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <span className="text-sm font-medium text-blue-900">
                  {selectedLeads.size} leads selected
                </span>
                <div className="flex gap-2 ml-4">
                  <Button size="sm" onClick={() => handleBulkAction('call')}>
                    <Phone className="h-4 w-4 mr-2" />
                    Bulk Call
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleBulkAction('email')}>
                    <Mail className="h-4 w-4 mr-2" />
                    Bulk Email
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleBulkAction('complete')}>
                    <CheckCircle className="h-4 w-4 mr-2" />
                    Mark Complete
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleBulkAction('export')}>
                    <Download className="h-4 w-4 mr-2" />
                    Export
                  </Button>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Results Summary */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <p className="text-sm text-slate-600">
            Showing {paginatedLeads.length} of {filteredLeads.length} leads
          </p>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="text-red-600 border-red-200">
              {filteredLeads.filter(l => l.priority === 'high').length} High Priority
            </Badge>
            <Badge variant="outline" className="text-green-600 border-green-200">
              {filteredLeads.filter(l => l.is_completed === true).length} Completed
            </Badge>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Select value={pageSize.toString()} onValueChange={(value) => setPageSize(Number(value))}>
            <SelectTrigger className="w-20">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10</SelectItem>
              <SelectItem value="25">25</SelectItem>
              <SelectItem value="50">50</SelectItem>
              <SelectItem value="100">100</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-sm text-slate-600">per page</span>
        </div>
      </div>

      {/* Leads Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50">
                  <TableHead className="w-12">
                    <Checkbox
                      checked={selectedLeads.size === paginatedLeads.length && paginatedLeads.length > 0}
                      onCheckedChange={handleSelectAll}
                    />
                  </TableHead>
                  <TableHead 
                    className="cursor-pointer hover:bg-slate-100"
                    onClick={() => handleSort('name')}
                  >
                    <div className="flex items-center">
                      Lead
                      {sortField === 'name' && (
                        sortDirection === 'asc' ? <ChevronUp className="ml-1 h-4 w-4" /> : <ChevronDown className="ml-1 h-4 w-4" />
                      )}
                    </div>
                  </TableHead>
                  <TableHead 
                    className="cursor-pointer hover:bg-slate-100"
                    onClick={() => handleSort('priority')}
                  >
                    <div className="flex items-center">
                      Priority
                      {sortField === 'priority' && (
                        sortDirection === 'asc' ? <ChevronUp className="ml-1 h-4 w-4" /> : <ChevronDown className="ml-1 h-4 w-4" />
                      )}
                    </div>
                  </TableHead>
                  <TableHead>Next Action</TableHead>
                  <TableHead>Primary Stall Reason</TableHead>
                  <TableHead>Contact Info</TableHead>
                  <TableHead 
                    className="cursor-pointer hover:bg-slate-100"
                    onClick={() => handleSort('leadScore')}
                  >
                    <div className="flex items-center">
                      Score
                      {sortField === 'leadScore' && (
                        sortDirection === 'asc' ? <ChevronUp className="ml-1 h-4 w-4" /> : <ChevronDown className="ml-1 h-4 w-4" />
                      )}
                    </div>
                  </TableHead>
                  <TableHead 
                    className="cursor-pointer hover:bg-slate-100"
                    onClick={() => handleSort('lastContact')}
                  >
                    <div className="flex items-center">
                      Last Contact
                      {sortField === 'lastContact' && (
                        sortDirection === 'asc' ? <ChevronUp className="ml-1 h-4 w-4" /> : <ChevronDown className="ml-1 h-4 w-4" />
                      )}
                    </div>
                  </TableHead>
                  <TableHead>Assignee</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedLeads.map((lead) => {
                  const isCompleted = lead.is_completed === true || lead.status === 'completed'
                  const isSelected = selectedLeads.has(lead.id)
                  
                  return (
                    <TableRow 
                      key={lead.id} 
                      className={`hover:bg-slate-50 ${isCompleted ? 'opacity-60 bg-slate-25' : ''} ${isSelected ? 'bg-blue-50' : ''}`}
                    >
                      <TableCell>
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={(checked) => handleSelectLead(lead.id, checked as boolean)}
                        />
                      </TableCell>
                      
                      <TableCell>
                        <div className="flex items-center space-x-3">
                          <Avatar className="h-8 w-8">
                            <AvatarFallback className="text-xs">
                              {lead.name.split(' ').map(n => n[0]).join('')}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <div className={`font-medium ${isCompleted ? 'line-through text-slate-500' : 'text-slate-900'}`}>
                              {lead.name}
                            </div>
                            <div className="text-sm text-slate-500">{lead.assignedTo || 'Unassigned'}</div>
                          </div>
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <Badge className={getPriorityColor(lead.priority)}>
                          {lead.priority.charAt(0).toUpperCase() + lead.priority.slice(1)}
                        </Badge>
                      </TableCell>
                      
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          <div className={`w-2 h-2 rounded-full ${getActionColor(lead.action)}`}></div>
                          <span className="text-sm font-medium">{formatActionCode(lead.action)}</span>
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <Badge className={getStallReasonColor(lead.stallReason)}>
                          {formatStallReason(lead.stallReason)}
                        </Badge>
                      </TableCell>
                      
                      <TableCell>
                        <div className="space-y-1">
                          <div className="text-sm">{lead.email}</div>
                          <div className="text-sm text-slate-500">{lead.phone}</div>
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          <div className="text-sm font-medium">{lead.leadScore}</div>
                          <div className="w-16 bg-slate-200 rounded-full h-1">
                            <div 
                              className="bg-blue-600 h-1 rounded-full" 
                              style={{ width: `${lead.leadScore}%` }}
                            ></div>
                          </div>
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <div className="text-sm text-slate-600">{lead.lastContact}</div>
                      </TableCell>
                      
                      <TableCell>
                        <div className="text-sm text-slate-600">
                          {lead.assignedTo || 'Unassigned'}
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          {!isCompleted && (
                            <>
                              <Button 
                                size="sm" 
                                variant="ghost"
                                onClick={() => handleMarkComplete(lead)}
                                className="h-8 w-8 p-0"
                              >
                                <CheckCircle className="h-4 w-4" />
                              </Button>
                              
                              {lead.suggestedMessage && (
                                <Button 
                                  size="sm" 
                                  variant="ghost"
                                  onClick={() => handleCopyMessage(lead.suggestedMessage)}
                                  className="h-8 w-8 p-0"
                                >
                                  <Copy className="h-4 w-4" />
                                </Button>
                              )}
                              
                              <Button size="sm" variant="ghost" className="h-8 w-8 p-0">
                                <Phone className="h-4 w-4" />
                              </Button>
                              
                              <Button size="sm" variant="ghost" className="h-8 w-8 p-0">
                                <Mail className="h-4 w-4" />
                              </Button>
                            </>
                          )}
                          
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => setSelectedLead(lead)}>
                                <Eye className="mr-2 h-4 w-4" />
                                View Details
                              </DropdownMenuItem>
                              <DropdownMenuItem>
                                <Edit className="mr-2 h-4 w-4" />
                                Edit Lead
                              </DropdownMenuItem>
                              <DropdownMenuItem>
                                <MessageSquare className="mr-2 h-4 w-4" />
                                Add Note
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem className="text-red-600">
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete Lead
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-600">
          Page {currentPage} of {totalPages}
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
          >
            Previous
          </Button>
          
          {/* Page numbers */}
          <div className="flex items-center space-x-1">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const pageNum = Math.max(1, Math.min(totalPages - 4, currentPage - 2)) + i
              return (
                <Button
                  key={pageNum}
                  variant={pageNum === currentPage ? "default" : "outline"}
                  size="sm"
                  onClick={() => setCurrentPage(pageNum)}
                  className="w-8 h-8 p-0"
                >
                  {pageNum}
                </Button>
              )
            })}
          </div>
          
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
          >
            Next
          </Button>
        </div>
      </div>

      {/* Lead Detail Modal */}
      <Dialog open={!!selectedLead} onOpenChange={() => setSelectedLead(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Lead Details</DialogTitle>
          </DialogHeader>
          {selectedLead && (
            <div className="space-y-6">
              <div className="flex items-center space-x-4">
                <Avatar className="h-16 w-16">
                  <AvatarFallback>
                    {selectedLead.name.split(' ').map((n: string) => n[0]).join('')}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <h2 className="text-xl font-semibold">{selectedLead.name}</h2>
                  <p className="text-slate-600">{selectedLead.email}</p>
                  <p className="text-slate-600">{selectedLead.phone}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <label className="text-sm font-medium text-slate-700">Priority</label>
                  <Badge className={getPriorityColor(selectedLead.priority)}>
                    {selectedLead.priority.charAt(0).toUpperCase() + selectedLead.priority.slice(1)}
                  </Badge>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">Lead Score</label>
                  <p className="text-sm font-bold">{selectedLead.leadScore}/100</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">Contact Attempts</label>
                  <p className="text-sm">{selectedLead.contactAttempts}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">Response Rate</label>
                  <p className="text-sm">{selectedLead.responseRate}%</p>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-slate-700">AI Summary</label>
                <p className="text-sm text-slate-600 mt-1">{selectedLead.summary}</p>
              </div>

              {selectedLead.suggestedMessage && (
                <div>
                  <label className="text-sm font-medium text-slate-700">Suggested Message</label>
                  <div className="mt-1 p-3 bg-slate-50 rounded-lg">
                    <p className="text-sm">{selectedLead.suggestedMessage}</p>
                    <Button 
                      size="sm" 
                      className="mt-2"
                      onClick={() => handleCopyMessage(selectedLead.suggestedMessage)}
                    >
                      <Copy className="h-4 w-4 mr-2" />
                      Copy Message
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Complete Lead Dialog */}
      <Dialog open={isCompleteDialogOpen} onOpenChange={() => setIsCompleteDialogOpen(false)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Complete Lead</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Label htmlFor="notes">Completion Notes</Label>
            <Textarea
              id="notes"
              value={completionNotes}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setCompletionNotes(e.target.value)}
              placeholder="Enter notes for completing the lead"
            />
            <Button onClick={handleCompleteSubmit}>Complete</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
} 