-- BigQuery Query: Get Conversation History for a List of Phone Numbers
-- IMPORTANT: Phone number formatting must match between Redshift and BigQuery
-- The RIGHT(user_platform_contact_id, 10) logic extracts the last 10 digits of phone numbers
-- This MUST be identical to the phone number processing in redshift_query.sql

SELECT
    -- Cleaned phone number for joining back to Redshift data later
    -- CRITICAL: Verify RIGHT(10) logic matches Redshift's cleaned_phone_number format
    RIGHT(b.user_platform_contact_id, 10) AS cleaned_phone_number,
    -- Essential fields for context and ordering
    a.creation_time,      -- Timestamp of the message
    a.msg_from,           -- Identifies 'bot' or 'operator' (or potentially 'user')
    a.operator_alias,     -- Provides agent name if available (often NULL for bot/user)
    a.message             -- The core message content
FROM
    `botmaker-bigdata.ext_metric_kavakcapital.message_metrics` AS a
INNER JOIN
    `botmaker-bigdata.ext_metric_kavakcapital.session_metrics` AS b
    ON a.session_id = b.session_id
WHERE
    -- Filter for the list of phone numbers obtained from Redshift
    RIGHT(b.user_platform_contact_id, 10) IN UNNEST(@target_phone_numbers_list)
    -- Ensure we only pull data within the last 3 months (aligns with Redshift & BQ limits)
    AND a.creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
ORDER BY
    cleaned_phone_number, -- Group messages by phone number
    a.creation_time ASC   -- Order messages chronologically for each phone 