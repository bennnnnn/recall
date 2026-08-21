# Consumer product scorecard

This is the launch scorecard for Recall as a general consumer AI assistant. Review it
weekly during beta. Targets are starting guardrails, not promises; replace them with
cohort baselines after the first two weeks.

Product analytics events contain metadata only. They must never include prompts, message
text, search queries, attachment names, or free-form provider errors.

## Core outcomes

- Activation: at least 70% of new accounts send a first message within 24 hours.
- Successful first reply: at least 98% of activated users receive an assistant message.
- D1 retained: at least 30% of activated users send another message the next day.
- D7 retained: at least 15% of activated users send another message seven days later.
- Answer quality: fewer than 10% of rated assistant messages receive thumbs down.
- Reliability: fewer than 2% of chat turns end in a user-visible error.
- Performance: non-tool chat time to first token below 2 seconds at p50 and 6 seconds at p95.
- Stability: at least 99.5% crash-free mobile sessions in Sentry.
- Conversion: establish a beta baseline for paywall view → purchase start → successful Pro
  purchase before changing pricing or paywall copy.

## Data sources

- `users.created_at`: signup cohort.
- `messages`: activation, first successful reply, retention, and rated answer quality.
- `usage_daily`: active users, tokens, and estimated provider cost.
- `product_events`: paywall, purchase, and notification-permission funnels.
- `chat_stream_timing`, `turn_cost`, and structured error logs: latency, reliability, and cost.
- Sentry: crashes, unhandled errors, and affected-user counts.
- RevenueCat: entitlement state, revenue, refunds, and subscriber retention.

## Weekly queries

Activation and first-reply success:

```sql
WITH first_turn AS (
  SELECT
    u.id,
    u.created_at,
    MIN(m.created_at) FILTER (WHERE m.role = 'user') AS first_user_message,
    MIN(m.created_at) FILTER (WHERE m.role = 'assistant') AS first_assistant_message
  FROM users u
  LEFT JOIN messages m ON m.user_id = u.id
  GROUP BY u.id, u.created_at
)
SELECT
  date_trunc('week', created_at) AS cohort_week,
  COUNT(*) AS signups,
  COUNT(*) FILTER (
    WHERE first_user_message <= created_at + INTERVAL '24 hours'
  ) AS activated,
  COUNT(*) FILTER (
    WHERE first_user_message <= created_at + INTERVAL '24 hours'
      AND first_assistant_message IS NOT NULL
  ) AS received_first_reply
FROM first_turn
GROUP BY 1
ORDER BY 1;
```

D1 and D7 retention:

```sql
WITH activated AS (
  SELECT
    u.id,
    MIN(m.created_at)::date AS activation_day
  FROM users u
  JOIN messages m ON m.user_id = u.id AND m.role = 'user'
  GROUP BY u.id
)
SELECT
  activation_day,
  COUNT(*) AS activated_users,
  COUNT(*) FILTER (
    WHERE EXISTS (
      SELECT 1 FROM messages m
      WHERE m.user_id = activated.id
        AND m.role = 'user'
        AND m.created_at::date = activation_day + 1
    )
  ) AS d1_users,
  COUNT(*) FILTER (
    WHERE EXISTS (
      SELECT 1 FROM messages m
      WHERE m.user_id = activated.id
        AND m.role = 'user'
        AND m.created_at::date = activation_day + 7
    )
  ) AS d7_users
FROM activated
GROUP BY activation_day
ORDER BY activation_day;
```

Rated answer quality:

```sql
SELECT
  date_trunc('week', created_at) AS week,
  model,
  COUNT(*) FILTER (WHERE feedback = 'up') AS thumbs_up,
  COUNT(*) FILTER (WHERE feedback = 'down') AS thumbs_down
FROM messages
WHERE role = 'assistant' AND feedback IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2;
```

Purchase funnel:

```sql
SELECT
  date_trunc('week', recorded_at) AS week,
  COUNT(*) FILTER (WHERE name = 'paywall_viewed') AS paywall_views,
  COUNT(*) FILTER (WHERE name = 'purchase_started') AS purchase_starts,
  COUNT(*) FILTER (WHERE name = 'purchase_succeeded') AS purchase_successes,
  COUNT(*) FILTER (WHERE name = 'purchase_failed') AS purchase_failures
FROM product_events
GROUP BY 1
ORDER BY 1;
```

## Review rules

- Segment by signup week before comparing retention.
- Do not optimize conversion while first-reply success or crash-free sessions are below target.
- Do not choose models on benchmark reputation alone; compare latency, errors, cost, and message
  feedback from Recall users.
- Investigate aggregate changes first. Access message content only for explicit support or
  consented quality review.
- Ship one measurable product change at a time so the scorecard can explain the result.
