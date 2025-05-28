import glob
import math
import numbers
import os
import sys
from datetime import datetime
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add the lead_recovery package to the path
sys.path.append("../../")
from lead_recovery.cache import SummaryCache, compute_conversation_digest

app = FastAPI(title="Lead Recovery API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3002",
        "http://localhost:3004",
        "http://localhost:3005",
    ],  # Support all common dev ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to the output_run directory
OUTPUT_RUN_PATH = "../../output_run"

# Initialize cache for completion tracking
cache = SummaryCache()


# Pydantic models for request bodies
class CompleteLeadRequest(BaseModel):
    completed_by: str
    notes: Optional[str] = None


class AddNoteRequest(BaseModel):
    note: str
    author: str


def get_latest_analysis_file(campaign_name: str) -> Optional[str]:
    """Get the latest analysis file for a campaign"""
    campaign_path = os.path.join(OUTPUT_RUN_PATH, campaign_name)
    if not os.path.exists(campaign_path):
        return None

    # Find all timestamped directories
    timestamp_dirs = [
        d
        for d in os.listdir(campaign_path)
        if os.path.isdir(os.path.join(campaign_path, d)) and d.startswith("2025-")
    ]

    if not timestamp_dirs:
        return None

    # Get the latest directory
    latest_dir = sorted(timestamp_dirs)[-1]

    # Look for analysis CSV files
    analysis_files = glob.glob(
        os.path.join(campaign_path, latest_dir, "*analysis*.csv")
    )

    if analysis_files:
        return analysis_files[0]

    return None


def get_conversation_digest_for_lead(phone: str, campaign_id: str) -> str:
    """Get conversation digest for a lead from the conversations data"""
    try:
        # Look for conversations.csv in the same directory as analysis
        analysis_file = get_latest_analysis_file(campaign_id)
        if not analysis_file:
            return "no_conversation_data"

        # Get the directory containing the analysis file
        analysis_dir = os.path.dirname(analysis_file)
        conversations_file = os.path.join(analysis_dir, "conversations.csv")

        if not os.path.exists(conversations_file):
            return "no_conversation_data"

        # Read conversations for this phone number
        conversations_df = pd.read_csv(conversations_file)

        # Filter by phone number (try different column names)
        phone_col = None
        for col in ["cleaned_phone_number", "cleaned_phone", "phone"]:
            if col in conversations_df.columns:
                phone_col = col
                break

        if not phone_col:
            return "no_conversation_data"

        lead_conversations = conversations_df[conversations_df[phone_col] == phone]

        if lead_conversations.empty:
            return "no_conversation_data"

        # Create conversation text for digest
        convo_text = "\n".join(
            f"{row.get('creation_time', '')[:19]} {row.get('msg_from', '')}: {row.get('message', '')}"
            for _, row in lead_conversations.iterrows()
        )

        return compute_conversation_digest(convo_text)

    except Exception as e:
        print(f"Error getting conversation digest: {e}")
        return "no_conversation_data"


def sanitize_for_json(value):
    """Recursively convert values to JSON-safe representations (no NaN / Inf)."""
    if isinstance(value, numbers.Real):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_for_json(v) for v in value]
    return value


def process_lead_data(df: pd.DataFrame, campaign_id: str) -> List[dict]:
    """Process DataFrame into lead objects with completion status"""
    leads = []

    # Clean the DataFrame to handle NaN values
    # Replace NaN with appropriate defaults for different data types
    df = df.copy()

    # Handle string columns
    string_columns = [
        "name",
        "last_name",
        "clean_email",
        "summary",
        "suggested_message_es",
        "primary_stall_reason_code",
        "next_action_code",
        "transfer_context_analysis",
        "cleaned_phone",
        "lead_created_at",
        "last_user_message_text",
        "last_kuna_message_text",
    ]
    for col in string_columns:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    # Handle boolean columns
    boolean_columns = [
        "NO_USER_MESSAGES_EXIST",
        "IS_WITHIN_REACTIVATION_WINDOW",
        "IS_RECOVERY_PHASE_ELIGIBLE",
        "handoff_invitation_detected",
        "handoff_response",
        "handoff_finalized",
        "human_transfer",
    ]
    for col in boolean_columns:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)

    # Handle numeric columns (only those that are truly numeric)
    numeric_columns = ["consecutive_recovery_templates_count"]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for _, row in df.iterrows():
        phone = str(row.get("cleaned_phone", ""))
        if not phone:
            continue  # Skip rows without phone numbers

        # Get completion status
        conversation_digest = get_conversation_digest_for_lead(phone, campaign_id)
        completion_status = cache.get_lead_completion_status(
            phone, campaign_id, conversation_digest
        )

        # Create full name
        first_name = str(row.get("name", "")).strip()
        last_name = str(row.get("last_name", "")).strip()
        full_name = (
            f"{first_name} {last_name}".strip()
            if first_name or last_name
            else "Unknown"
        )

        # Map the CSV columns to our lead format
        lead = {
            "id": phone,  # Use phone as ID for consistency
            "name": full_name,
            "email": str(row.get("clean_email", "")),
            "phone": phone,
            "action": str(row.get("next_action_code", "UNKNOWN")),
            "priority": determine_priority(row),
            "stallReason": str(row.get("primary_stall_reason_code", "Unknown")),
            "summary": str(row.get("summary", "")),
            "suggestedMessage": str(row.get("suggested_message_es", "")),
            "lastContact": format_last_contact(row),
            "createdAt": str(row.get("lead_created_at", "")),
            "status": "completed" if completion_status["is_completed"] else "pending",
            "avatar": (
                f"/avatars/{first_name.lower()}.jpg"
                if first_name
                else "/avatars/default.jpg"
            ),
            # Add completion tracking fields
            "completion_status": completion_status["status"],
            "is_completed": completion_status["is_completed"],
            "needs_reactivation": completion_status["needs_reactivation"],
            "completion_info": completion_status["completion_info"],
        }

        # Recursively sanitize for JSON
        lead = sanitize_for_json(lead)

        leads.append(lead)

    return leads


def determine_priority(row) -> str:
    """Determine lead priority based on action code and other factors"""
    action = row.get("next_action_code", "")

    if action in ["LLAMAR_LEAD", "CONTACTO_PRIORITARIO"]:
        return "high"
    elif action in ["MANEJAR_OBJECION", "INSISTIR", "ENVIAR_PLANTILLA_RECUPERACION"]:
        return "medium"
    elif action in ["CERRAR", "ESPERAR"]:
        return "low"
    else:
        return "medium"  # Default for any unknown actions


def format_last_contact(row) -> str:
    """Format last contact time"""
    # This would need to be adapted based on your actual data structure
    return "2 hours ago"  # Placeholder


@app.get("/")
async def root():
    return {"message": "Lead Recovery API", "version": "1.0.0"}


@app.get("/campaigns")
async def get_campaigns():
    """Get list of available campaigns"""
    if not os.path.exists(OUTPUT_RUN_PATH):
        return {"campaigns": []}

    campaigns = []
    for item in os.listdir(OUTPUT_RUN_PATH):
        item_path = os.path.join(OUTPUT_RUN_PATH, item)
        if os.path.isdir(item_path):
            # Check if it has analysis files
            latest_file = get_latest_analysis_file(item)
            if latest_file:
                campaigns.append(
                    {
                        "id": item,
                        "name": item.replace("_", " ").title(),
                        "lastUpdated": datetime.fromtimestamp(
                            os.path.getmtime(latest_file)
                        ).isoformat(),
                    }
                )

    return {"campaigns": campaigns}


@app.get("/leads/{campaign_id}")
async def get_leads(
    campaign_id: str,
    priority: Optional[str] = Query(
        None, description="Filter by priority: high, medium, low"
    ),
    status: Optional[str] = Query(
        None, description="Filter by status: pending, completed"
    ),
    search: Optional[str] = Query(None, description="Search in name, email, phone"),
    limit: int = Query(50, description="Number of leads to return"),
    offset: int = Query(0, description="Number of leads to skip"),
):
    """Get leads for a specific campaign"""

    # Get the latest analysis file
    analysis_file = get_latest_analysis_file(campaign_id)
    if not analysis_file:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis data found for campaign: {campaign_id}",
        )

    try:
        # Read the CSV file
        df = pd.read_csv(analysis_file)

        # Process into lead format
        leads = process_lead_data(df, campaign_id)

        # Apply filters
        filtered_leads = leads

        if priority:
            filtered_leads = [
                lead for lead in filtered_leads if lead["priority"] == priority
            ]

        if status:
            filtered_leads = [
                lead for lead in filtered_leads if lead["status"] == status
            ]

        if search:
            search_lower = search.lower()
            filtered_leads = [
                lead
                for lead in filtered_leads
                if search_lower in lead["name"].lower()
                or search_lower in lead["email"].lower()
                or search_lower in lead["phone"]
            ]

        # Apply pagination
        total = len(filtered_leads)
        paginated_leads = filtered_leads[offset : offset + limit]

        return {
            "leads": paginated_leads,
            "total": total,
            "offset": offset,
            "limit": limit,
            "campaign": campaign_id,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing leads data: {str(e)}"
        )


@app.get("/stats/{campaign_id}")
async def get_campaign_stats(campaign_id: str):
    """Get statistics for a specific campaign"""

    analysis_file = get_latest_analysis_file(campaign_id)
    if not analysis_file:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis data found for campaign: {campaign_id}",
        )

    try:
        df = pd.read_csv(analysis_file)
        leads = process_lead_data(df, campaign_id)

        # Calculate statistics
        total_leads = len(leads)
        high_priority = len([lead for lead in leads if lead["priority"] == "high"])
        medium_priority = len([lead for lead in leads if lead["priority"] == "medium"])
        low_priority = len([lead for lead in leads if lead["priority"] == "low"])

        # Action distribution
        action_counts = {}
        for lead in leads:
            action = lead["action"]
            action_counts[action] = action_counts.get(action, 0) + 1

        # Stall reason distribution
        stall_counts = {}
        for lead in leads:
            reason = lead["stallReason"]
            stall_counts[reason] = stall_counts.get(reason, 0) + 1

        return {
            "totalLeads": total_leads,
            "highPriority": high_priority,
            "mediumPriority": medium_priority,
            "lowPriority": low_priority,
            "actionDistribution": action_counts,
            "stallReasons": stall_counts,
            "completionRate": 0.26,  # This would be calculated from actual completion data
            "conversionRate": 0.245,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error calculating stats: {str(e)}"
        )


@app.post("/leads/{campaign_id}/{lead_id}/complete")
async def mark_lead_complete(
    campaign_id: str, lead_id: str, request: CompleteLeadRequest
):
    """Mark a lead as completed"""
    try:
        # Get conversation digest for this lead
        conversation_digest = get_conversation_digest_for_lead(lead_id, campaign_id)

        # Mark as complete in cache
        success = cache.mark_lead_complete(
            phone_number=lead_id,
            recipe_name=campaign_id,
            conversation_digest=conversation_digest,
            completed_by=request.completed_by,
            notes=request.notes,
        )

        if success:
            return {"message": "Lead marked as completed", "lead_id": lead_id}
        else:
            raise HTTPException(
                status_code=500, detail="Failed to mark lead as completed"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error marking lead complete: {str(e)}"
        )


@app.get("/test-endpoint")
async def test_endpoint():
    """Test endpoint to verify server is running latest code"""
    return {
        "message": "Server is running latest code",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/completion-stats/{campaign_id}")
async def get_completion_stats(campaign_id: str):
    """Get completion statistics for a campaign"""
    try:
        stats = cache.get_completion_stats(campaign_id)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting completion stats: {str(e)}"
        )


@app.get("/completed-leads/{campaign_id}")
async def get_completed_leads(campaign_id: str):
    """Get all completed leads for a campaign"""
    try:
        completed_leads = cache.get_completed_leads_for_recipe(campaign_id)
        return {"completed_leads": completed_leads}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting completed leads: {str(e)}"
        )


@app.post("/leads/{lead_id}/note")
async def add_lead_note(lead_id: str, request: AddNoteRequest):
    """Add a note to a lead (placeholder - could be extended to store in cache)"""
    return {
        "message": f"Note added to lead {lead_id}",
        "note": request.note,
        "author": request.author,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
