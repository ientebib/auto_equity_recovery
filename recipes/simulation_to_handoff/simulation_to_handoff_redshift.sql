WITH
  lead_data AS (
    SELECT
      ld.id  AS lead_id,
      ld.user_id,
      LOWER(
        CASE
          WHEN POSITION('+' IN ld.user_email) > 0 THEN
            SUBSTRING(ld.user_email FROM 1 FOR POSITION('+' IN ld.user_email)-1)
            || SUBSTRING(ld.user_email FROM POSITION('@' IN ld.user_email))
          ELSE ld.user_email
        END
      )        AS clean_email,
      ld.create_date AS lead_created_at,
      ld.profiling_status
    FROM financing_acceptation_api_global_refined.financing_leads_data ld
    WHERE ld.product = 'f079451e-04dd-4741-b7e0-ee6ddedc6b7d'
      AND ld.create_date >= DATEADD(day, -20, CURRENT_DATE)
  ),
  entered_handoff AS (
    SELECT DISTINCT lead_id
    FROM financing_acceptation_api_global_refined.leads_audit
    WHERE field = 'OFFER_STATUS'
      AND new_value = 'ENTERED'
  ),
  eligible_leads AS (
    SELECT ld.*
    FROM lead_data ld
    LEFT JOIN entered_handoff eh USING (lead_id)
    WHERE eh.lead_id IS NULL
      AND (ld.profiling_status IS NULL OR RIGHT(ld.profiling_status,1) <> 'R')
  ),
  ranked_leads AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY clean_email ORDER BY lead_created_at DESC, lead_id DESC) AS rn
    FROM eligible_leads
  ),
  latest_lead_per_email AS (
    SELECT lead_id,
           user_id,
           clean_email,
           lead_created_at
    FROM ranked_leads
    WHERE rn = 1
  ),
  intents_clean AS (
    SELECT
      i.id,
      LOWER(
        CASE
          WHEN POSITION('+' IN i.email) > 0 THEN
            SUBSTRING(i.email FROM 1 FOR POSITION('+' IN i.email)-1)
            || SUBSTRING(i.email FROM POSITION('@' IN i.email))
          ELSE i.email
        END
      )                       AS cleaned_email,
      i.name,
      i.last_name,
      RIGHT(i.phone_number,10) AS cleaned_phone_number,
      i.updated_at
    FROM kuna_data_api_global_refined.intents i
  ),
  ranked_intents AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY cleaned_email ORDER BY updated_at DESC, id DESC) AS rn
    FROM intents_clean
    WHERE cleaned_email IN (SELECT clean_email FROM latest_lead_per_email)
  ),
  latest_intent AS (
    SELECT cleaned_email,
           name,
           last_name,
           cleaned_phone_number
    FROM ranked_intents
    WHERE rn = 1
  )
SELECT
  lle.lead_id,
  lle.user_id,
  lle.clean_email,
  li.name,
  li.last_name,
  li.cleaned_phone_number,
  lle.lead_created_at
FROM latest_lead_per_email AS lle
LEFT JOIN latest_intent AS li
  ON lle.clean_email = li.cleaned_email
WHERE li.cleaned_phone_number IS NOT NULL
ORDER BY lle.lead_created_at DESC;