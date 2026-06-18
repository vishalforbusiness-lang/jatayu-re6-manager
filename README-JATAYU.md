# Jatayu RE6 Manager

Offline GST invoice, ledger, payment, vehicle, product, report, and PESO Form RE6 manager.

## Run Backend

```bash
pip install -r requirements.txt
python app.py
```

The API and built frontend are served at `http://127.0.0.1:5000`.

Default login:

- Username: `admin`
- Password: `admin123`

## Build Frontend

```bash
npm install
npm run build
```

The build is written to `dist/`, which Flask serves automatically.

## Desktop Build

```bash
npm run dist:desktop
```

This Electron configuration packages the built UI. For a single Python executable alternative, run:

```bash
pyinstaller --onefile --add-data "dist;dist" app.py
```
