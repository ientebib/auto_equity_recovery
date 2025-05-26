import streamlit as st
import pandas as pd
import json
import yaml
from pathlib import Path
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional
import re

# Import our clipboard utilities
try:
    from clipboard_utils import copy_to_clipboard_js, display_copyable_text, create_shareable_link
except ImportError:
    # Fallback if clipboard_utils is not available
    def copy_to_clipboard_js(text, button_text="Copy", success_text="Copied!"):
        if st.button(button_text):
            st.success(success_text)
    
    def display_copyable_text(text, label="Message"):
        st.markdown(f"**{label}:**")
        st.info(text)
        copy_to_clipboard_js(text)
    
    def create_shareable_link(lead_data):
        return f"Lead: {lead_data.get('name', 'N/A')}"

# Helper function to safely get string values from pandas data
def safe_str(value, default="N/A"):
    """Safely convert any value to string, handling NaN and None."""
    if pd.isna(value) or value is None:
        return default
    return str(value)

# Set page config
st.set_page_config(
    page_title="Lead Recovery Dashboard", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for compact table styling
st.markdown("""
<style>
    .compact-table {
        font-size: 14px;
    }
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    .stColumn {
        padding: 0.1rem 0.2rem;
    }
    .element-container {
        margin-bottom: 0.2rem;
    }
    .priority-high {
        background-color: #fee;
        border-left: 4px solid #dc3545;
    }
    .priority-medium {
        background-color: #fff8e1;
        border-left: 4px solid #fd7e14;
    }
    .priority-low {
        background-color: #f8f9fa;
        border-left: 4px solid #28a745;
    }
    .status-completed {
        opacity: 0.6;
        text-decoration: line-through;
    }
    .action-badge {
        padding: 2px 6px;
        border-radius: 10px;
        font-size: 10px;
        font-weight: bold;
        color: white;
        text-align: center;
        display: inline-block;
        min-width: 70px;
    }
    .badge-high { background-color: #dc3545; }
    .badge-medium { background-color: #fd7e14; }
    .badge-low { background-color: #28a745; }
    .lead-row {
        padding: 4px;
        margin: 1px 0;
        border-radius: 4px;
        border: 1px solid #e0e0e0;
    }
    .lead-row:hover {
        background-color: #f5f5f5;
        border-color: #007bff;
    }
    .expanded-details {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border: 1px solid #dee2e6;
    }
    .stButton > button {
        padding: 0.2rem 0.4rem;
        font-size: 12px;
        height: 2rem;
        margin: 0;
    }
    .quick-stats {
        display: flex;
        justify-content: space-around;
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .stat-item {
        text-align: center;
    }
    .stat-number {
        font-size: 2rem;
        font-weight: bold;
        color: #495057;
    }
    .stat-label {
        font-size: 0.9rem;
        color: #6c757d;
    }
    /* Reduce spacing between elements */
    .row-widget.stButton {
        margin-bottom: 0.1rem;
    }
    .stMarkdown {
        margin-bottom: 0.2rem;
    }
    /* Make text smaller and more compact */
    .stMarkdown p {
        font-size: 13px;
        line-height: 1.2;
        margin-bottom: 0.1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'completed_actions' not in st.session_state:
    st.session_state.completed_actions = set()
if 'lead_notes' not in st.session_state:
    st.session_state.lead_notes = {}
if 'selected_leads' not in st.session_state:
    st.session_state.selected_leads = set()
if 'expanded_leads' not in st.session_state:
    st.session_state.expanded_leads = set()
if 'dashboard_settings' not in st.session_state:
    st.session_state.dashboard_settings = {
        'items_per_page': 75,
        'auto_refresh': False,
        'show_completed': True,
        'view_mode': 'compact'
    }

# Helper functions
def load_latest_data() -> Optional[List]:
    """Load the latest analysis data from the output directory."""
    output_dir = Path(__file__).parent.parent / "output_run"
    
    if not output_dir.exists():
        return []
    
    latest_files = []
    for recipe_dir in output_dir.iterdir():
        if recipe_dir.is_dir():
            # Look for analysis CSV files
            csv_files = list(recipe_dir.glob("*_analysis_*.csv"))
            if csv_files:
                latest_file = max(csv_files, key=lambda x: x.stat().st_mtime)
                latest_files.append((recipe_dir.name, latest_file))
    
    return latest_files

def load_recipe_meta(recipe_name: str) -> Optional[Dict]:
    """Load recipe metadata from meta.yml file."""
    recipe_dir = Path(__file__).parent.parent / "recipes" / recipe_name
    meta_file = recipe_dir / "meta.yml"
    
    if meta_file.exists():
        try:
            with open(meta_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            st.warning(f"Could not load meta.yml for {recipe_name}: {e}")
    
    return None

def get_action_priority_from_meta(action_code: str, recipe_meta: Dict = None) -> str:
    """Get priority level for action codes based on simulation_to_handoff taxonomy."""
    # V1 Priority taxonomy for simulation_to_handoff
    high_priority = ['CONTACTO_PRIORITARIO', 'LLAMAR_LEAD']
    medium_priority = ['MANEJAR_OBJECION', 'INSISTIR', 'ENVIAR_PLANTILLA_RECUPERACION']
    low_priority = ['ESPERAR', 'CERRAR']
    
    if action_code in high_priority:
        return 'high'
    elif action_code in medium_priority:
        return 'medium'
    elif action_code in low_priority:
        return 'low'
    else:
        return 'medium'  # Default for unknown codes

def get_priority_badge_class(priority: str) -> str:
    """Get CSS class for priority badge."""
    return f"badge-{priority}"

def get_stall_reason_description(code: str) -> str:
    """Get human-readable description for stall reason codes."""
    descriptions = {
        "NUNCA_RESPONDIO": "Never responded",
        "FINANCIAMIENTO_ACTIVO": "Active financing",
        "VEHICULO_ANTIGUO_KM": "Old vehicle/high mileage",
        "NO_PROPIETARIO": "Not vehicle owner",
        "VIN_EXTRANJERO": "Foreign vehicle",
        "ZONA_NO_CUBIERTA": "Area not covered",
        "USUARIO_SIN_AUTO": "No vehicle",
        "RECHAZADO_POR_KUNA": "Rejected by Kuna",
        "PRODUCTO_INCORRECTO_COMPRADOR": "Wrong product",
        "OTRO_PROCESO_DE_NEGOCIO": "Other business process",
        "DESINTERES_EXPLICITO": "Explicit disinterest",
        "ADEUDO_VEHICULAR_MULTAS": "Vehicle debt/fines",
        "PROBLEMA_SEGUNDA_LLAVE": "Second key issue",
        "PROBLEMA_TERMINOS": "Terms issue",
        "ERROR_PROCESO_INTERNO": "Internal error",
        "PROCESO_EN_CURSO": "Process in progress",
        "GHOSTING": "Ghosting",
        "OTRO": "Other"
    }
    return descriptions.get(code, code)

def format_time_ago(time_str: str) -> str:
    """Format time string to human readable."""
    if pd.isna(time_str) or time_str == "":
        return "N/A"
    
    match = re.match(r'(\d+)h\s*(\d+)m', str(time_str))
    if match:
        hours, minutes = int(match.group(1)), int(match.group(2))
        if hours > 24:
            days = hours // 24
            remaining_hours = hours % 24
            return f"{days}d {remaining_hours}h"
        else:
            return f"{hours}h {minutes}m"
    
    return str(time_str)

def render_compact_lead_row(row: pd.Series, idx: int) -> None:
    """Render a single lead in compact table format."""
    lead_id = row['lead_id']
    is_completed = lead_id in st.session_state.completed_actions
    is_expanded = lead_id in st.session_state.expanded_leads
    
    action_code = safe_str(row['next_action_code'])
    priority = get_action_priority_from_meta(action_code)
    priority_class = f"priority-{priority}"
    
    # Single compact row - no expansion by default
    cols = st.columns([0.3, 2.2, 1.8, 1.5, 1.2, 0.6, 0.6, 0.4])
    
    with cols[0]:
        is_selected = st.checkbox(
            "Select", 
            key=f"select_{lead_id}", 
            value=lead_id in st.session_state.selected_leads,
            label_visibility="collapsed"
        )
        if is_selected and lead_id not in st.session_state.selected_leads:
            st.session_state.selected_leads.add(lead_id)
        elif not is_selected and lead_id in st.session_state.selected_leads:
            st.session_state.selected_leads.remove(lead_id)
    
    with cols[1]:
        name = f"{safe_str(row.get('name', ''))} {safe_str(row.get('last_name', ''))}".strip()
        if is_completed:
            st.markdown(f"~~**{name or 'Unknown Lead'}**~~")
        else:
            st.markdown(f"**{name or 'Unknown Lead'}**")
        email = safe_str(row.get('clean_email', 'N/A'))
        st.markdown(f"📧 {email[:30]}{'...' if len(email) > 30 else ''}")
    
    with cols[2]:
        badge_class = get_priority_badge_class(priority)
        st.markdown(f"""
        <span class="action-badge {badge_class}">{action_code}</span>
        """, unsafe_allow_html=True)
        st.markdown(f"📱 {safe_str(row.get('cleaned_phone', 'N/A'))}")
    
    with cols[3]:
        stall_code = safe_str(row['primary_stall_reason_code'])
        stall_desc = get_stall_reason_description(stall_code)
        st.markdown(f"**{stall_desc[:20]}{'...' if len(stall_desc) > 20 else ''}**")
    
    with cols[4]:
        last_msg_time = format_time_ago(safe_str(row.get('HOURS_MINUTES_SINCE_LAST_MESSAGE', 'N/A')))
        st.markdown(f"**{last_msg_time}**")
        created = safe_str(row.get('lead_created_at', 'N/A'))[:10]
        st.markdown(f"{created}")
    
    with cols[5]:
        if is_completed:
            st.markdown("✅")
        else:
            if st.button("✅", key=f"complete_{lead_id}", help="Mark as done"):
                st.session_state.completed_actions.add(lead_id)
                st.rerun()
    
    with cols[6]:
        # Copy suggested message button
        suggested_message = safe_str(row.get('suggested_message_es', ''))
        if suggested_message and suggested_message not in ['N/A', '']:
            if st.button("📋", key=f"copy_{lead_id}", help="Copy message"):
                copy_to_clipboard_js(suggested_message, "Copied!", "Message copied!")
        else:
            st.markdown("—")
    
    with cols[7]:
        # Expand/collapse button
        expand_icon = "🔽" if is_expanded else "▶️"
        if st.button(expand_icon, key=f"expand_{lead_id}", help="Show details"):
            if is_expanded:
                st.session_state.expanded_leads.remove(lead_id)
            else:
                st.session_state.expanded_leads.add(lead_id)
            st.rerun()
    
    # ONLY show expanded details if explicitly expanded
    if is_expanded:
        with st.container():
            st.markdown("---")
            
            # Summary
            summary = safe_str(row.get('summary', 'No summary available'))
            st.markdown(f"**AI Summary:** {summary}")
            
            # Suggested message with copy functionality
            if suggested_message and suggested_message not in ['N/A', '']:
                st.markdown("**Suggested Message:**")
                st.info(suggested_message)
                copy_to_clipboard_js(suggested_message, "📋 Copy Message", "Message copied to clipboard!")
            
            # Quick actions
            action_cols = st.columns(4)
            
            with action_cols[0]:
                if st.button("📞 Call", key=f"call_{lead_id}"):
                    st.info(f"Call: {safe_str(row.get('cleaned_phone', 'N/A'))}")
            
            with action_cols[1]:
                if st.button("📧 Email", key=f"email_{lead_id}"):
                    email = safe_str(row.get('clean_email', ''))
                    if email != 'N/A':
                        st.markdown(f"[Open Email](mailto:{email}?subject=Follow up - Kuna AutoEquity)")
            
            with action_cols[2]:
                if st.button("📋 Copy Details", key=f"details_{lead_id}"):
                    details = create_shareable_link(row.to_dict())
                    copy_to_clipboard_js(details, "Details copied!")
            
            with action_cols[3]:
                if st.button("📝 Add Note", key=f"note_{lead_id}"):
                    st.session_state[f"show_notes_{lead_id}"] = True
            
            # Notes section (if shown)
            if st.session_state.get(f"show_notes_{lead_id}", False):
                notes = st.text_area(
                    "Notes:",
                    value=st.session_state.lead_notes.get(lead_id, ""),
                    key=f"notes_input_{lead_id}",
                    height=80
                )
                if notes != st.session_state.lead_notes.get(lead_id, ""):
                    st.session_state.lead_notes[lead_id] = notes
            
            # Additional technical details in expandable section
            with st.expander("Technical Details", expanded=False):
                tech_cols = st.columns(2)
                
                with tech_cols[0]:
                    st.markdown("**Lead Info:**")
                    st.write(f"Lead ID: {lead_id}")
                    st.write(f"User ID: {safe_str(row.get('user_id', 'N/A'))}")
                    st.write(f"Transfer: {'Yes' if row.get('human_transfer') else 'No'}")
                    
                with tech_cols[1]:
                    st.markdown("**Timing:**")
                    st.write(f"Last User Msg: {format_time_ago(safe_str(row.get('HOURS_MINUTES_SINCE_LAST_USER_MESSAGE', 'N/A')))}")
                    st.write(f"No User Messages: {'Yes' if row.get('NO_USER_MESSAGES_EXIST') else 'No'}")
                    st.write(f"Recovery Eligible: {'Yes' if row.get('IS_RECOVERY_PHASE_ELIGIBLE') else 'No'}")
                
                # Last messages
                last_user_msg = safe_str(row.get('last_user_message_text', ''))
                if last_user_msg and last_user_msg != 'N/A':
                    st.markdown("**Last User Message:**")
                    st.text_area("", value=last_user_msg, height=60, key=f"user_msg_display_{lead_id}", disabled=True, label_visibility="collapsed")
                
                last_kuna_msg = safe_str(row.get('last_kuna_message_text', ''))
                if last_kuna_msg and last_kuna_msg != 'N/A':
                    st.markdown("**Last Kuna Message:**")
                    st.text_area("", value=last_kuna_msg, height=60, key=f"kuna_msg_display_{lead_id}", disabled=True, label_visibility="collapsed")
            
            st.markdown("---")

# Main dashboard
def main():
    st.title("📊 Lead Recovery Dashboard - Compact View")
    st.markdown("**AI-Powered Lead Management for Sales Teams**")
    
    # Load data
    latest_files = load_latest_data()
    
    if not latest_files:
        st.error("❌ No analysis data found. Please run a recipe analysis first.")
        st.info("💡 Use the Recipe Builder to create and run analysis recipes.")
        
        # Demo data option
        if st.button("🎭 Generate Demo Data"):
            st.info("Running demo data generator...")
            st.code("python webui/generate_demo_data.py")
        return
    
    # Sidebar controls
    with st.sidebar:
        st.title("🔧 Dashboard Controls")
        
        # Recipe selection
        recipe_names = [recipe for recipe, _ in latest_files]
        selected_recipe = st.selectbox(
            "📂 Select Campaign/Recipe",
            options=recipe_names,
            index=0
        )
        
        # Load selected data and recipe metadata
        selected_file = next(file for recipe, file in latest_files if recipe == selected_recipe)
        recipe_meta = load_recipe_meta(selected_recipe)
        
        try:
            df = pd.read_csv(selected_file)
            st.success(f"✅ Loaded {len(df)} leads")
            
            # Show file info
            file_size = selected_file.stat().st_size / 1024  # KB
            modified_time = datetime.fromtimestamp(selected_file.stat().st_mtime)
            st.info(f"📊 File: {file_size:.1f}KB\n🕒 Updated: {modified_time.strftime('%Y-%m-%d %H:%M')}")
            
        except Exception as e:
            st.error(f"❌ Error loading data: {e}")
            return
        
        st.markdown("---")
        
        # Recipe-driven filters
        st.markdown("### 🔍 Smart Filters")
        
        # Action filter based on recipe meta
        if recipe_meta and 'llm_config' in recipe_meta:
            expected_keys = recipe_meta['llm_config'].get('expected_llm_keys', {})
            action_config = expected_keys.get('next_action_code', {})
            enum_values = action_config.get('enum_values', [])
            
            if enum_values:
                st.markdown("**Next Action** (from recipe):")
                selected_actions = st.multiselect(
                    "Filter by action codes",
                    options=enum_values,
                    default=enum_values[:4] if len(enum_values) > 4 else enum_values,
                    label_visibility="collapsed"
                )
            else:
                # Fallback to data-driven
                unique_actions = df['next_action_code'].dropna().unique()
                selected_actions = st.multiselect(
                    "Next Action",
                    options=unique_actions,
                    default=unique_actions[:4] if len(unique_actions) > 4 else unique_actions
                )
        else:
            unique_actions = df['next_action_code'].dropna().unique()
            selected_actions = st.multiselect(
                "Next Action",
                options=unique_actions,
                default=unique_actions[:4] if len(unique_actions) > 4 else unique_actions
            )
        
        # Priority filter
        priority_filter = st.selectbox(
            "Priority Level",
            options=["All", "🔴 High Priority", "🟠 Medium Priority", "🟢 Low Priority"]
        )
        
        # Status filter
        status_filter = st.selectbox(
            "Task Status",
            options=["All", "Pending", "Completed", "High Priority Only"]
        )
        
        st.markdown("---")
        
        # Bulk actions
        st.markdown("### ⚡ Bulk Actions")
        
        selected_count = len(st.session_state.selected_leads)
        st.write(f"Selected: {selected_count} leads")
        
        if selected_count > 0:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Mark All Done"):
                    st.session_state.completed_actions.update(st.session_state.selected_leads)
                    st.session_state.selected_leads.clear()
                    st.rerun()
            
            with col2:
                if st.button("📧 Export"):
                    selected_df = df[df['lead_id'].isin(st.session_state.selected_leads)]
                    csv = selected_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download",
                        csv,
                        f"selected_leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        "text/csv"
                    )
        
        # Clear selections
        if st.button("🗑️ Clear Selections"):
            st.session_state.selected_leads.clear()
            st.rerun()
        
        st.markdown("---")
        
        # Settings
        st.markdown("### ⚙️ Settings")
        
        st.session_state.dashboard_settings['items_per_page'] = st.slider(
            "Items per page", 20, 150, 
            st.session_state.dashboard_settings.get('items_per_page', 75)
        )
    
    # Apply filters
    filtered_df = df.copy()
    
    if selected_actions:
        filtered_df = filtered_df[filtered_df['next_action_code'].isin(selected_actions)]
    
    if priority_filter != "All":
        if priority_filter == "🔴 High Priority":
            high_actions = ['CONTACTO_PRIORITARIO', 'LLAMAR_LEAD']
            filtered_df = filtered_df[filtered_df['next_action_code'].isin(high_actions)]
        elif priority_filter == "🟠 Medium Priority":
            medium_actions = ['MANEJAR_OBJECION', 'INSISTIR', 'ENVIAR_PLANTILLA_RECUPERACION']
            filtered_df = filtered_df[filtered_df['next_action_code'].isin(medium_actions)]
        elif priority_filter == "🟢 Low Priority":
            low_actions = ['ESPERAR', 'CERRAR']
            filtered_df = filtered_df[filtered_df['next_action_code'].isin(low_actions)]
    
    if status_filter == "Completed":
        filtered_df = filtered_df[filtered_df['lead_id'].isin(st.session_state.completed_actions)]
    elif status_filter == "Pending":
        filtered_df = filtered_df[~filtered_df['lead_id'].isin(st.session_state.completed_actions)]
    elif status_filter == "High Priority Only":
        high_actions = ['CONTACTO_PRIORITARIO', 'LLAMAR_LEAD']
        filtered_df = filtered_df[filtered_df['next_action_code'].isin(high_actions)]
    
    # Main dashboard content
    
    # Key metrics - more compact
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Total", len(df))
    
    with col2:
        high_priority_actions = ['CONTACTO_PRIORITARIO', 'LLAMAR_LEAD']
        priority_count = len(df[df['next_action_code'].isin(high_priority_actions)])
        st.metric("🔴 High", priority_count)
    
    with col3:
        completed_count = len([lead_id for lead_id in df['lead_id'] if lead_id in st.session_state.completed_actions])
        st.metric("✅ Done", completed_count)
    
    with col4:
        success_rate = (completed_count / len(df) * 100) if len(df) > 0 else 0
        st.metric("📈 Rate", f"{success_rate:.1f}%")
    
    # Search and controls - more compact
    search_cols = st.columns([4, 1.5, 1.5])
    
    with search_cols[0]:
        search_term = st.text_input("🔍 Search", placeholder="name, email, phone, summary", key="search_input", label_visibility="collapsed")
    
    with search_cols[1]:
        sort_by = st.selectbox("Sort", options=["lead_created_at", "HOURS_MINUTES_SINCE_LAST_MESSAGE", "name", "next_action_code"], label_visibility="collapsed")
    
    with search_cols[2]:
        sort_order = st.selectbox("Order", options=["Descending", "Ascending"], label_visibility="collapsed")
    
    # Apply search
    if search_term:
        search_cols_list = ['name', 'last_name', 'clean_email', 'cleaned_phone', 'summary']
        search_mask = False
        for col in search_cols_list:
            if col in filtered_df.columns:
                search_mask |= filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
        filtered_df = filtered_df[search_mask]
    
    # Apply sorting
    if sort_by in filtered_df.columns:
        ascending = sort_order == "Ascending"
        filtered_df = filtered_df.sort_values(sort_by, ascending=ascending)
    
    # Column headers - single line
    header_cols = st.columns([0.3, 2.2, 1.8, 1.5, 1.2, 0.6, 0.6, 0.4])
    headers = ["☑️", "Name & Email", "Action & Phone", "Stall Reason", "Timing", "✅", "📋", "▶️"]
    
    for i, header in enumerate(headers):
        with header_cols[i]:
            st.markdown(f"**{header}**")
    
    st.markdown("---")
    
    # Pagination - more compact
    items_per_page = st.session_state.dashboard_settings['items_per_page']
    total_items = len(filtered_df)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    if total_pages > 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            page = st.selectbox(
                f"Showing {total_items} leads",
                options=list(range(1, total_pages + 1)),
                format_func=lambda x: f"Page {x} of {total_pages}",
                label_visibility="collapsed"
            )
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_df = filtered_df.iloc[start_idx:end_idx]
    else:
        page_df = filtered_df
    
    # Lead rows
    if len(page_df) == 0:
        st.info("🔍 No leads match your filters.")
    else:
        for idx, (_, row) in enumerate(page_df.iterrows()):
            render_compact_lead_row(row, idx)

if __name__ == "__main__":
    main() 