# Browser authentication

Tokens do not belong in the user entity. Login creates a row in `auth_sessions`,
linked to the user. That row stores only the refresh token's hash and lifecycle
metadata. Separate logins, such as two devices, have independent sessions.

Registration (`POST /users`), login (`POST /auth/login`), and password updates
require passwords of 8 to 128 characters, inclusive. Registration and password
updates also require at least one uppercase letter, one digit (0–9), and one ASCII
punctuation character, such as `!`, `@`, `#`, `$`, or `%`. Whitespace is preserved
and does not count as a special character.
Login validates length only, allowing existing accounts to authenticate with their
original passwords. Invalid registration passwords and password lengths outside
these bounds return 422.

Authenticated users can change their own password with `PATCH /users/me`
and a JSON body containing `password`. This field shares the registration schema's
length and complexity checks. The service hashes it with Argon2id before saving;
responses never include the password or its hash. Missing or invalid bearer tokens
return 401. No route accepts a user ID, so another account cannot be addressed.

Changing `email` or `password` also requires `current_password`, so a stolen access
token alone cannot take over the account. A wrong value returns 403 (not 401: the
token is still valid) and changes nothing. If the new password equals the current
one, the request returns 400 and no account fields are changed. A successful
password change revokes every login session of the user, including the current
one: old access tokens and refresh cookies stop working and the client logs in again.

## API flow

1. `POST /auth/login` with JSON email/password and `credentials: "include"`.
   The response contains the access token and sets the refresh cookie.
   If the account is inactive, valid credentials reactivate it and update
   `updated_at`. Previous sessions are revoked, keeping their access and refresh
   tokens invalid. Reactivation and creation of the new session are atomic.
2. Keep the access token in memory and send it as `Authorization: Bearer ...`.
3. On page startup or access-token expiration, call `POST /auth/refresh` with
   credentials included and the `X-Requested-With: XMLHttpRequest` header.
   This works without an access token. The response gives a fresh access token
   and rotates the HttpOnly cookie.
4. `POST /auth/logout` with the same cookie credentials/custom header revokes
   that session and clears the cookie. Other devices keep their sessions.

Deactivation prevents protected requests and token refresh. Refresh does not
reactivate an account; the user must log in again with their email and password.
An incorrect password leaves the account inactive.

The backend cannot detect a page reload by itself. There is no frontend in this
repository yet; integrate the following pattern into the frontend's startup code:

```javascript
// Same-origin API by default; use the configured backend origin if separate.
const API_ORIGIN = "";
let accessToken = null;
let pendingRefresh = null;

async function restoreSession() {
  if (!pendingRefresh) {
    pendingRefresh = fetch(`${API_ORIGIN}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(async (response) => {
        if (!response.ok) {
          accessToken = null;
          throw new Error("Login required");
        }
        accessToken = (await response.json()).access_token;
        return accessToken;
      })
      .finally(() => { pendingRefresh = null; });
  }
  return pendingRefresh;
}

// Run once during application startup, including after a page reload.
try {
  await restoreSession();
  // Render the authenticated app; use accessToken in Authorization headers.
} catch {
  // Render the login screen.
}
```

After a successful login, retain its returned access token in the same in-memory
state. JavaScript must not read the refresh cookie or store it in localStorage.
HttpOnly makes the cookie unavailable to JavaScript while the browser still
sends it with credentialed fetch requests.

## Rotation and deployment

Refresh is single-use. Requests sharing one browser session must serialize
renewals. The shared promise above prevents parallel refreshes in one page;
coordinate across tabs too if the frontend supports simultaneous renewals.
Reusing an old signed refresh token revokes its session, requiring login again.
This intentionally fails closed instead of accepting the old token repeatedly.
Sessions expire after seven days by default, even with regular refreshes.

For HTTP localhost development, `.env.example` sets `REFRESH_COOKIE_SECURE=false`.
The application default is true and production must use HTTPS. Use the same host
consistently, such as `localhost` for both frontend and API; different ports are
supported with an exact `FRONTEND_ORIGIN`, but mixing `localhost` and `127.0.0.1`
will not work reliably with SameSite cookies. This setup is for same-site frontends;
an unrelated frontend domain requires a separate cookie/CORS security design.

## Rate limits and accepted risks

Login and registration are limited per client IP. `PATCH /users/me` is limited per
account (10 per 60 seconds per process) because it can run Argon2 and checks
`current_password`; excess requests return 429 with `Retry-After`.

Behind a gateway, set `FORWARDED_ALLOW_IPS` to the gateway's exact IP or CIDR.
Otherwise every request appears to come from the gateway, all clients share one
login limit, and 10 failed logins lock everyone out. Never use `*`: any client
could then spoof `X-Forwarded-For` and bypass the limit. Limits are per process,
so multiple workers or replicas also need a shared limit at the gateway.

Accepted risk: registration reveals whether a username or email is taken (409), so
account existence can be probed, at the per-IP registration rate. Login does not
leak this. Closing it requires email-verified registration that answers the same
way for new and existing emails; revisit when email delivery exists or if the API
is exposed beyond the internal network.

Old access tokens without session claims require a fresh login after this update.
Apply `python -m alembic upgrade head` before using the new auth routes.
