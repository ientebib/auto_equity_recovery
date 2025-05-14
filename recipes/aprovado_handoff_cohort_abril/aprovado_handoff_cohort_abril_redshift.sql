SELECT * FROM (
    WITH negativized_users AS (
        SELECT sf.user_id
        FROM serving.car_sales_funnel sf
        WHERE sf.country_iso = 'MX'
          AND sf.flg_gross_delivered
          AND NOT sf.flg_returned
          AND sf.car_payment_method = 'Financing'
          AND sf.financial_profiling_score IS NOT NULL
          AND sf.last_financial_application_bank_name IN ('KAVAK FINANCIAMIENTO', 'Kavak Capital', 'KUNA OD')
          AND sf.last_financial_application_resolution NOT IN (
              'no rejected', 'Without_resolution', 'Incomplete',
              'Solicitud incompleta', 'Solicitud Rechazada', 'Fraud revision'
          )
          AND sf.delivery_time >= DATEADD(month, -60, CURRENT_DATE)
    ),
    lead_data AS (
        SELECT
            ld.id AS lead_id,
            ld.user_id,
            ld.user_email,
            CASE
                WHEN POSITION('+' IN ld.user_email) > 0 THEN
                    SUBSTRING(ld.user_email FROM 1 FOR POSITION('+' IN ld.user_email) - 1) ||
                    SUBSTRING(ld.user_email FROM POSITION('@' IN ld.user_email))
                ELSE ld.user_email
            END AS bo_email,
            ld.vehicle_id,
            ld.profiling_status,
            (ld.create_date - INTERVAL '6 HOUR') AS lead_created_at
        FROM financing_acceptation_api_global_refined.financing_leads_data ld
        WHERE ld.product = 'f079451e-04dd-4741-b7e0-ee6ddedc6b7d'
    ),
    leads_audit_events AS (
        SELECT
            ld.lead_id,
            ld.bo_email,
            (fala.event_date - INTERVAL '6 HOUR') AS event_date,
            CASE
                WHEN fala.field = 'SIMULATION' AND fala.new_value IS NOT NULL THEN 'Simulation'
                WHEN fala.field = 'OFFER_STATUS' AND fala.new_value = 'ENTERED' THEN 'HandOff_Completed'
                WHEN fala.field = 'OFFER_STATUS' AND fala.new_value = 'APPROVED' THEN 'HandOff_Approved'
                WHEN fala.field = 'OFFER_STATUS' AND fala.new_value = 'REJECTED' THEN 'HandOff_Rejected'
                ELSE NULL
            END AS event_type
        FROM lead_data ld
        LEFT JOIN financing_acceptation_api_global_refined.leads_audit fala
            ON ld.lead_id = fala.lead_id
        WHERE fala.event_date IS NOT NULL
    ),
    profiling_events AS (
        SELECT lead_id, bo_email, lead_created_at AS event_date, 'Lead_Started' AS event_type
        FROM lead_data
        UNION ALL
        SELECT lead_id, bo_email, lead_created_at AS event_date, 'Completed_Profiling' AS event_type
        FROM lead_data
        WHERE profiling_status IS NOT NULL
        UNION ALL
        SELECT lead_id, bo_email, lead_created_at AS event_date, 'Approved_Profiling' AS event_type
        FROM lead_data
        WHERE profiling_status IS NOT NULL AND RIGHT(profiling_status, 1) != 'R'
    ),
    all_events AS (
        SELECT * FROM leads_audit_events WHERE event_type IS NOT NULL
        UNION ALL
        SELECT * FROM profiling_events
    ),
    user_event_summary AS (
        SELECT
            ae.bo_email,
            ld.user_id,
            MAX(ld.lead_id) AS last_lead_id,
            TO_CHAR(MIN(ae.event_date), 'YYYY-MM-DD') AS first_interaction,
            TO_CHAR(MAX(ae.event_date), 'YYYY-MM-DD') AS last_interaction_raw,
            COUNT(CASE WHEN ae.event_type = 'Lead_Started' THEN 1 END) AS count_lead_started,
            COUNT(CASE WHEN ae.event_type = 'Completed_Profiling' THEN 1 END) AS count_completed_profiling,
            COUNT(CASE WHEN ae.event_type = 'Approved_Profiling' THEN 1 END) AS count_approved_profiling,
            COUNT(CASE WHEN ae.event_type = 'Simulation' THEN 1 END) AS count_simulation,
            COUNT(CASE WHEN ae.event_type = 'HandOff_Completed' THEN 1 END) AS count_handoff_completed,
            COUNT(CASE WHEN ae.event_type = 'HandOff_Approved' THEN 1 END) AS count_handoff_approved,
            COUNT(CASE WHEN ae.event_type = 'HandOff_Rejected' THEN 1 END) AS count_handoff_rejected,
            TO_CHAR(MAX(CASE WHEN ae.event_type = 'Lead_Started' THEN ae.event_date END), 'YYYY-MM-DD') AS last_lead_started_date,
            TO_CHAR(MAX(CASE WHEN ae.event_type = 'Completed_Profiling' THEN ae.event_date END), 'YYYY-MM-DD') AS last_completed_profiling_date,
            TO_CHAR(MAX(CASE WHEN ae.event_type = 'Approved_Profiling' THEN ae.event_date END), 'YYYY-MM-DD') AS last_approved_profiling_date,
            TO_CHAR(MAX(CASE WHEN ae.event_type = 'Simulation' THEN ae.event_date END), 'YYYY-MM-DD') AS last_simulation_date,
            TO_CHAR(MAX(CASE WHEN ae.event_type = 'HandOff_Completed' THEN ae.event_date END), 'YYYY-MM-DD') AS last_handoff_completed_date,
            TO_CHAR(MAX(CASE WHEN ae.event_type = 'HandOff_Approved' THEN ae.event_date END), 'YYYY-MM-DD') AS last_handoff_approved_date,
            TO_CHAR(MAX(CASE WHEN ae.event_type = 'HandOff_Rejected' THEN ae.event_date END), 'YYYY-MM-DD') AS last_handoff_rejected_date
        FROM all_events ae
        LEFT JOIN lead_data ld ON ae.lead_id = ld.lead_id
        GROUP BY ae.bo_email, ld.user_id
    ),
    filtered AS (
        SELECT
            *,
            TO_DATE(last_interaction_raw, 'YYYY-MM-DD') AS last_interaction,
            -- Add the new column to identify the cohort based on last_approved_profiling_date
            CASE
                WHEN last_approved_profiling_date BETWEEN '2025-03-10' AND '2025-03-16' THEN 'COHORT 1'
                WHEN last_approved_profiling_date BETWEEN '2025-03-17' AND '2025-03-23' THEN 'COHORT 2'
                ELSE NULL -- Should not happen with the WHERE clause below, but good practice
            END AS cohort
        FROM user_event_summary
        -- Filter results based on the last_approved_profiling_date
        WHERE last_approved_profiling_date IS NOT NULL
          AND (last_approved_profiling_date BETWEEN '2025-03-10' AND '2025-03-16'
               OR last_approved_profiling_date BETWEEN '2025-03-17' AND '2025-03-23')
    ),
    bills_data AS (
        WITH users AS (
            SELECT
                ld.user_id,
                CASE
                    WHEN POSITION('+' IN ld.user_email) > 0 THEN
                        SUBSTRING(ld.user_email, 1, POSITION('+' IN ld.user_email) - 1) ||
                        SUBSTRING(ld.user_email, POSITION('@' IN ld.user_email))
                    ELSE ld.user_email
                END AS clean_email
            FROM financing_acceptation_api_global_refined.financing_leads_data ld
        ),
        financing_data AS (
            SELECT
                o.stock_id,
                od.installments,
                CAST(REPLACE(od.installment_amount, '''', '') AS DECIMAL(18, 2)) AS installment_amount,
                CAST(REPLACE(od.interest_rate, '''', '') AS DECIMAL(18, 2)) / 100 AS interest_rate,
                CAST(REPLACE(od.financing_amount, '''', '') AS DECIMAL(18, 2)) AS financing_amount
            FROM financing_acceptation_api_global_refined.offer o
            LEFT JOIN financing_acceptation_api_global_refined.offer_data od ON o.offer_data_id = od.id
        ),
        bills AS (
            SELECT
                b.bill_id,
                b.bill_status,
                b.bill_item_name,
                (b.bill_creation_date - INTERVAL '6 hour') AS bill_creation_date,
                c.email AS email
            FROM netsuite_global_refined.bill b
            JOIN netsuite_global_refined.clients c ON b.bill_client_id = c.client_id
            WHERE b.bill_item_name = 'Auto Equity'
        ),
        ranked_leads AS (
            SELECT
                ld.id AS lead_id,
                us.clean_email,
                ld.vehicle_id,
                b.bill_creation_date,
                b.bill_id,
                b.bill_status,
                b.bill_item_name,
                fd.interest_rate,
                fd.installments,
                fd.installment_amount,
                fd.financing_amount,
                ROW_NUMBER() OVER (
                    PARTITION BY us.clean_email
                    ORDER BY
                        CASE WHEN fd.financing_amount IS NOT NULL AND fd.financing_amount > 0 THEN 1 ELSE 0 END DESC,
                        CASE WHEN fd.installment_amount IS NOT NULL AND fd.installment_amount > 0 THEN 1 ELSE 0 END DESC,
                        CASE WHEN fd.interest_rate IS NOT NULL AND fd.interest_rate > 0 THEN 1 ELSE 0 END DESC,
                        b.bill_creation_date DESC
                ) AS rn
            FROM financing_acceptation_api_global_refined.financing_leads_data ld
            LEFT JOIN users us ON ld.user_id = us.user_id
            LEFT JOIN bills b ON us.clean_email = b.email
            LEFT JOIN financing_data fd ON fd.stock_id = ld.vehicle_id
            WHERE (ld.product = '0a332293-5126-4794-ab81-9dbbcceab97f' OR ld.product = 'f079451e-04dd-4741-b7e0-ee6ddedc6b7d')
                AND b.bill_id IS NOT NULL
        )
        SELECT *
        FROM ranked_leads
        WHERE rn = 1
    )
    SELECT
        f.bo_email,
        COALESCE(cp.growth_customer_type, 'NEW ACCOUNT KUNA') AS growth_customer_type,
        f.first_interaction,
        f.last_interaction_raw,
        f.last_lead_started_date,
        f.last_completed_profiling_date,
        f.last_approved_profiling_date,
        f.last_simulation_date,
        f.last_handoff_completed_date,
        f.last_handoff_approved_date,
        f.last_handoff_rejected_date,
        f.last_interaction,
        cp.phone,
        cp.phone AS cleaned_phone_number,
        cp.full_name,
        CASE
            WHEN cp.growth_customer_type = 'CUSTOMER' AND cp.sales_qty <> 0 AND cp.purchases_qty = 0 THEN 'customer_sales'
            WHEN cp.growth_customer_type = 'CUSTOMER' AND cp.sales_qty = 0 AND cp.purchases_qty <> 0 THEN 'customer_purchases'
            WHEN cp.growth_customer_type = 'CUSTOMER' AND cp.sales_qty <> 0 AND cp.purchases_qty <> 0 THEN 'customer_sales_purchases'
            WHEN cp.growth_customer_type IN ('POTENTIAL ACTIVATION', 'NEW ACCOUNT') AND cp.sales_lead_qty <> 0 AND (cp.registers_qty IS NULL OR cp.registers_qty = 0) THEN 'kavak_saleslead'
            WHEN cp.growth_customer_type IN ('POTENTIAL ACTIVATION', 'NEW ACCOUNT') AND (cp.sales_lead_qty IS NULL OR cp.sales_lead_qty = 0) AND cp.registers_qty <> 0 THEN 'kavak_purchaselead'
            WHEN cp.growth_customer_type IN ('POTENTIAL ACTIVATION', 'NEW ACCOUNT') AND cp.sales_lead_qty <> 0 AND cp.registers_qty <> 0 THEN 'kavak_lead360'
            WHEN cp.growth_customer_type = 'NEW ACCOUNT KUNA' THEN 'Kuna_new_account'
            ELSE NULL
        END AS growth_avenue,
        b.bill_creation_date,
        CASE WHEN nu.user_id IS NOT NULL THEN TRUE ELSE FALSE END AS car_loan_active,
        f.last_lead_id,
        i.max_loan,
        -- Include the new cohort column from the filtered CTE
        f.cohort
    FROM filtered f
    LEFT JOIN cdp_global_serving.customer_profile cp ON f.bo_email = cp.email
    LEFT JOIN bills_data b ON f.bo_email = b.clean_email
    LEFT JOIN negativized_users nu ON f.user_id = nu.user_id
    LEFT JOIN kuna_data_api_global_refined.intents i ON f.last_lead_id = i.id
    ORDER BY f.last_interaction DESC
    LIMIT 40000
) AS t1;
