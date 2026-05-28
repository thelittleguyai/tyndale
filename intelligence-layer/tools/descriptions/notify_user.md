# notify_user

mode: universal

## What it does
Sends a templated notification to the user on a chosen channel at a chosen urgency tier.

## When to use
- To surface an upcoming/overdue deadline, a completed result, or a needed action (per P2).
- By the Proactive Monitor cron at deadline thresholds.

## When NOT to use
- To send an email to a payer/provider on the user's behalf (that is `send_email`, gated, Full
  V1); for in-conversation responses (the Lead Planner composes those directly).

## Arguments
- `user_id` (UUID, required).
- `urgency_tier` (enum, required) — `urgent | action | success | info`.
- `channel` (enum, required) — `sms | push | email | in_app`.
- `message_template_id` (string, required) — e.g. `"deadline_7d"`.
- `template_vars` (dict, required) — e.g. `{"issue":"deductible correction","days":7}`.

## Returns
```json
{"notification_id":"ntf_5c…"}
```

## Errors and edge cases
- Unknown template or missing required `template_vars` → validation error naming the gap.
- Channel not configured for the user → falls back to `in_app` and notes the fallback.

## Used by
Lead Planner (V1-Lite), Proactive Monitor cron.
