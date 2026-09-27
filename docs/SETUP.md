## How to Run the Current Prototype

The project is currently designed to run locally through a command-line interface (CLI).

### 1. Clone the repository

```powershell
git clone <repository-url>
cd travel-agent
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

Create a .env file in the project root and add your Groq API key:

```powershell
GROQ_API_KEY=your_api_key_here
```

## 4. Run the project

You can start the agent with:

```powershell
$ python src/main.py
```

or

```powershell
$ .\run.ps1
```

## 5. Stop the agent

```powershell
$ exit
```

or

```powershell
$ quit
```