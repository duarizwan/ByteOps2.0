---
description: How to connect Gmail OAuth2 to ByteOps
---

## Prerequisites
- Google account with access to Google Cloud Console
- ByteOps backend running on `http://localhost:8000`

---

## Step 1 — Create a Google Cloud Project

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown (top-left) → **New Project**
3. Name it `ByteOps` → **Create**
4. Make sure the new project is selected in the dropdown

---

## Step 2 — Enable the Gmail API

1. In the left menu go to **APIs & Services → Library**
2. Search for **Gmail API** → click it → **Enable**

---

## Step 3 — Configure the OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. User Type: **External** → **Create**
3. Fill in:
   - App name: `ByteOps`
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue** (skip Scopes and Test Users screens for now)
5. Back on the consent screen, click **Add users** under **Test users** → add your Gmail address

---

## Step 4 — Create OAuth2 Credentials

1. Go to **APIs & Services → Credentials → + Create Credentials → OAuth 2.0 Client ID**
2. Application type: **Web application**
3. Name: `ByteOps Local`
4. Under **Authorised redirect URIs** click **+ Add URI** and enter:
   ```
   http://localhost:8000/api/auth/gmail/callback
   ```
5. Click **Create**
6. A dialog shows your **Client ID** and **Client Secret** — copy both

---

## Step 5 — Add Credentials to Backend `.env`

Open `d:\uni\FYP\ByteOps\backend\.env` and add:

```env
GMAIL_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-<your-client-secret>
```

---

## Step 6 — Restart the Backend

```powershell
# Stop the running uvicorn (Ctrl+C), then:
uv run uvicorn app.main:app --reload --port 8000
```

---

## Step 7 — Test the Connection

1. Open `http://localhost:3000/settings`
2. Click **Connect** on the Gmail card
3. You should be redirected to Google's OAuth consent screen
4. Sign in and approve the permissions
5. You'll be redirected back to `/settings?connected=gmail` and the card will show **Connected**
