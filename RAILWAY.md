# Deploy on Railway

This repo contains **two** services. Create both in one Railway project from the same GitHub repository.

## 1. Telegram Notification API (web)

| Setting | Value |
|---------|-------|
| Dockerfile | `Dockerfile.notification` |
| Health check | `/health` |

**Environment variables:** copy from `config.env.example` and set in Railway dashboard.

## 2. Telegram App Bot (polling worker)

| Setting | Value |
|---------|-------|
| Dockerfile | `Dockerfile` |
| Health check | none |

Uses the same env vars as the notification API.

## Local development

```bash
cp config.env.example config.env
docker compose up -d
```
