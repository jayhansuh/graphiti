# API Authentication

This service now supports a minimal API key authentication mechanism to prevent
unrestricted access to endpoints. Set the `API_KEY` environment variable (or the
`api_key` setting in `.env`) and include the same value in the
`X-API-Key` request header to access protected routes.

## About OAuth and User Control

Adding full OAuth-based authentication with user accounts is feasible but more
involved than the simple API key approach. Implementing OAuth 2.0 would require:

- Integrating with an identity provider (Auth0, GitHub, etc.)
- Managing authorization flows and redirect/callback URLs
- Storing and validating access tokens for each request
- Potentially handling refresh tokens and user sessions

For command line or programmatic clients, workflows similar to the GitHub CLI's
browser-based login can be achieved using OAuth device code flows or
authorization code flows. While libraries such as `fastapi-users` and
`authlib` simplify much of the work, setting up user management, consent, and
secure storage still introduces extra operational complexity compared to a
static API key.

In summary, OAuth offers fine-grained user control and revocable credentials but
requires additional infrastructure and configuration. The current API key scheme
provides a lightweight safeguard and can serve as a stepping stone toward more
comprehensive authentication when needed.
