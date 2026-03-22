# Frontend

## Dashboard (`frontend/dashboard/`)

Admin panel for managing users, enrollment, and viewing activity. Open `index.html` directly in a browser.

- **Mock mode** (default): Works without backend — shows sample data
- **Live mode**: Uncheck "Use mock data", set API base URL and API key (`dev-api-key-001`)

### Features

- **Snapshot**: Stat cards, auth attempt chart (24h), outcome donut chart
- **Enrollment**: Bluetooth device connection, people table, add/remove users
- **Activity**: Verification log with filtering
- **API reference**: Endpoint docs for live integration

### Enrollment flow

Users enroll through the dashboard (admin-driven). There is no self-service enrollment:

1. Admin adds a person in the People table
2. Connects BLE enrollment device (or uses simulate mode)
3. Captures ECG sample → sent to `POST /enroll` or `POST /relay/enrollment`
4. Backend stores embedding in ChromaDB + baseline stats in SQLite

## Color theme

Both apps share the same palette:

| Token   | Value     | Usage              |
|---------|-----------|--------------------|
| accent  | `#6C8EEF` | Periwinkle blue    |
| success | `#34D399` | Mint green         |
| danger  | `#E05555` | Coral red          |
| bg      | `#0B0D12` | Dark background    |
| font    | Inter     | Primary typeface   |
| mono    | JetBrains Mono | Code / data   |
