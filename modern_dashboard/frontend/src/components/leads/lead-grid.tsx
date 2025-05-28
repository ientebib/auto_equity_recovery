'use client'

import { useState } from 'react'
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
  Search
} from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'

// Mock lead data - in real app this would come from API
const mockLeads = [
  {
    id: '1',
    name: 'María García',
    email: 'maria.garcia@email.com',
    phone: '+52 55 1234 5678',
    action: 'LLAMAR_LEAD',
    priority: 'high',
    stallReason: 'Never Responded',
    summary: 'Cliente nunca respondió al contacto inicial tras oferta preaprobada.',
    suggestedMessage: 'Hola María, ¿pudiste revisar nuestra propuesta de préstamo? Estoy aquí para resolver cualquier duda.',
    lastContact: '2 hours ago',
    createdAt: '2024-01-15',
    status: 'pending',
    avatar: '/avatars/maria.jpg'
  },
  {
    id: '2',
    name: 'Carlos Rodríguez',
    email: 'carlos.rodriguez@email.com',
    phone: '+52 55 9876 5432',
    action: 'MANEJAR_OBJECION',
    priority: 'medium',
    stallReason: 'Terms Issues',
    summary: 'Cliente cuestiona tasas y términos del préstamo.',
    suggestedMessage: 'Hola Carlos, entiendo tus dudas sobre los términos. ¿Te gustaría revisar otras opciones?',
    lastContact: '1 day ago',
    createdAt: '2024-01-14',
    status: 'pending',
    avatar: '/avatars/carlos.jpg'
  },
  {
    id: '3',
    name: 'Ana López',
    email: 'ana.lopez@email.com',
    phone: '+52 55 5555 1234',
    action: 'CERRAR',
    priority: 'low',
    stallReason: 'Explicit Disinterest',
    summary: 'Cliente declinó explícitamente la oferta.',
    suggestedMessage: '',
    lastContact: '3 days ago',
    createdAt: '2024-01-12',
    status: 'completed',
    avatar: '/avatars/ana.jpg'
  },
  {
    id: '4',
    name: 'Luis Martínez',
    email: 'luis.martinez@email.com',
    phone: '+52 55 7777 8888',
    action: 'CONTACTO_PRIORITARIO',
    priority: 'high',
    stallReason: 'Ghosting',
    summary: 'Cliente dejó de responder hace 48h sin causa aparente.',
    suggestedMessage: 'Hola Luis, necesitamos resolver tu consulta urgente. ¿Cuándo podemos hablar?',
    lastContact: '6 hours ago',
    createdAt: '2024-01-16',
    status: 'pending',
    avatar: '/avatars/luis.jpg'
  }
]

const getPriorityColor = (priority: string) => {
  switch (priority) {
    case 'high': return 'bg-red-100 text-red-800 border-red-200'
    case 'medium': return 'bg-orange-100 text-orange-800 border-orange-200'
    case 'low': return 'bg-green-100 text-green-800 border-green-200'
    default: return 'bg-gray-100 text-gray-800 border-gray-200'
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

export function LeadGrid() {
  const [selectedLead, setSelectedLead] = useState<any>(null)
  const [completedLeads, setCompletedLeads] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')
  const [filterPriority, setFilterPriority] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')

  const handleMarkComplete = (leadId: string) => {
    setCompletedLeads(prev => new Set([...prev, leadId]))
  }

  const handleCopyMessage = (message: string) => {
    navigator.clipboard.writeText(message)
    // You could add a toast notification here
  }

  const filteredLeads = mockLeads.filter(lead => {
    const matchesSearch = lead.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         lead.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         lead.phone.includes(searchTerm)
    
    const matchesPriority = filterPriority === 'all' || lead.priority === filterPriority
    
    const isCompleted = completedLeads.has(lead.id) || lead.status === 'completed'
    const matchesStatus = filterStatus === 'all' || 
                         (filterStatus === 'completed' && isCompleted) ||
                         (filterStatus === 'pending' && !isCompleted)
    
    return matchesSearch && matchesPriority && matchesStatus
  })

  return (
    <div className="space-y-6">
      {/* Filters and Search */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row gap-4">
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
            
            <Select value={filterPriority} onValueChange={setFilterPriority}>
              <SelectTrigger className="w-full md:w-48">
                <SelectValue placeholder="Filter by priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priorities</SelectItem>
                <SelectItem value="high">High Priority</SelectItem>
                <SelectItem value="medium">Medium Priority</SelectItem>
                <SelectItem value="low">Low Priority</SelectItem>
              </SelectContent>
            </Select>

            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-full md:w-48">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Results Summary */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">
          Showing {filteredLeads.length} of {mockLeads.length} leads
        </p>
        <div className="flex items-center space-x-2">
          <Badge variant="outline" className="text-red-600 border-red-200">
            {filteredLeads.filter(l => l.priority === 'high').length} High Priority
          </Badge>
          <Badge variant="outline" className="text-green-600 border-green-200">
            {filteredLeads.filter(l => completedLeads.has(l.id) || l.status === 'completed').length} Completed
          </Badge>
        </div>
      </div>

      {/* Lead Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredLeads.map((lead) => {
          const isCompleted = completedLeads.has(lead.id) || lead.status === 'completed'
          
          return (
            <Card 
              key={lead.id} 
              className={`group hover:shadow-lg transition-all duration-300 ${
                isCompleted ? 'opacity-75 bg-slate-50' : 'hover:shadow-xl'
              } ${lead.priority === 'high' ? 'ring-2 ring-red-100' : ''}`}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <Avatar className="h-10 w-10">
                      <AvatarFallback>
                        {lead.name.split(' ').map(n => n[0]).join('')}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <h3 className={`font-semibold ${isCompleted ? 'line-through text-slate-500' : 'text-slate-900'}`}>
                        {lead.name}
                      </h3>
                      <p className="text-sm text-slate-500">{lead.email}</p>
                    </div>
                  </div>
                  
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => setSelectedLead(lead)}>
                        View Details
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleCopyMessage(lead.suggestedMessage)}>
                        Copy Message
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        Add Note
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                {/* Priority and Action */}
                <div className="flex items-center justify-between">
                  <Badge className={getPriorityColor(lead.priority)}>
                    {lead.priority.charAt(0).toUpperCase() + lead.priority.slice(1)} Priority
                  </Badge>
                  <div className="flex items-center space-x-2">
                    <div className={`w-2 h-2 rounded-full ${getActionColor(lead.action)}`}></div>
                    <span className="text-xs font-medium text-slate-600">{lead.action}</span>
                  </div>
                </div>

                {/* Summary */}
                <p className="text-sm text-slate-600 line-clamp-2">
                  {lead.summary}
                </p>

                {/* Stall Reason */}
                <div className="flex items-center space-x-2">
                  <AlertTriangle className="h-4 w-4 text-orange-500" />
                  <span className="text-sm text-slate-600">{lead.stallReason}</span>
                </div>

                {/* Contact Info */}
                <div className="space-y-2">
                  <div className="flex items-center space-x-2 text-sm text-slate-600">
                    <Phone className="h-4 w-4" />
                    <span>{lead.phone}</span>
                  </div>
                  <div className="flex items-center space-x-2 text-sm text-slate-600">
                    <Clock className="h-4 w-4" />
                    <span>Last contact: {lead.lastContact}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center space-x-2 pt-2">
                  {!isCompleted && (
                    <>
                      <Button 
                        size="sm" 
                        onClick={() => handleMarkComplete(lead.id)}
                        className="flex-1"
                      >
                        <CheckCircle className="h-4 w-4 mr-2" />
                        Complete
                      </Button>
                      
                      {lead.suggestedMessage && (
                        <Button 
                          size="sm" 
                          variant="outline"
                          onClick={() => handleCopyMessage(lead.suggestedMessage)}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      )}
                      
                      <Button size="sm" variant="outline">
                        <Phone className="h-4 w-4" />
                      </Button>
                      
                      <Button size="sm" variant="outline">
                        <Mail className="h-4 w-4" />
                      </Button>
                    </>
                  )}
                  
                  {isCompleted && (
                    <div className="flex items-center space-x-2 text-green-600 w-full justify-center">
                      <CheckCircle className="h-4 w-4" />
                      <span className="text-sm font-medium">Completed</span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Lead Detail Modal */}
      <Dialog open={!!selectedLead} onOpenChange={() => setSelectedLead(null)}>
        <DialogContent className="max-w-2xl">
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

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-slate-700">Priority</label>
                  <Badge className={getPriorityColor(selectedLead.priority)}>
                    {selectedLead.priority.charAt(0).toUpperCase() + selectedLead.priority.slice(1)}
                  </Badge>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">Next Action</label>
                  <p className="text-sm">{selectedLead.action}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">Stall Reason</label>
                  <p className="text-sm">{selectedLead.stallReason}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">Last Contact</label>
                  <p className="text-sm">{selectedLead.lastContact}</p>
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
    </div>
  )
} 