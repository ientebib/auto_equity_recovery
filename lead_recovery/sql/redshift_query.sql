-- Redshift Query: Get Target AutoEquity Leads for Bot 1 (No Profiling Completed)
-- IMPORTANT: Phone number formatting must match between Redshift and BigQuery
-- The RIGHT(phone_number, 10) logic extracts the last 10 digits of phone numbers
-- This MUST be identical to the phone number processing in bigquery_query.sql

WITH latest_lead_per_email AS (
  -- Find the most recent lead record for each cleaned email address
  -- Filter for leads within the last 3 months AND the specific AutoEquity product
  SELECT
    ld.id, ld.create_date, ld.user_id, ld.user_email, ld.product,
    ld.profiling_status, ld.vehicle_id, ld.simulation_id, ld.handoff_status, ld.transaction_id,
    LOWER(
      CASE
        WHEN POSITION('+' IN ld.user_email) > 0 THEN SUBSTRING(ld.user_email FROM 1 FOR POSITION('+' IN ld.user_email) - 1) || SUBSTRING(ld.user_email FROM POSITION('@' IN ld.user_email) FOR LENGTH(ld.user_email))
        ELSE ld.user_email
      END
    ) AS cleaned_email,
    ROW_NUMBER() OVER (
      PARTITION BY LOWER(CASE WHEN POSITION('+' IN ld.user_email) > 0 THEN SUBSTRING(ld.user_email FROM 1 FOR POSITION('+' IN ld.user_email) - 1) || SUBSTRING(ld.user_email FROM POSITION('@' IN ld.user_email) FOR LENGTH(ld.user_email)) ELSE ld.user_email END)
      ORDER BY ld.create_date DESC, ld.id DESC
    ) AS rn
  FROM financing_acceptation_api_global_refined.financing_leads_data ld
  WHERE
    ld.create_date >= DATEADD(month, -3, CURRENT_DATE) -- Align with 3-month BQ history
    AND ld.product = 'f079451e-04dd-4741-b7e0-ee6ddedc6b7d' -- *** Filter ONLY for AutoEquity product ID ***
),
latest_intent_per_email AS (
  -- Find the most recent intent record for each cleaned email address
  SELECT
    i.id AS intent_id, i.email, i.name, i.second_name, i.last_name,
    i.second_last_name, i.phone_number, i.offer_option_selected,
    LOWER(
      CASE
        WHEN POSITION('+' IN i.email) > 0 THEN SUBSTRING(i.email FROM 1 FOR POSITION('+' IN i.email) - 1) || SUBSTRING(i.email FROM POSITION('@' IN i.email) FOR LENGTH(i.email))
        ELSE i.email
      END
    ) AS cleaned_email,
    ROW_NUMBER() OVER (
      PARTITION BY LOWER(CASE WHEN POSITION('+' IN i.email) > 0 THEN SUBSTRING(i.email FROM 1 FOR POSITION('+' IN i.email) - 1) || SUBSTRING(i.email FROM POSITION('@' IN i.email) FOR LENGTH(i.email)) ELSE i.email END)
      ORDER BY i.updated_at DESC, i.id DESC
    ) AS rn
  FROM kuna_data_api_global_refined.intents i
)
-- Final selection joining the latest lead and latest intent, applying all filters
SELECT
  ll.id AS lead_id,          -- Unique Lead Identifier
  ll.user_id,                -- User Identifier
  ll.create_date,            -- Lead Creation Date
  li.name,                   -- First Name
  li.last_name,              -- Last Name
  -- Cleaned Phone Number (CRITICAL - Verify RIGHT(10) logic is correct for your data)
  RIGHT(li.phone_number, 10) AS cleaned_phone_number
FROM latest_lead_per_email ll
JOIN latest_intent_per_email li ON ll.cleaned_email = li.cleaned_email AND li.rn = 1
WHERE
  ll.rn = 1 -- Ensure we only take the latest lead per email
  -- Filters confirming they didn't progress:
  AND ll.profiling_status IS NULL
  AND ll.vehicle_id IS NULL
  AND li.offer_option_selected IS NULL
  AND ll.simulation_id IS NULL
  AND ll.handoff_status IS NULL
  AND ll.transaction_id IS NULL;