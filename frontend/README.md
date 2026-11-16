# Responda frontend

## Run locally

1. Start the backend on port 8000:

   ```powershell
   cd ..\backend
   uvicorn app.main:app --reload
   ```

2. In a second terminal, start the frontend:

   ```powershell
   cd frontend
   npm run dev
   ```

Open `http://localhost:5173`. The API URL defaults to
`http://127.0.0.1:8000/api/v1`; override it in a `.env` file with
`VITE_API_BASE_URL` when deploying.

## Production build

```powershell
npm run build
```
