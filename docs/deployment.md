# Deployment Documentation

This document provides step-by-step instructions for deploying the AI Travel Agent application to a Streamlit deployment platform.

## Prerequisites

Before deploying the application, ensure you have:

- A GitHub account
- Your API keys ready:
  - OpenAI API key (recommended) or setup for local model use
  - SerpAPI key (optional but recommended for better search results)
  - OpenWeather API key (for weather information)

## Local Setup and Testing

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd travel-agent
```

### Step 2: Configure Environment Variables

Create a `.env` file in the project root with the following variables:

```
# API Keys Configuration
OPENWEATHER_API_KEY=your-openweather-api-key
LLM_MODE=openai  # Options: local, openai
OPENAI_API_KEY=your-openai-api-key  # If using OpenAI mode
SERPAPI_API_KEY=your-serpapi-key  # Optional
```

Alternatively, for local LLM setup:

```
LLM_MODE=local
OPENAI_API_BASE=http://localhost:11434/v1  # For Ollama
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Run the Application Locally

```bash
streamlit run app.py
```

## Deployment to Streamlit Cloud

Streamlit Cloud offers a free tier for hosting Streamlit applications, making it an ideal choice for this project.

### Step 1: Push Your Code to GitHub

1. Create a new GitHub repository if you haven't already
2. Initialize git in your project folder (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/your-username/your-repo-name.git
   git push -u origin main
   ```

### Step 2: Create a Streamlit Cloud Account

1. Go to [Streamlit Cloud](https://streamlit.io/cloud)
2. Sign up using your GitHub account
3. Verify your email address

### Step 3: Deploy Your Application

1. Log in to Streamlit Cloud
2. Click "New app"
3. Select your GitHub repository, branch, and main file (`app.py`)
4. Click "Deploy"

### Step 4: Configure Secrets in Streamlit Cloud

1. In your deployed app settings, navigate to "Secrets"
2. Add your configuration in TOML format:
   ```toml
   [general]
   LLM_MODE = "openai"
   
   [openai]
   OPENAI_API_KEY = "your-openai-api-key"
   
   [search]
   SERPAPI_API_KEY = "your-serpapi-key"
   
   [weather]
   OPENWEATHER_API_KEY = "your-openweather-api-key"
   ```

### Step 5: Verify Deployment

1. Open your app URL
2. Test the application by interacting with it
3. Check that all functionalities work as expected

## Alternative Deployment Options

### Hugging Face Spaces

1. Create an account on [Hugging Face](https://huggingface.co/)
2. Create a new Space with Streamlit as the SDK
3. Upload your files or connect to your GitHub repository
4. Configure secrets in the Space settings

### Railway

1. Create an account on [Railway](https://railway.app/)
2. Create a new project from your GitHub repository
3. Add environment variables in the project settings
4. Deploy the application

## Troubleshooting Common Issues

### API Key Issues

**Problem**: The application fails to make API calls.
**Solution**: Verify that your API keys are correctly set in the environment variables or secrets.

### Package Installation Errors

**Problem**: Deployment fails due to package installation issues.
**Solution**: Check your `requirements.txt` file for any incompatible packages or version conflicts.

### Resource Limitations

**Problem**: The application crashes due to memory limitations.
**Solution**: Optimize your code for memory usage or upgrade your deployment plan.

### Local Model Connection

**Problem**: The application can't connect to the local LLM.
**Solution**: Ensure Ollama is running and the API base URL is correctly configured.

## Monitoring and Maintenance

- Regularly check your deployment platform's dashboard for any issues
- Monitor your API usage to avoid exceeding limits
- Update the application when new features or bug fixes are available

## Security Best Practices

- Never commit API keys to your repository
- Use environment variables or secrets management for sensitive information
- Regularly rotate your API keys
- Monitor for unusual API usage patterns

## Need Help?

If you encounter any deployment issues, please:

1. Check the troubleshooting section above
2. Review the logs in your deployment platform's dashboard
3. Consult the documentation for your specific deployment platform
4. Reach out to the repository maintainer 