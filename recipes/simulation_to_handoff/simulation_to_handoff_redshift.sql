-- First extract just the leads we need to a result set (now potentially larger due to 90-day window)
WITH simulation_lead_ids AS (
    SELECT DISTINCT ld.id AS lead_id
    FROM financing_acceptation_api_global_refined.financing_leads_data ld
    JOIN financing_acceptation_api_global_refined.leads_audit la
        ON ld.id = la.lead_id
    WHERE
        ld.product = 'f079451e-04dd-4741-b7e0-ee6ddedc6b7d'
        -- Changed from -7 to -90 to fetch the last 90 days
        AND ld.create_date >= DATEADD(day, -14, CURRENT_DATE)
        AND la.field = 'SIMULATION' AND la.new_value IS NOT NULL
),
-- Get the full lead data with cleaned emails, for the leads that matter
leads_with_simulation AS (
    SELECT
        ld.id AS lead_id,
        ld.user_id,
        ld.create_date,
        ld.user_email,
        ld.product,
        LOWER(
            CASE
            WHEN POSITION('+' IN ld.user_email) > 0
            THEN SUBSTRING(ld.user_email, 1, POSITION('+' IN ld.user_email)-1)
                 || SUBSTRING(ld.user_email, POSITION('@' IN ld.user_email))
            ELSE ld.user_email
            END
        ) AS cleaned_email
    FROM financing_acceptation_api_global_refined.financing_leads_data ld
    JOIN simulation_lead_ids sim ON ld.id = sim.lead_id
),
-- Find which of our selected leads entered handoff (single pass through leads_audit)
entered_handoff_leads AS (
    SELECT DISTINCT lead_id
    FROM financing_acceptation_api_global_refined.leads_audit
    WHERE
        field = 'OFFER_STATUS'
        AND new_value = 'ENTERED'
        AND lead_id IN (SELECT lead_id FROM leads_with_simulation)
),
-- Get the lead emails for intent matching
lead_emails AS (
    SELECT DISTINCT cleaned_email
    FROM leads_with_simulation
),
-- Get only relevant intents (minimizing the join against the large intents table)
relevant_intents AS (
    SELECT
        i.id AS intent_id,
        i.email,
        i.name,
        i.last_name,
        i.phone_number,
        i.updated_at,
        LOWER(
            CASE
            WHEN POSITION('+' IN i.email) > 0
            THEN SUBSTRING(i.email FROM 1 FOR POSITION('+' IN i.email) - 1) || SUBSTRING(i.email FROM POSITION('@' IN i.email))
            ELSE i.email
            END
        ) AS cleaned_email
    FROM kuna_data_api_global_refined.intents i
    JOIN lead_emails le ON le.cleaned_email = LOWER(
        CASE
        WHEN POSITION('+' IN i.email) > 0
        THEN SUBSTRING(i.email FROM 1 FOR POSITION('+' IN i.email) - 1) || SUBSTRING(i.email FROM POSITION('@' IN i.email))
        ELSE i.email
        END
    )
),
latest_intent_per_email AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY cleaned_email ORDER BY updated_at DESC, intent_id DESC) AS rn
    FROM relevant_intents
)
-- Final selection: Leads with simulation, not in handoff, joined with latest intent info
SELECT
    lws.lead_id,
    lws.user_id,
    DATEADD(hour, -6, lws.create_date) AS lead_created_at, -- Adjust timezone
    li.name,
    li.last_name,
    RIGHT(li.phone_number, 10) AS cleaned_phone_number -- Extract last 10 digits of phone
FROM leads_with_simulation lws
JOIN latest_intent_per_email li ON lws.cleaned_email = li.cleaned_email AND li.rn = 1
LEFT JOIN entered_handoff_leads hel ON lws.lead_id = hel.lead_id
WHERE hel.lead_id IS NULL -- Keep only leads NOT found in entered_handoff_leads
ORDER BY lead_created_at DESC, lws.lead_id
limit 10;