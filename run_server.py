import argparse
import subprocess
import sys
import os
from dotenv import load_dotenv

def run_streamlit():
    """Run the Streamlit application"""
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])

def run_api():
    """Run the FastAPI server"""
    subprocess.run([sys.executable, "api.py"])

def main():
    parser = argparse.ArgumentParser(description='Run the Travel Agent application')
    parser.add_argument('--mode', choices=['streamlit', 'api'], default='streamlit',
                      help='Choose the mode to run the application (default: streamlit)')
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    if args.mode == 'streamlit':
        print("Starting Streamlit application...")
        run_streamlit()
    else:
        print("Starting API server...")
        run_api()

if __name__ == "__main__":
    main() 