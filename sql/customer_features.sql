
WITH customer_step_counts AS (
    SELECT
        nameOrig AS customer_id,
        step,
        COUNT(*) AS transactions_in_step,
        SUM(amount) AS amount_in_step
    FROM transactions
    GROUP BY nameOrig, step
),

customer_history AS (
    SELECT
        customer_id,
        step,

        COALESCE(
            SUM(transactions_in_step) OVER (
                PARTITION BY customer_id
                ORDER BY step
                ROWS BETWEEN UNBOUNDED PRECEDING
                         AND 1 PRECEDING
            ),
            0
        ) AS customer_transaction_count,

        COUNT(*) OVER (
            PARTITION BY customer_id
            ORDER BY step
            ROWS BETWEEN UNBOUNDED PRECEDING
                     AND 1 PRECEDING
        ) AS customer_prior_active_steps,

        SUM(amount_in_step) OVER (
            PARTITION BY customer_id
            ORDER BY step
            ROWS BETWEEN UNBOUNDED PRECEDING
                     AND 1 PRECEDING
        ) AS historical_amount_sum

    FROM customer_step_counts
),

customer_features AS (
    SELECT
        customer_id,
        step,
        customer_transaction_count,
        customer_prior_active_steps,

        CASE
            WHEN customer_prior_active_steps > 0
            THEN CAST(customer_transaction_count AS DOUBLE)
                / customer_prior_active_steps
            ELSE NULL
        END AS customer_avg_transactions_per_active_step,


        CASE
            WHEN customer_transaction_count > 0
            THEN historical_amount_sum
                 / customer_transaction_count
            ELSE NULL
        END AS customer_avg_amount,

        CASE
            WHEN customer_transaction_count > 0 THEN 1
            ELSE 0
        END AS has_customer_history

    FROM customer_history
)

SELECT
    t.*,
    f.customer_transaction_count,
    f.customer_prior_active_steps,
    f.customer_avg_transactions_per_active_step,
    f.customer_avg_amount,
    f.has_customer_history,

    CASE
        WHEN f.customer_avg_amount > 0
        THEN t.amount / f.customer_avg_amount
        ELSE NULL
    END AS amount_vs_avg

FROM transactions AS t
JOIN customer_features AS f
    ON t.nameOrig = f.customer_id
   AND t.step = f.step;
