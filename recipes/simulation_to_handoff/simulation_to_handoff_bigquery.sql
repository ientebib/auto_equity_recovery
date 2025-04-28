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
ORDER BY cleaned_phone_number, a.creation_time ASC; 