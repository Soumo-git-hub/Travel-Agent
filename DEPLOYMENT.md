# AI Travel Agent Deployment Guide

This guide provides detailed instructions for deploying the AI Travel Agent application to various platforms.

## Prerequisites

Before deploying the application, ensure you have:

1. A GitHub account
2. Your project code pushed to a GitHub repository
3. API keys for:
   - OpenWeather
   - OpenRouter or OpenAI

## Deployment to Streamlit Cloud

### Step 1: Push Your Code to GitHub

1. Create a new GitHub repository if you haven't already
2. Initialize git in your project folder:
   ```
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/your-repo-name.git
   git push -u origin main
   ```

### Step 2: Create a Streamlit Cloud Account

1. Go to [Streamlit Cloud](https://streamlit.io/cloud)
2. Sign up using your GitHub account
3. Verify your email address

### Step 3: Deploy Your Application

1. Log in to Streamlit Cloud
2. Click "New app"
3. Select your GitHub repository, branch, and the main file (`app.py`)
4. Click "Deploy"

### Step 4: Configure Secrets

1. In your deployed app settings, navigate to "Secrets"
2. Add the following secrets:
   ```
   OPENWEATHER_API_KEY = "your-api-key"
   OPENROUTER_API_KEY = "your-api-key"
   # Optional: OPENAI_API_KEY = "your-api-key"
   LLM_MODE = "openrouter"  # or "openai"
   ```

### Step 5: Advanced Configuration (Optional)

- Set up a custom domain
- Configure resource limits
- Set scheduled app restarts

### Step 6: Verify Deployment

1. Open your app URL
2. Test the application by interacting with it
3. Ensure all core functionalities work properly

## Troubleshooting

### Common Issues and Solutions

1. **Application Error**
   - Check app logs in Streamlit Cloud dashboard
   - Verify requirements.txt includes all dependencies

2. **API Issues**
   - Verify API keys are correctly added as secrets
   - Check API usage limits

3. **Package Problems**
   - Ensure requirements.txt has correct package versions
   - Test locally before deployment

4. **Memory Limitations**
   - Optimize your code for memory usage
   - Consider upgrading your Streamlit Cloud plan

## Maintenance

- Monitor app usage on Streamlit Cloud dashboard
- Update your code regularly
- Keep an eye on your API usage

## Security Considerations

- Never commit API keys to your repository
- Use Streamlit secrets for sensitive information
- Monitor API usage for unauthorized access

## Additional Resources

- [Streamlit Cloud Documentation](https://docs.streamlit.io/streamlit-community-cloud)
- [OpenWeather API Documentation](https://openweathermap.org/api)
- [OpenRouter Documentation](https://openrouter.ai/docs) 