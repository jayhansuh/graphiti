# Quick Start Guide

## The OAuth Error You're Seeing

You're getting "401: invalid_client" because the OAuth credentials are placeholders. This is expected!

## Two Options to Continue:

### Option 1: Use API Key (Immediate Access)
1. Go to http://localhost:8002/login
2. Click "Use API Key"
3. Enter: `test-api-key-for-development`
4. You're in!

### Option 2: Set Up Real OAuth
1. Get credentials from Google/GitHub (see `/docs/OAUTH_SETUP_DETAILED.md`)
2. Update the `.env` file with real credentials
3. Restart the server
4. OAuth will work!

## The OAuth implementation is complete and working - it just needs real credentials from Google/GitHub to function.