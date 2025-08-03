# OAuth Setup Guide for Graphiti Server

This guide explains how to set up OAuth authentication with Google and GitHub for the Graphiti server.

## Overview

The Graphiti server now supports OAuth 2.0 authentication alongside the existing API key authentication. This enables:

- User-specific document ownership and access control
- Secure authentication via Google and GitHub
- Document sharing between users
- Fine-grained permissions (Owner, Editor, Viewer)

## Prerequisites

1. PostgreSQL database for user data storage
2. (Optional) Redis for session state management
3. OAuth application credentials from Google and/or GitHub

## Environment Variables

Add the following to your `.env` file:

```bash
# Required: PostgreSQL connection string for user database
POSTGRES_URI=postgresql+asyncpg://user:password@localhost:5432/graphiti_users

# Required: JWT secret for session tokens
JWT_SECRET_KEY=your-secret-key-here-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# OAuth redirect base URL (your server URL)
OAUTH_REDIRECT_BASE_URL=http://localhost:8000

# Google OAuth (optional - only if using Google)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# GitHub OAuth (optional - only if using GitHub)
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Redis URL (optional - for CSRF state storage)
REDIS_URL=redis://localhost:6379
```

## Setting Up OAuth Applications

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Application type: "Web application"
6. Add authorized redirect URI: `http://localhost:8000/auth/google/callback`
7. Copy the Client ID and Client Secret

### GitHub OAuth Setup

1. Go to GitHub Settings → Developer settings → OAuth Apps
2. Click "New OAuth App"
3. Fill in:
   - Application name: "Graphiti"
   - Homepage URL: `http://localhost:8000`
   - Authorization callback URL: `http://localhost:8000/auth/github/callback`
4. Copy the Client ID and Client Secret

## Database Setup

The server will automatically create the required tables on startup, but you can also run migrations manually:

```bash
cd server
alembic upgrade head
```

## API Endpoints

### Authentication Endpoints

#### Initiate OAuth Login
```
POST /auth/{provider}/login
```
Providers: `google`, `github`

Returns:
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "random-state-string"
}
```

#### OAuth Callback (handled automatically)
```
GET /auth/{provider}/callback?code=...&state=...
```
Redirects to frontend with JWT token

#### Get Current User
```
GET /auth/me
Authorization: Bearer <jwt-token>
```

#### Logout
```
POST /auth/logout
```

### Document Ownership Endpoints

#### Get User's Documents
```
GET /auth/documents/owned
Authorization: Bearer <jwt-token>
```

#### Share Document
```
POST /auth/documents/{group_id}/share
Authorization: Bearer <jwt-token>
Content-Type: application/json

{
  "user_email": "user@example.com",
  "permissions": "viewer"  // owner, editor, viewer
}
```

#### Revoke Access
```
DELETE /auth/documents/{group_id}/access/{user_id}
Authorization: Bearer <jwt-token>
```

#### Get Document Users
```
GET /auth/documents/{group_id}/users
Authorization: Bearer <jwt-token>
```

## Authentication Flow

1. Frontend calls `POST /auth/{provider}/login`
2. Frontend redirects user to the authorization URL
3. User authenticates with OAuth provider
4. Provider redirects to `/auth/{provider}/callback`
5. Server exchanges code for tokens and creates/updates user
6. Server generates JWT and redirects to frontend with token
7. Frontend stores JWT and includes in future requests

## Using Both Auth Methods

The server supports both OAuth and API key authentication:

- **OAuth**: Use `Authorization: Bearer <jwt-token>` header
- **API Key**: Use `X-API-Key: <api-key>` header

OAuth users have document ownership and access control, while API key access has full permissions (suitable for programmatic access).

## Document Ownership

When OAuth users create documents (via `/messages` endpoint):
- If no `group_id` is provided, a new one is generated
- The user becomes the document owner automatically
- Only users with appropriate permissions can access the document

## Security Features

1. **CSRF Protection**: State parameter validation
2. **Rate Limiting**: 5 login attempts per 5 minutes per IP
3. **JWT Expiration**: Tokens expire after 24 hours by default
4. **Permission Levels**: Owner > Editor > Viewer
5. **Secure Redirects**: Only configured URLs allowed

## Troubleshooting

### Common Issues

1. **"Provider not configured"**: Ensure OAuth credentials are in `.env`
2. **Database connection errors**: Check PostgreSQL is running and URI is correct
3. **CSRF state mismatch**: Ensure Redis is running if configured
4. **JWT decode errors**: Check JWT_SECRET_KEY is consistent

### Testing

Test OAuth flow with curl:

```bash
# Get login URL
curl -X POST http://localhost:8000/auth/google/login

# Test with JWT token
curl -H "Authorization: Bearer <jwt-token>" http://localhost:8000/auth/me
```

## Production Considerations

1. Use HTTPS for production deployments
2. Set secure session cookies
3. Configure proper CORS settings
4. Use a persistent Redis instance for state storage
5. Set strong JWT secret keys
6. Monitor rate limiting and adjust as needed
7. Regular security audits of user permissions