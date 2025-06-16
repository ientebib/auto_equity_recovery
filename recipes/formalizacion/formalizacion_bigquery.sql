-- Empty BigQuery SQL file - ready to build together 

WITH 
  -- Get all messages for target phone numbers
  all_messages AS (
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
      AND a.creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
  ),
  
  -- Find the first message that indicates formalization phase start
  formalization_start AS (
    SELECT 
      cleaned_phone_number,
      MIN(creation_time) AS formalization_start_time
    FROM all_messages
    WHERE REGEXP_CONTAINS(LOWER(message), r'y estaré acompañándote en esta última parte del proceso')
    GROUP BY cleaned_phone_number
  )

-- Return only messages from formalization start onwards
SELECT 
  am.cleaned_phone_number,
  am.creation_time,
  am.msg_from,
  am.operator_alias,
  am.message
FROM all_messages am
INNER JOIN formalization_start fs 
  ON am.cleaned_phone_number = fs.cleaned_phone_number
WHERE am.creation_time >= fs.formalization_start_time
ORDER BY am.cleaned_phone_number, am.creation_time ASC; 