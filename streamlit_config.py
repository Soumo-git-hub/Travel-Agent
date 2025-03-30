import os
import streamlit as st

def is_streamlit_cloud():
    """Check if the app is running on Streamlit Cloud"""
    return os.environ.get('STREAMLIT_SHARING', '') == 'true' or os.environ.get('STREAMLIT_CLOUD', '') == 'true'

def setup_streamlit_secrets():
    """Set up environment variables from Streamlit secrets when deployed"""
    if is_streamlit_cloud():
        print("Running on Streamlit Cloud, using secrets")
        # Set OpenRouter as default for cloud deployment
        os.environ['LLM_MODE'] = 'openrouter'
        
        # Set API keys from Streamlit secrets
        if 'OPENROUTER_API_KEY' in st.secrets:
            os.environ['OPENROUTER_API_KEY'] = st.secrets['OPENROUTER_API_KEY']
        
        if 'OPENWEATHER_API_KEY' in st.secrets:
            os.environ['OPENWEATHER_API_KEY'] = st.secrets['OPENWEATHER_API_KEY']
            
        if 'OPENAI_API_KEY' in st.secrets:
            os.environ['OPENAI_API_KEY'] = st.secrets['OPENAI_API_KEY']
    else:
        print("Running locally, using .env file") 