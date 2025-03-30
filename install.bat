@echo off
echo ===================================================
echo Installing AI Travel Agent dependencies...
echo ===================================================
echo.

echo Step 1: Verifying Python installation...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Ensure "Add Python to PATH" is checked during installation.
    pause
    exit /b 1
)
echo Python found successfully.
echo.

echo Step 2: Installing core dependencies...
python -m pip install --upgrade pip
python -m pip install streamlit==1.31.0
python -m pip install requests==2.31.0
python -m pip install python-dotenv==1.0.1
echo Core dependencies installed.
echo.

echo Step 3: Installing LangChain and related packages...
python -m pip install "langchain>=0.1.10,<0.2.0"
python -m pip install langchain-community==0.0.13
python -m pip install langchain-openai==0.0.2
python -m pip install duckduckgo-search==3.9.6
python -m pip install pydantic==2.5.2
echo LangChain packages installed.
echo.

echo Step 4: Installing OpenAI and Hugging Face packages...
python -m pip install openai>=1.10.0
python -m pip install huggingface_hub==0.20.3
python -m pip install transformers==4.36.2
echo OpenAI and Hugging Face packages installed.
echo.

echo Step 5: Installing CrewAI...
python -m pip install crewai==0.28.4
echo CrewAI installed.
echo.

echo Step 6: Verifying Streamlit installation...
python -c "import streamlit" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Streamlit installation failed.
    echo Try running: python -m pip install streamlit --no-cache-dir
    pause
    exit /b 1
)
echo Streamlit verified successfully.
echo.

echo ===================================================
echo Installation complete!
echo ===================================================
echo.
echo IMPORTANT NOTICE FOR USING LOCAL MODELS:
echo - To use Ollama, download it from https://ollama.com/
echo - Install it and run it before starting this app
echo - Run: ollama pull llama3
echo.
echo To run with an API service instead, edit the .env file:
echo - Set LLM_MODE=openrouter to use OpenRouter
echo - Add your API key in the .env file
echo.
echo To run the application, type: run.bat
echo.
pause 