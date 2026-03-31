# Email Configuration — GL Intelligence Platform

## Production: SendGrid (recommended)

The approval_handler.py uses SendGrid for all email dispatch.
No OAuth, no browser prompts, works on Cloud Run.

### Setup

1. Create a SendGrid account at https://sendgrid.com
2. Create an API key: Settings → API Keys → Create API Key
3. Verify your sender domain or email
4. Set environment variables:

```bash
export SENDGRID_API_KEY="SG.your-key-here"
export FROM_EMAIL="noreply@betechnology.com"
export REVIEWER_EMAIL="controller@client.com"
export REVIEWER_NAME="Controller"
```

### Test

```bash
cd "FASB DISE ASSETS"
python3 approval_handler.py send-emails
```

### Cost

SendGrid free tier: 100 emails/day. Paid: $15/month for 50K emails.
At ~20 accounts per agent run, free tier is sufficient for all clients.

## Deprecated: Gmail OAuth

The approval_workflow.py file uses Gmail API with OAuth Desktop App credentials.
This requires browser-based token refresh and does NOT work on Cloud Run.
Only use for local development/testing.
