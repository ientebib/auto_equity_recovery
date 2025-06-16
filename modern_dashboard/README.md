# 🚀 Lead Recovery Modern Dashboard

A beautiful, professional dashboard for managing AI-powered lead recovery campaigns. Built with modern web technologies for an exceptional user experience.

![Dashboard Preview](https://via.placeholder.com/800x400/3b82f6/ffffff?text=Modern+Lead+Dashboard)

## ✨ Features

### 🎨 **Beautiful Modern UI**
- **Clean Design**: Professional interface with modern design principles
- **Responsive Layout**: Works perfectly on desktop, tablet, and mobile
- **Smooth Animations**: Delightful micro-interactions and transitions
- **Dark/Light Mode**: Automatic theme switching (coming soon)

### 📊 **Comprehensive Analytics**
- **Real-time Stats**: Live metrics and KPIs
- **Interactive Charts**: Beautiful visualizations with Recharts
- **Performance Tracking**: Conversion rates, response rates, and more
- **Campaign Comparison**: Compare multiple campaigns side-by-side

### 🎯 **Advanced Lead Management**
- **Smart Filtering**: Filter by priority, status, action type, and more
- **Global Search**: Find leads instantly by name, email, or phone
- **Bulk Actions**: Manage multiple leads simultaneously
- **Priority System**: Visual priority indicators (High/Medium/Low)

### 🤖 **AI-Powered Insights**
- **Smart Recommendations**: AI-suggested next actions
- **Message Templates**: Copy AI-generated messages with one click
- **Stall Analysis**: Understand why leads aren't converting
- **Conversation Summaries**: Quick AI-generated lead summaries

### ⚡ **Productivity Features**
- **One-Click Actions**: Call, email, or message leads instantly
- **Progress Tracking**: Mark leads as completed and track progress
- **Notes System**: Add and manage lead notes
- **Export Options**: Download filtered data as CSV

## 🛠️ Technology Stack

### Frontend
- **Next.js 15** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first CSS framework
- **shadcn/ui** - Beautiful, accessible components
- **Recharts** - Interactive data visualizations
- **Lucide React** - Beautiful icons

### Backend
- **FastAPI** - Modern, fast Python API framework
- **Pandas** - Data processing and analysis
- **Uvicorn** - ASGI server for production

## 🚀 Quick Start

### Prerequisites
- **Node.js 18+** and npm
- **Python 3.8+** and pip
- Your existing lead recovery data in `output_run/` directory

### 1. Clone and Setup
```bash
# Navigate to your lead recovery project
cd lead_recovery_project

# The modern_dashboard directory should already exist
cd modern_dashboard
```

### 2. Install Dependencies

**Frontend:**
```bash
cd frontend
npm install
```

**Backend:**
```bash
cd ../backend
pip install -r requirements.txt
```

### 3. Start the Dashboard
```bash
# From the modern_dashboard directory
./start_dashboard.sh
```

Or start manually:
```bash
# Terminal 1 - Backend
cd backend
python main.py

# Terminal 2 - Frontend  
cd frontend
npm run dev
```

### 4. Access the Dashboard
- **Dashboard UI**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **API Endpoints**: http://localhost:8000

## 📱 Usage Guide

### Dashboard Overview
1. **Stats Cards**: View key metrics at the top
2. **Analytics Charts**: Explore data with interactive visualizations
3. **Lead Grid**: Browse and manage individual leads

### Managing Leads
1. **Search & Filter**: Use the search bar and filters to find specific leads
2. **View Details**: Click on any lead card to see full details
3. **Take Actions**: Use the action buttons to call, email, or message
4. **Mark Complete**: Track your progress by marking leads as done
5. **Add Notes**: Keep track of important information

### Bulk Operations
1. **Select Multiple**: Use checkboxes to select multiple leads
2. **Bulk Actions**: Apply actions to all selected leads
3. **Export Data**: Download your filtered results

## 🎯 Key Workflows

### Morning Routine
1. Open dashboard and review overnight metrics
2. Filter for "High Priority" leads
3. Work through the list systematically
4. Mark completed actions as done

### Lead Follow-up
1. Search for specific lead by name/email
2. Review AI summary and conversation history
3. Copy suggested message template
4. Send message via WhatsApp/SMS
5. Mark as completed and add notes

### End-of-Day Reporting
1. Filter by "Completed" status
2. Review daily progress metrics
3. Export completed leads for reporting
4. Plan tomorrow's priorities

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the backend directory:
```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Data Paths
OUTPUT_RUN_PATH=../../output_run

# CORS Settings
ALLOWED_ORIGINS=http://localhost:3000
```

### Customization
- **Colors**: Modify `tailwind.config.js` for brand colors
- **Components**: Customize UI components in `src/components/`
- **API**: Extend backend endpoints in `backend/main.py`

## 📊 API Endpoints

### Campaigns
- `GET /campaigns` - List all available campaigns
- `GET /stats/{campaign_id}` - Get campaign statistics

### Leads
- `GET /leads/{campaign_id}` - Get leads with filtering
- `POST /leads/{lead_id}/complete` - Mark lead as completed
- `POST /leads/{lead_id}/note` - Add note to lead

### Documentation
- `GET /docs` - Interactive API documentation
- `GET /redoc` - Alternative API documentation

## 🎨 Design System

### Colors
- **Primary**: Blue (#3b82f6) - Actions and highlights
- **Success**: Green (#10b981) - Completed items
- **Warning**: Orange (#f59e0b) - Medium priority
- **Danger**: Red (#ef4444) - High priority
- **Neutral**: Slate - Text and backgrounds

### Typography
- **Headings**: Inter font family, bold weights
- **Body**: Inter font family, regular weights
- **Code**: Mono font family

### Spacing
- **Consistent Scale**: 4px base unit (0.25rem)
- **Component Spacing**: 16px (1rem) standard
- **Section Spacing**: 24px (1.5rem) between sections

## 🚀 Deployment

### Development
```bash
./start_dashboard.sh
```

### Production
1. **Build Frontend**:
   ```bash
   cd frontend
   npm run build
   ```

2. **Start Production Servers**:
   ```bash
   # Backend
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8000

   # Frontend (with PM2 or similar)
   cd frontend
   npm start
   ```

3. **Reverse Proxy**: Configure nginx or similar for production

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

This project is part of the Lead Recovery system. See the main project license.

## 🆘 Support

### Common Issues
- **Port conflicts**: Change ports in configuration files
- **Data not loading**: Check `output_run/` directory structure
- **Styling issues**: Clear browser cache and restart

### Getting Help
1. Check the console for error messages
2. Verify all dependencies are installed
3. Ensure data files are in the correct format
4. Contact the development team

# Quick Start: Run Both Frontend and Backend

To start both the backend and frontend servers at once (each in a new Terminal tab, macOS only):

```bash
./start_modern_dashboard.sh
```

- This script will open one tab for the backend (Python) and one for the frontend (Next.js/React).
- Make sure you have run `chmod +x start_modern_dashboard.sh` once to make it executable.

---

**Built with ❤️ for sales teams who deserve beautiful tools** 