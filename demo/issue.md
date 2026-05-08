# Demo App: Rate limit failed `POST /login` attempts

## User Story

As a demo operator, I want repeated failed sign-in attempts throttled by client IP so the demo app shows a realistic security control that can be exercised through both the browser flow and `curl`.

## Problem

The current demo app accepts unlimited failed `POST /login` attempts. That makes the auth path too forgiving for the Phase 0 end-to-end run and gives the Reviewer very little legitimate attack surface.

## Scope

- Add rate limiting to failed `POST /login` attempts.
- Allow at most 5 failed attempts per client IP in a rolling 60-second window.
- Return `429 Too Many Requests` plus a `Retry-After` header when the limit is active.
- Keep the demo UAT path tied to the existing browser login flow and the credentials from `demo/app/.env.example`.
- For this demo only, process-local in-memory tracking is acceptable.

## Acceptance Criteria

1. For one client IP, failed login attempts 1 through 5 are processed normally; if 5 failed attempts already exist for that IP in the immediately preceding rolling 60-second window, the next `POST /login` returns `429 Too Many Requests` instead of evaluating credentials.
2. While an IP remains blocked under that rolling window, every additional `POST /login` from that IP returns `429`, and the browser flow shows a human-readable wait message instead of silently failing.
3. Every `429` response includes `Retry-After` as an integer number of seconds computed by rounding up the remaining wait until the oldest counted failed attempt ages out of the rolling 60-second window; while the IP is still blocked, the value must never be `0`.
4. Once fewer than 5 failed attempts remain for that IP in the immediately preceding rolling 60-second window, the next login attempt is processed normally, and a correct login still follows the existing happy path: `303 See Other`, session cookie set, then access to `/notes`.
5. The rate limit is UAT-able on localhost in 6 failed submissions or fewer by using the demo account email from `demo/app/.env.example` with an incorrect password.

## Clarified Constraints

- Count failed attempts only.
- A successful login resets that IP's failed-attempt bucket if the IP is not already blocked.
- The limit uses a rolling window, not a fixed-duration ban. An IP becomes eligible again as soon as the oldest counted failed attempt falls outside the last 60 seconds.
- Once an IP is blocked, even a correct password from that same IP receives `429` until the rolling window no longer contains 5 failed attempts.
- The tracked identity for this issue is the client IP observed by the app during local development. Proxy-aware behavior and trusted forwarded headers are out of scope.
- `Retry-After` rounds up fractional seconds to the next integer and stays at `1` or greater while the IP is still blocked.

## Security Considerations

- Keep the invalid-login response generic. Do not reveal whether the email exists or whether only the password was wrong.
- Preserve the current session behavior for successful logins; the change should only affect throttling around `POST /login`.
- `Retry-After` must reflect the remaining wait until the oldest counted failed attempt leaves the rolling 60-second window and must not be missing on `429` responses.
- This is a demo safeguard, not a production-grade distributed limiter. Process restart and multi-instance drift are accepted limitations for Phase 0.

## Reviewer Attack Surface

- Off-by-one behavior between the 5th and 6th failed attempt.
- `Retry-After` math at the 60-second boundary or under small clock skew.
- Localhost IP bucketing differences such as `127.0.0.1` vs `::1`.
- Per-process storage means two app instances will not share counters.

## UAT Notes

1. Start the app using `demo/app/README.md`.
2. Open `http://127.0.0.1:8000/login`.
3. Use the demo email from `demo/app/.env.example` and intentionally submit a wrong password 6 times.
4. Confirm the 6th submission is rate limited and exposes `Retry-After`.
5. Wait the indicated number of seconds, then sign in with the correct password and confirm redirect to `/notes`.

Default demo credentials today are `demo@spanweave.dev` / `demo1234`, but the file in `demo/app/.env.example` remains the source of truth.

## Sample `curl` Requests

```bash
# Single failed attempt against the real login route
curl -i -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'email=demo@spanweave.dev' \
  --data-urlencode 'password=wrong-password'
```

```bash
# Trigger the limit locally: attempts 1-5 should stay on the normal invalid-login path,
# attempt 6 should return 429 and include Retry-After
for i in 1 2 3 4 5 6; do
  echo "== Attempt $i =="
  curl -i -s -X POST http://127.0.0.1:8000/login \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode 'email=demo@spanweave.dev' \
    --data-urlencode 'password=wrong-password' \
  | sed -n '1,12p'
done
```

```bash
# After waiting the reported Retry-After seconds, the normal login flow should work again
curl -i -c cookies.txt -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'email=demo@spanweave.dev' \
  --data-urlencode 'password=demo1234'
```
