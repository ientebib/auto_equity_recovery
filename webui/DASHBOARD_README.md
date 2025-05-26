# 📊 Lead Recovery Dashboard

An interactive, production-ready dashboard for sales teams to manage AI-analyzed leads and recommended actions.

## 🎯 Overview

The Lead Recovery Dashboard transforms your AI-generated lead analysis data into an actionable workflow tool for sales teams. It provides:

- **Interactive Lead Management**: Browse, filter, and manage thousands of leads efficiently
- **AI-Powered Insights**: View AI summaries, stall reasons, and next action recommendations  
- **One-Click Actions**: Copy suggested messages, mark tasks complete, initiate calls/emails
- **Advanced Filtering**: Filter by action type, priority, time, completion status
- **Analytics Dashboard**: Visual insights into lead distribution and performance
- **Bulk Operations**: Manage multiple leads simultaneously
- **Real-time Tracking**: Track completion rates and team progress

## 🚀 Quick Start

### Option 1: Using the Launch Script (Recommended)
```bash
# From the project root directory
python run_dashboard.py
```

### Option 2: Manual Launch
```bash
# Install dependencies (if needed)
pip install streamlit pandas plotly

# Run dashboard
streamlit run webui/dashboard.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`

## 📋 Prerequisites

1. **Analysis Data**: You need CSV files generated from recipe analysis in the `output_run/` directory
2. **Python Dependencies**: 
   - `streamlit` >= 1.28.0
   - `pandas` >= 1.5.0  
   - `plotly` >= 5.0.0
   - `pyperclip` (optional, for clipboard functionality)

## 🎮 Features & Usage

### 📊 Main Dashboard

**Key Metrics Display**:
- Total leads in current dataset
- High priority actions requiring immediate attention
- Completed actions today (tracked per session)
- Overall completion rate

**Analytics Section**:
- Action distribution pie chart
- Top stall reasons bar chart
- Expandable for detailed insights

### 🔍 Filtering & Search

**Sidebar Filters**:
- **Campaign/Recipe**: Switch between different analysis datasets
- **Next Action**: Filter by recommended action types (LLAMAR_LEAD, CERRAR, etc.)
- **Priority Level**: High/Medium/Low priority actions
- **Task Status**: Pending, Completed, or Priority leads
- **Time-based**: Filter by when users last responded

**Search & Sort**:
- Global search across names, emails, phones, and summaries
- Sort by creation date, last message time, name, or action type
- Pagination for large datasets

### 📋 Lead Cards

Each lead is displayed in an interactive card showing:

**Basic Info**:
- Lead name, email, and phone
- Next recommended action (color-coded by priority)
- Stall reason with human-readable description
- Time since last message and lead creation date

**Actions**:
- ✅ **Mark Done**: Track completion status
- 📋 **Copy Message**: Copy AI-suggested message to clipboard
- 📞 **Call Lead**: Quick access to phone number
- 📧 **Email**: Open email client with pre-filled recipient
- 📋 **Copy Details**: Copy all lead information for sharing

**Expandable Details**:
- Full conversation history (last user and Kuna messages)
- Technical details (Lead ID, User ID, transfer status)
- Recovery eligibility and timing information
- Personal notes section for each lead

### ⚡ Bulk Actions

**Selection Tools**:
- Checkboxes to select multiple leads
- "Select All" functionality for filtered results
- Clear selections button

**Bulk Operations**:
- Mark multiple leads as completed
- Export selected leads to CSV
- Track progress across selected items

### 📥 Export & Data Management

**Export Options**:
- Export filtered data with completion status and notes
- Download CSV files with timestamp
- Include custom notes and completion tracking

**Data Persistence** (per session):
- Completion status tracking
- Personal notes for each lead
- Filter preferences
- Selection state

## 🎨 UI Features

### Color Coding
- **🔴 High Priority**: CONTACTO_PRIORITARIO, LLAMAR_LEAD (red)
- **🟠 Medium Priority**: MANEJAR_OBJECION, INSISTIR (orange/teal)
- **🟢 Low Priority**: CERRAR, ESPERAR, etc. (green/gray)

### Status Indicators
- **Green Cards**: Completed tasks
- **Red Cards**: High priority pending tasks
- **Yellow Cards**: Standard pending tasks

### Responsive Design
- Wide layout optimized for desktop use
- Collapsible sidebar for more screen space
- Pagination for performance with large datasets

## ⚙️ Settings & Configuration

**Dashboard Settings**:
- Items per page (5-50 leads)
- Auto-refresh toggle (for live environments)
- Show/hide completed items

**Session Persistence**:
- Filter preferences maintained
- Completion tracking per session
- Notes saved temporarily

## 📈 Analytics & Insights

The dashboard provides several analytical views:

1. **Action Distribution**: Pie chart showing breakdown of recommended actions
2. **Stall Reasons**: Bar chart of most common reasons leads stall
3. **Completion Tracking**: Real-time progress metrics
4. **Time-based Analysis**: Filter by response timeframes

## 🔧 Technical Details

### Data Sources
- Reads CSV files from `output_run/<recipe_name>/` directories
- Automatically finds latest analysis files
- Supports multiple recipe datasets

### Performance Optimizations
- Pagination for large datasets
- Efficient filtering and search
- Optimized pandas operations
- Session state management

### Browser Compatibility
- Chrome/Edge (recommended)
- Firefox 
- Safari
- Clipboard functionality requires HTTPS in production

## 🚨 Troubleshooting

### Common Issues

**"No analysis data found"**:
- Ensure you've run a recipe analysis first
- Check that CSV files exist in `output_run/` subdirectories
- Verify file naming convention: `*_analysis_*.csv`

**Copy functionality not working**:
- Modern browsers require HTTPS for clipboard API
- Use fallback text selection for HTTP/local development
- Check browser permissions for clipboard access

**Dashboard not loading**:
- Verify Streamlit installation: `pip install streamlit`
- Check Python path includes project directory
- Run from project root: `python run_dashboard.py`

**Performance issues with large datasets**:
- Reduce items per page in settings
- Use filters to narrow down results
- Consider data archiving for very large datasets

## 🔮 Future Enhancements

Potential improvements for production deployment:

- **Database Integration**: Connect to live data sources
- **User Authentication**: Multi-user support with role-based access
- **Real-time Updates**: Live data refresh and team collaboration
- **Mobile Responsive**: Touch-optimized interface for tablets
- **Integration APIs**: Connect with CRM systems and communication tools
- **Advanced Analytics**: Conversion tracking, performance metrics, team dashboards

## 📞 Support

For technical support or feature requests:
1. Check this README and troubleshooting section
2. Review the Recipe Builder documentation
3. Contact your technical team lead

---

**Pro Tips for Sales Teams** 💡:
- Start each day by filtering for "High Priority" actions
- Use bulk actions to mark completed calls/emails
- Add notes to leads for team coordination  
- Export daily progress reports for management
- Use analytics to identify common stall patterns 