@echo off
echo ===================================================
echo Starting AI Travel Agent...
echo ===================================================
echo.

echo Checking LLM settings in .env file...
for /f "tokens=2 delims==" %%a in ('findstr "LLM_MODE" .env') do set LLM_MODE=%%a
echo Current LLM Mode: %LLM_MODE%
echo.

echo Note: The application will try OpenRouter first, then fall back to Ollama,
echo and finally to OpenAI if needed.
echo.

echo Starting Streamlit application...
python -m streamlit run app.py

pause 