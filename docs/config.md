# How to Run the Current Version

The project includes a FastAPI backend and a separate command-line agent in `agent/`.

### 1. Clone the repository

```powershell
$ git clone https://github.com/fcl2002/Travel-Agent.git
$ cd travel-agent
```

This file contains the basic commands required to activate the virtual environment and run the project on Windows using VS Code and PowerShell.

## 1. Activate the venv

On Windows, run:

```powershell
$ .\.venv\Scripts\Activate.ps1
```
## 2. Instal dependencies

```powershell
$ pip install -r requirements.txt
```

## 3. Configure environment variables

Copy `.env.example` to `.env` if it does not already exist. The backend uses
`DATABASE_URL`. To use the command-line agent, also add your LLM API key:

```powershell
GROQ_API_KEY=your_api_key_here
```

## 4. Run the backend

Set `JWT_SECRET_KEY` in `.env` to a cryptographically random key before starting
the API; use the generation command in [README.md](../README.md). It preserves
an existing key and does not print the generated secret.

With Docker Desktop running and the virtual environment active:

```powershell
docker compose up -d --wait db
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. Stop the API with `Ctrl+C`.
Run the complete test suite, including PostgreSQL and server startup checks,
with `python -m pytest`.

## 5. Run the agent

You can start the agent with:

```powershell
$ python agent/main.py
```

or

```powershell
$ .\run.ps1
```

## 6. Stop the agent

```powershell
$ exit
```

or

```powershell
$ quit
```
