# HirePatch

This project is now a small Python web app.

- `app.py` runs the server
- `hirepatch.db` stores listings in SQLite
- `index.html`, `styles.css`, and `script.js` power the frontend
- `render.yaml` and `Procfile` prepare the app for deployment

## Run locally

From this folder:

```sh
./run.sh
```

Then open:

```text
http://localhost:8000
```

If port `8000` is already busy, run:

```sh
PORT=8001 ./run.sh
```

The backend serves the site and exposes a JSON API at `/api/listings`.

It also exposes a simple health endpoint at `/health`.

## Real Messaging Setup

The `Send Message` button now uses the Python backend to send:

- SMS with Twilio
- Email with Resend

Create or edit `.env` in this folder. The app now loads it automatically on startup.

You can use `.env.example` as the template. The local `.env` file is already ignored by git.

Example:

```dotenv
TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN="your_twilio_auth_token"
TWILIO_FROM_NUMBER="+15551234567"
RESEND_API_KEY="re_xxxxxxxxx"
RESEND_FROM_EMAIL="HirePatch <noreply@yourdomain.com>"
```

Then start the server:

```sh
./run.sh
```

If any of those variables are missing, the message form will return a configuration error instead of sending.

## Deployment

The app is now prepared for deployment.

- It binds to `0.0.0.0` by default
- It supports `PORT`
- It supports `DB_PATH` and `DATA_DIR` for SQLite persistence
- It includes [render.yaml](/Users/jackbete/Applications/Job%20app/render.yaml) and [Procfile](/Users/jackbete/Applications/Job%20app/Procfile)

### Render

1. Push this project to GitHub.
2. In Render, create a new Blueprint or Web Service from the repo.
3. Render can use [render.yaml](/Users/jackbete/Applications/Job%20app/render.yaml) automatically.
4. Set these secret env vars in Render:
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_FROM_NUMBER`
   - `RESEND_API_KEY`
   - `RESEND_FROM_EMAIL`
5. Deploy and then open `/health` to confirm it is up.

### Important SQLite note

This app uses SQLite. On hosted platforms, you need persistent storage or your listings will be lost on redeploy/restart.

- Render: the included [render.yaml](/Users/jackbete/Applications/Job%20app/render.yaml) mounts a persistent disk at `/var/data`
- Other platforms: set `DB_PATH` to a persistent volume location

If you later want multi-user scaling or more durable hosting, move from SQLite to Postgres.

## Why `npm start` does not work

- There is no `package.json`
- This machine does not have `node` installed
