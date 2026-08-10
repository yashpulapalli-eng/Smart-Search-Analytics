-- ============================================================
-- ShopSense AI Search — Core Analytics Queries
-- All metrics segmented by experiment variant (control = legacy,
-- treatment = ai_semantic) to set up the Day 6 A/B comparison.
-- ============================================================


-- 1. ZERO-RESULT RATE (primary metric)
-- % of searches that returned 0 products, by variant
SELECT
    ea.variant,
    COUNT(*) AS total_searches,
    SUM(CASE WHEN se.result_count = 0 THEN 1 ELSE 0 END) AS zero_result_searches,
    ROUND(100.0 * SUM(CASE WHEN se.result_count = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS zero_result_rate_pct
FROM search_events se
JOIN experiment_assignments ea ON se.user_id = ea.user_id
GROUP BY ea.variant;


-- 2. CTR (Click-Through Rate): clicks / searches, by variant
SELECT
    ea.variant,
    COUNT(DISTINCT se.event_id) AS total_searches,
    COUNT(DISTINCT ce.event_id) AS total_clicks,
    ROUND(100.0 * COUNT(DISTINCT ce.event_id) / COUNT(DISTINCT se.event_id), 2) AS ctr_pct
FROM search_events se
JOIN experiment_assignments ea ON se.user_id = ea.user_id
LEFT JOIN click_events ce ON ce.search_event_id = se.event_id
GROUP BY ea.variant;


-- 3. FULL FUNNEL: search -> click -> cart -> purchase, by variant
SELECT
    ea.variant,
    COUNT(DISTINCT se.event_id) AS searches,
    COUNT(DISTINCT ce.event_id) AS clicks,
    COUNT(DISTINCT ae.event_id) AS cart_adds,
    COUNT(DISTINCT pe.event_id) AS purchases,
    ROUND(100.0 * COUNT(DISTINCT ce.event_id) / COUNT(DISTINCT se.event_id), 2) AS search_to_click_pct,
    ROUND(100.0 * COUNT(DISTINCT ae.event_id) / NULLIF(COUNT(DISTINCT ce.event_id), 0), 2) AS click_to_cart_pct,
    ROUND(100.0 * COUNT(DISTINCT pe.event_id) / NULLIF(COUNT(DISTINCT ae.event_id), 0), 2) AS cart_to_purchase_pct,
    ROUND(100.0 * COUNT(DISTINCT pe.event_id) / COUNT(DISTINCT se.event_id), 2) AS search_to_purchase_pct
FROM search_events se
JOIN experiment_assignments ea ON se.user_id = ea.user_id
LEFT JOIN click_events ce ON ce.search_event_id = se.event_id
LEFT JOIN cart_events ae ON ae.search_event_id = se.event_id
LEFT JOIN purchase_events pe ON pe.search_event_id = se.event_id
GROUP BY ea.variant;


-- 4. AI SEARCH ADOPTION: % of treatment-group sessions with >=1 search
SELECT
    ea.variant,
    COUNT(DISTINCT s.session_id) AS total_sessions,
    COUNT(DISTINCT se.session_id) AS sessions_with_search,
    ROUND(100.0 * COUNT(DISTINCT se.session_id) / COUNT(DISTINCT s.session_id), 2) AS adoption_pct
FROM sessions s
JOIN experiment_assignments ea ON s.user_id = ea.user_id
LEFT JOIN search_events se ON se.session_id = s.session_id
GROUP BY ea.variant;


-- 5. DAU (Daily Active Users): unique users per day, by variant
SELECT
    ea.variant,
    DATE(se.timestamp) AS activity_date,
    COUNT(DISTINCT se.user_id) AS dau
FROM search_events se
JOIN experiment_assignments ea ON se.user_id = ea.user_id
GROUP BY ea.variant, DATE(se.timestamp)
ORDER BY activity_date, ea.variant;


-- 6. WAU (Weekly Active Users): unique users per 7-day window, by variant
SELECT
    ea.variant,
    (CAST(JULIANDAY(DATE(se.timestamp)) - JULIANDAY('2026-06-01') AS INT) / 7) AS week_number,
    COUNT(DISTINCT se.user_id) AS wau
FROM search_events se
JOIN experiment_assignments ea ON se.user_id = ea.user_id
GROUP BY ea.variant, week_number
ORDER BY week_number, ea.variant;


-- 7. 7-DAY RETENTION: of users active on day 0, % active again within days 1-7
-- (day 0 = each user's FIRST active day, not a fixed calendar date)
WITH first_activity AS (
    SELECT user_id, MIN(DATE(timestamp)) AS day0
    FROM search_events
    GROUP BY user_id
),
retained AS (
    SELECT
        fa.user_id,
        fa.day0,
        MAX(CASE
            WHEN DATE(se.timestamp) > fa.day0
             AND DATE(se.timestamp) <= DATE(fa.day0, '+7 days')
            THEN 1 ELSE 0
        END) AS returned_within_7d
    FROM first_activity fa
    JOIN search_events se ON se.user_id = fa.user_id
    GROUP BY fa.user_id, fa.day0
)
SELECT
    ea.variant,
    COUNT(DISTINCT r.user_id) AS day0_users,
    SUM(r.returned_within_7d) AS retained_users,
    ROUND(100.0 * SUM(r.returned_within_7d) / COUNT(DISTINCT r.user_id), 2) AS retention_7d_pct
FROM retained r
JOIN experiment_assignments ea ON r.user_id = ea.user_id
GROUP BY ea.variant;


-- 8. SEARCH SUCCESS RATE: % of searches followed by a click within 30s
SELECT
    ea.variant,
    COUNT(DISTINCT se.event_id) AS total_searches,
    COUNT(DISTINCT CASE
        WHEN ce.event_id IS NOT NULL
         AND (JULIANDAY(ce.timestamp) - JULIANDAY(se.timestamp)) * 86400 <= 30
        THEN se.event_id
    END) AS successful_searches,
    ROUND(100.0 * COUNT(DISTINCT CASE
        WHEN ce.event_id IS NOT NULL
         AND (JULIANDAY(ce.timestamp) - JULIANDAY(se.timestamp)) * 86400 <= 30
        THEN se.event_id
    END) / COUNT(DISTINCT se.event_id), 2) AS search_success_rate_pct
FROM search_events se
JOIN experiment_assignments ea ON se.user_id = ea.user_id
LEFT JOIN click_events ce ON ce.search_event_id = se.event_id
GROUP BY ea.variant;


-- 9. AVG SEARCH LATENCY (guardrail metric), by variant
SELECT
    ea.variant,
    ROUND(AVG(se.latency_ms), 1) AS avg_latency_ms,
    ROUND(MIN(se.latency_ms), 1) AS min_latency_ms,
    ROUND(MAX(se.latency_ms), 1) AS max_latency_ms
FROM search_events se
JOIN experiment_assignments ea ON se.user_id = ea.user_id
GROUP BY ea.variant;


-- 10. REVENUE PER SEARCH (business impact), by variant
SELECT
    ea.variant,
    COUNT(DISTINCT se.event_id) AS total_searches,
    COALESCE(SUM(pe.revenue), 0) AS total_revenue,
    ROUND(COALESCE(SUM(pe.revenue), 0) / COUNT(DISTINCT se.event_id), 2) AS revenue_per_search
FROM search_events se
JOIN experiment_assignments ea ON se.user_id = ea.user_id
LEFT JOIN purchase_events pe ON pe.search_event_id = se.event_id
GROUP BY ea.variant;
