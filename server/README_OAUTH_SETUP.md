# OAuth Setup Guide for Graphiti

This guide explains how to set up OAuth authentication for Google and GitHub providers.

## Quick Start (Using API Key)

If you don't want to set up OAuth immediately, you can use the API key authentication:

1. The default API key is: `test-api-key-for-development`
2. Click "Use API Key" on the login page
3. Enter the API key and click "Login"

## Setting Up Google OAuth

1. **Go to Google Cloud Console**
   - Visit https://console.cloud.google.com/
   - Create a new project or select an existing one

2. **Enable APIs**
   - Go to "APIs & Services" → "Library"
   - Search for "Google+ API" and enable it

3. **Create OAuth Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - If prompted, configure the OAuth consent screen first:
     - Choose "External" for user type
     - Fill in required fields (app name, support email)
     - Add test users if needed

4. **Configure OAuth Client**
   - Application type: "Web application"
   - Name: "Graphiti Local Dev" (or any name you prefer)
   - Authorized JavaScript origins: `http://localhost:8002`
   - Authorized redirect URIs: `http://localhost:8002/auth/google/callback`
   - Click "Create"

5. **Copy Credentials**
   - Copy the Client ID and Client Secret
   - Update the `.env` file with these values

## Setting Up GitHub OAuth

1. **Go to GitHub Settings**
   - Visit https://github.com/settings/developers
   - Click "OAuth Apps" → "New OAuth App"

2. **Configure OAuth App**
   - Application name: "Graphiti Local Dev"
   - Homepage URL: `http://localhost:8002`
   - Authorization callback URL: `http://localhost:8002/auth/github/callback`
   - Click "Register application"

3. **Copy Credentials**
   - Copy the Client ID
   - Click "Generate a new client secret"
   - Copy the Client Secret
   - Update the `.env` file with these values

## Updating Environment Variables

Edit the `.env` file and replace the placeholder values:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your-actual-google-client-id
GOOGLE_CLIENT_SECRET=your-actual-google-client-secret

# GitHub OAuth
GITHUB_CLIENT_ID=your-actual-github-client-id
GITHUB_CLIENT_SECRET=your-actual-github-client-secret
```

## Testing OAuth

1. Restart the server after updating `.env`
2. Visit http://localhost:8002/login
3. Click "Continue with Google" or "Continue with GitHub"
4. Complete the OAuth flow
5. You should be redirected back to the main application

## Troubleshooting

- **"Provider not configured" error**: OAuth credentials are missing in `.env`
- **Redirect URI mismatch**: Ensure the callback URLs match exactly
- **Connection refused**: Make sure the server is running on port 8002
- **Invalid client**: Double-check your Client ID and Secret

## Security Notes

- Never commit real OAuth credentials to version control
- Use environment variables or secrets management in production
- The test `.env` file contains placeholder values only