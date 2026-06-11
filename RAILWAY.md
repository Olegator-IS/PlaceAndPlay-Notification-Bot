# Deploy on Railway

Two services from one GitHub repo. Set **Dockerfile path in Railway UI** for each service.

## 1. Notification API (web)

| Setting | Value |
|---------|-------|
| Builder | `Dockerfile` |
| Dockerfile path | `Dockerfile.notification` |
| Health check | off or `/health` |
| Public domain | yes |

**Variables (minimum):**
- `TELEGRAM_BOT_TOKEN`
- `NOTIFICATION_API_KEY`

## 2. App Bot worker (polling)

| Setting | Value |
|---------|-------|
| Builder | `Dockerfile` |
| Dockerfile path | `Dockerfile` |
| Health check | **off** |
| Public domain | **no** |

**Variables:** all from `config.env.example`.

## Auth Service (after API is live)

- `APP_TELEGRAM_BOT_NOTIFICATION_SERVICE_URL` = notification API public URL
- `TELEGRAM_BOT_API_KEY` = same as `NOTIFICATION_API_KEY`
- `APP_TELEGRAM_BOT_TOKEN` = same as App Bot `TELEGRAM_BOT_TOKEN`
