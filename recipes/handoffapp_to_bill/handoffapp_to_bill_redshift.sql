-- Re-using the structure of the original complex query
-- to identify cohorts, flag stages, and FILTER for those who reached simulation.

WITH lead_data AS (
    -- Select AutoEquity leads and clean email
    SELECT
        ld.id AS lead_id,
        ld.user_email,
        ld.user_id,
        ld.product,
        ld.profiling_status,
        LOWER(
            CASE
                WHEN POSITION('+' IN ld.user_email) > 0 THEN
                    SUBSTRING(ld.user_email FROM 1 FOR POSITION('+' IN ld.user_email) - 1) ||
                    SUBSTRING(ld.user_email FROM POSITION('@' IN ld.user_email))
                ELSE ld.user_email
            END
        ) AS cleaned_email,
        (ld.create_date - INTERVAL '6 HOUR') AS lead_created_at -- Assuming UTC-6 adjustment needed
    FROM financing_acceptation_api_global_refined.financing_leads_data ld
    WHERE ld.product = 'f079451e-04dd-4741-b7e0-ee6ddedc6b7d' -- AutoEquity Product ID
),
leads_audit_events AS (
    -- Extract key events from audit log
    SELECT
        ld.lead_id,
        ld.cleaned_email, -- Changed alias to cleaned_email
        (fala.event_date - INTERVAL '6 HOUR') AS event_date,
        CASE
            WHEN fala.field = 'SIMULATION' AND fala.new_value IS NOT NULL THEN 'Simulation'
            WHEN fala.field = 'OFFER_STATUS' AND fala.new_value = 'ENTERED' THEN 'HandOff_Completed' -- This specific event marks handoff completion
            -- Add other relevant audit events if needed
            ELSE NULL
        END AS event_type
    FROM lead_data ld
    LEFT JOIN financing_acceptation_api_global_refined.leads_audit fala
        ON ld.lead_id = fala.lead_id
    WHERE fala.event_date IS NOT NULL
      AND CASE -- Only include relevant event types
            WHEN fala.field = 'SIMULATION' AND fala.new_value IS NOT NULL THEN TRUE
            WHEN fala.field = 'OFFER_STATUS' AND fala.new_value = 'ENTERED' THEN TRUE
            ELSE FALSE
          END
),
profiling_events AS (
    -- Create pseudo-events for profiling status based on lead creation date
    SELECT lead_id, cleaned_email, lead_created_at AS event_date, 'Approved_Profiling' AS event_type
    FROM lead_data
    WHERE profiling_status IS NOT NULL
      AND RIGHT(profiling_status, 2) != '_R' -- Exclude rejected statuses explicitly
      AND profiling_status != 'REJECTED'
),
all_events AS (
    -- Combine audit and profiling events
    SELECT lead_id, cleaned_email, event_date, event_type FROM leads_audit_events WHERE event_type IS NOT NULL
    UNION ALL
    SELECT lead_id, cleaned_email, event_date, event_type FROM profiling_events
),
user_event_summary AS (
    -- Calculate latest dates for key events per user email
    SELECT
        ae.cleaned_email,
        -- Keep MAX dates as timestamps for filtering
        MAX(CASE WHEN ae.event_type = 'Approved_Profiling' THEN ae.event_date END) AS last_approved_profiling_date_ts,
        MAX(CASE WHEN ae.event_type = 'Simulation' THEN ae.event_date END) AS last_simulation_date_ts,
        MAX(CASE WHEN ae.event_type = 'HandOff_Completed' THEN ae.event_date END) AS last_handoff_completed_date_ts
    FROM all_events ae
    GROUP BY ae.cleaned_email
),
latest_intent_per_email AS (
    -- Find the most recent intent record for each cleaned email to get name/phone
    SELECT
        i.name,
        i.last_name,
        i.phone_number,
        LOWER(
            CASE
                WHEN POSITION('+' IN i.email) > 0 THEN
                    SUBSTRING(i.email FROM 1 FOR POSITION('+' IN i.email) - 1) ||
                    SUBSTRING(i.email FROM POSITION('@' IN i.email))
                ELSE i.email
            END
        ) AS cleaned_email,
        ROW_NUMBER() OVER (
            PARTITION BY cleaned_email
            ORDER BY i.updated_at DESC, i.id DESC
        ) AS rn
    FROM kuna_data_api_global_refined.intents i
),
bills_data AS (
    -- Identify customers with a relevant 'Auto Equity' bill in Netsuite
    SELECT DISTINCT -- Use DISTINCT as we only care IF a bill exists for the email
        LOWER(
            CASE
                WHEN POSITION('+' IN c.email) > 0 THEN
                    SUBSTRING(c.email FROM 1 FOR POSITION('+' IN c.email) - 1) ||
                    SUBSTRING(c.email FROM POSITION('@' IN c.email))
                ELSE c.email
            END
        ) AS cleaned_email,
        b.bill_id -- Keep bill_id to check for existence
    FROM netsuite_global_refined.bill b
    JOIN netsuite_global_refined.clients c ON b.bill_client_id = c.client_id
    WHERE b.bill_item_name = 'Auto Equity'
      AND b.bill_status IS NOT NULL
)
-- Final Selection and Filtering
SELECT
    li.name,
    li.last_name,
    ues.cleaned_email AS email,
    -- Clean the phone number: Remove non-digits, take last 10
    RIGHT(REGEXP_REPLACE(li.phone_number, '\\D',''), 10) AS cleaned_phone_number,
    cp.growth_customer_type AS customer_type,
    ues.last_approved_profiling_date_ts::DATE AS profiling_approval_date,
    CASE
        WHEN ues.last_approved_profiling_date_ts::DATE BETWEEN '2025-03-03' AND '2025-03-09' THEN 'Cohort 1'
        WHEN ues.last_approved_profiling_date_ts::DATE BETWEEN '2025-03-31' AND '2025-04-06' THEN 'Cohort 2'
        ELSE 'Other'
    END AS cohort,
    CASE
        WHEN b.bill_id IS NOT NULL THEN 'Yes'
        ELSE 'No'
    END AS converted_to_bill,
    -- Flags based on whether the last date for the event exists
    CASE WHEN ues.last_simulation_date_ts IS NOT NULL THEN 'Yes' ELSE 'No' END AS reached_simulation, -- This will always be 'Yes' now due to the WHERE clause
    CASE WHEN ues.last_handoff_completed_date_ts IS NOT NULL THEN 'Yes' ELSE 'No' END AS completed_handoff
FROM user_event_summary ues
JOIN cdp_global_serving.customer_profile cp ON ues.cleaned_email = cp.email -- Use INNER JOIN to implicitly filter for those in CDP
LEFT JOIN latest_intent_per_email li ON ues.cleaned_email = li.cleaned_email AND li.rn = 1
LEFT JOIN bills_data b ON ues.cleaned_email = b.cleaned_email
WHERE
    cp.growth_customer_type = 'CUSTOMER' -- Filter for CUSTOMER type
    AND ues.last_approved_profiling_date_ts IS NOT NULL -- Ensure they actually approved profiling
    AND (
        (ues.last_approved_profiling_date_ts::DATE BETWEEN '2025-03-03' AND '2025-03-09') OR
        (ues.last_approved_profiling_date_ts::DATE BETWEEN '2025-03-31' AND '2025-04-06')
    )
    AND ues.last_simulation_date_ts IS NOT NULL -- *** ADDED FILTER: Only include if simulation date exists ***
ORDER BY
    profiling_approval_date,
    ues.cleaned_email;