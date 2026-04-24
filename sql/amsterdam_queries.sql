-- ============================================================
-- Amsterdam Open Data Analytics
-- Sources: data.amsterdam.nl (open licence CC0)
--          Inside Airbnb: insideairbnb.com/amsterdam
-- ============================================================

-- 1. Short-term rental density by neighbourhood
SELECT
    n.neighbourhood                             AS neighbourhood,
    COUNT(l.id)                                 AS rental_listings,
    ROUND(AVG(l.price), 2)                      AS avg_price_per_night,
    ROUND(AVG(l.availability_365), 0)           AS avg_days_available,
    COUNT(l.id) * 1.0 / n.area_km2             AS listings_per_km2
FROM listings l
JOIN neighbourhoods n ON l.neighbourhood_cleansed = n.neighbourhood
GROUP BY n.neighbourhood, n.area_km2
ORDER BY listings_per_km2 DESC;


-- 2. Neighbourhood price bands
SELECT
    neighbourhood_cleansed                      AS neighbourhood,
    COUNT(*)                                    AS total_listings,
    ROUND(MIN(price), 2)                        AS min_price,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY price), 2) AS q1_price,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY price), 2) AS median_price,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY price), 2) AS q3_price,
    ROUND(MAX(price), 2)                        AS max_price,
    ROUND(AVG(price), 2)                        AS avg_price
FROM listings
WHERE price > 0
GROUP BY neighbourhood_cleansed
ORDER BY median_price DESC;


-- 3. Room type breakdown by neighbourhood
SELECT
    neighbourhood_cleansed                      AS neighbourhood,
    room_type,
    COUNT(*)                                    AS listing_count,
    ROUND(AVG(price), 2)                        AS avg_price,
    ROUND(100.0 * COUNT(*)
        / SUM(COUNT(*)) OVER (PARTITION BY neighbourhood_cleansed), 1) AS pct_of_neighbourhood
FROM listings
GROUP BY neighbourhood_cleansed, room_type
ORDER BY neighbourhood_cleansed, listing_count DESC;


-- 4. Highly available listings vs occasional rentals
SELECT
    neighbourhood_cleansed                      AS neighbourhood,
    SUM(CASE WHEN availability_365 >= 180 THEN 1 ELSE 0 END)  AS commercial_listings,
    SUM(CASE WHEN availability_365 < 60 THEN 1 ELSE 0 END)    AS occasional_listings,
    COUNT(*)                                                    AS total_listings,
    ROUND(100.0 * SUM(CASE WHEN availability_365 >= 180 THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 1)               AS pct_commercial
FROM listings
GROUP BY neighbourhood_cleansed
ORDER BY pct_commercial DESC;


-- 5. Review activity as proxy for occupancy (last 12 months)
SELECT
    l.neighbourhood_cleansed                    AS neighbourhood,
    COUNT(DISTINCT l.id)                        AS active_listings,
    COUNT(r.id)                                 AS reviews_last_12m,
    ROUND(COUNT(r.id) * 1.0 / NULLIF(COUNT(DISTINCT l.id), 0), 1) AS reviews_per_listing
FROM listings l
LEFT JOIN reviews r
    ON l.id = r.listing_id
    AND r.date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY l.neighbourhood_cleansed
ORDER BY reviews_per_listing DESC;


-- 6. Host concentration analysis (multi-listing hosts)
WITH host_listings AS (
    SELECT
        host_id,
        host_name,
        COUNT(*)                                AS listing_count,
        ROUND(AVG(price), 2)                    AS avg_price
    FROM listings
    GROUP BY host_id, host_name
)
SELECT
    CASE
        WHEN listing_count = 1 THEN '1 listing'
        WHEN listing_count BETWEEN 2 AND 5 THEN '2-5 listings'
        WHEN listing_count BETWEEN 6 AND 20 THEN '6-20 listings'
        ELSE '20+ listings (commercial operator)'
    END                                         AS host_type,
    COUNT(*)                                    AS host_count,
    SUM(listing_count)                          AS total_listings,
    ROUND(100.0 * SUM(listing_count)
        / (SELECT COUNT(*) FROM listings), 1)   AS pct_of_market
FROM host_listings
GROUP BY host_type
ORDER BY total_listings DESC;


-- 7. Seasonal demand patterns (review volume by month)
SELECT
    EXTRACT(MONTH FROM date)                    AS month_num,
    TO_CHAR(date, 'Month')                      AS month_name,
    COUNT(*)                                    AS review_count,
    COUNT(DISTINCT listing_id)                  AS active_listings
FROM reviews
WHERE date >= CURRENT_DATE - INTERVAL '2 years'
GROUP BY month_num, month_name
ORDER BY month_num;


-- 8. Price premium by proximity to city centre (Amsterdam Centraal)
-- Assuming a 'distance_to_centre_km' column computed in Python
SELECT
    CASE
        WHEN distance_to_centre_km < 1   THEN '< 1 km'
        WHEN distance_to_centre_km < 2   THEN '1-2 km'
        WHEN distance_to_centre_km < 3   THEN '2-3 km'
        WHEN distance_to_centre_km < 5   THEN '3-5 km'
        ELSE '5+ km'
    END                                         AS distance_band,
    COUNT(*)                                    AS listings,
    ROUND(AVG(price), 2)                        AS avg_price,
    ROUND(MEDIAN(price), 2)                     AS median_price
FROM listings
WHERE price > 0 AND distance_to_centre_km IS NOT NULL
GROUP BY distance_band
ORDER BY avg_price DESC;
