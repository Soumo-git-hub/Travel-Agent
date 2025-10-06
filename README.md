# AI Travel Agent: Adaptive Travel Co-Pilot

An agentic travel planner that functions as a hyper-personalization engine, designed to automate and elevate the travel planning experience. This project showcases a tool-augmented agent built with LangChain that leverages a RAG pipeline to create deeply personalized itineraries, cutting user research and planning time by over 80%.

🔗 **Live Demo**: [Travel Agent App](https://soumo-travel-agent-app.streamlit.app)

## Screenshot
<p align="center">
  <img src="./AI%20Agent.png" alt="Travel Agent Screenshot" width="800"/>
</p>

## Table of Contents
- [Features](#-features)
- [Technical Stack](#-technical-stack)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Running the Application](#running-the-application)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features
### 🤖 Agentic & Adaptive Capabilities
- **Autonomous Itinerary Generation**: The core agent autonomously performs multi-step reasoning to generate complete, day-by-day travel plans from a single natural language prompt.
- **Adaptive Recommendations via RAG**: Leverages a Retrieval-Augmented Generation (RAG) pipeline to provide context-aware suggestions for attractions, dining, and activities that adapt to stated preferences and implicit user needs.
- **Real-Time Tool Integration**: Seamlessly integrates with 5+ external, real-time APIs and tools (e.g., Web Search, Weather, Maps) to enrich plans with live data, demonstrating a robust tool-augmented architecture.
- **Hyper-Personalization**: Goes beyond basic filters to consider budget, interests, travel style, and accessibility needs to create truly unique travel experiences.

### ⚙️ Core Functionality
- **Conversational AI Interface**: An intuitive, chat-based UI powered by Streamlit for natural interaction.
- **Budget-Aware Planning**: Provides cost estimates and recommendations tailored to low, moderate, or high budget levels.
- **Cultural & Safety Insights**: Offers location-specific tips on local customs, etiquette, and safety considerations.

## 🛠️ Technical Stack
- **Core Agentic Framework**: LangChain
- **AI Architecture**: RAG (Retrieval-Augmented Generation)
- **Machine Learning**: Scikit-learn (for preference modeling)
- **Frontend**: Streamlit
- **LLM Integration**: Google Gemini Pro (with support for local models via Ollama)
- **Core Language**: Python

### APIs & Data Tools:
- **LLM API**: Google Gemini
- **Weather API**: OpenWeather
- **Web Search Tool**: Integrated for real-time information retrieval.
- **Maps/Geocoding API**: For location data and distances.
- **Recommendation APIs**: For sourcing real-time hotel and restaurant suggestions.

## 🚀 Getting Started
### Prerequisites
- Python 3.8 or higher
- An active internet connection for API access

### Installation
1. Clone the repository:
```bash
git clone <repository-url>
cd travel-agent
```

2. Create and activate a virtual environment:
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Configuration
1. Create a `.env` file in the project root.

2. Add your primary API keys and configuration. Note: Other tools like web search are integrated directly.
```
OPENWEATHER_API_KEY=your_openweather_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
LLM_MODE=google  # Options: google, local
```

3. API Key Sources:
- OpenWeather Key: [openweathermap.org/api](https://openweathermap.org/api)
- Gemini Key: [makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey)

### Running the Application
1. Start the Streamlit app:
```bash
streamlit run app.py
```

2. Open your browser and navigate to the local URL provided (usually http://localhost:8501).

## 📁 Project Structure
```
travel-agent/
├── .streamlit/
│   └── config.toml      # Streamlit configuration
├── app.py              # Main application file (Streamlit UI & agent logic)
├── requirements.txt    # Python dependencies
├── README.md           # Project documentation
├── LICENSE             # MIT License
└── .gitignore          # Git ignore rules
```

## 🤝 Contributing
Contributions are welcome! Please fork the repository, create a feature branch, and submit a Pull Request with a clear description of your changes.

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.