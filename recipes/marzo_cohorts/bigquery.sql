-- recipes/marzo_cohorts/bigquery.sql
-- Fetches conversation history from BigQuery for the specified phone numbers.
-- DO NOT MODIFY these column names: cleaned_phone_number, creation_time, msg_from, message

SELECT
    RIGHT(b.user_platform_contact_id, 10) AS cleaned_phone_number,
    a.creation_time,
    a.msg_from,
    a.operator_alias,
    a.message
FROM `botmaker-bigdata.ext_metric_kavakcapital.message_metrics` AS a
INNER JOIN `botmaker-bigdata.ext_metric_kavakcapital.session_metrics` AS b
        ON a.session_id = b.session_id
WHERE RIGHT(b.user_platform_contact_id, 10) IN UNNEST(@target_phone_numbers_list)
  AND a.creation_time <= TIMESTAMP('2025-05-07 23:59:59') -- Only messages up to May 7th, 2025
ORDER BY cleaned_phone_number, a.creation_time ASC;