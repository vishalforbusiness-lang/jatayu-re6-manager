# Jagdish Trading Company - Explosive Dealer Management System

Single-file offline management app for GST invoices, RE-6 register, inventory,
drivers, vehicles, parties, products, and settings.

## Run Locally

```bash
npm start
```

Open `http://127.0.0.1:3000`.

## Railway

Railway starts the app with:

```bash
node server.js
```

### Important: Persistent Data

Railway containers have temporary files. If you do not attach a Railway Volume,
saved parties, invoices, RE-6 records, settings, and user data will disappear
after a redeploy.

Create a Railway Volume for this service and mount it at:

```text
/data
```

The server stores all profiles in:

```text
/data/users.json
```

If your Railway Volume uses a different mount path, set this variable:

```text
DATA_DIR=/your-volume-path
```

Health check:

```text
/health
```
