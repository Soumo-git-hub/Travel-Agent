# AI Travel Agent

An intelligent travel planning assistant powered by AI that helps users create personalized travel itineraries. The app uses advanced language models and real-time data to provide comprehensive travel recommendations.

## Table of Contents
- [Features](#features)
- [Technologies Used](#technologies-used)
- [Setup](#setup)
- [Running Locally](#running-locally)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Features

- 🤖 **AI-Powered Chat Interface**
  - Natural language interaction for travel planning
  - Context-aware responses and recommendations
  - Support for both Google Gemini and local LLM models

- 📋 **Smart Itinerary Generation**
  - Personalized day-by-day travel plans
  - Activity recommendations based on interests
  - Flexible scheduling and customization

- 🌤️ **Real-time Weather Information**
  - Current weather conditions
  - Temperature, humidity, and wind speed
  - Weather alerts and travel advice

- 🍽️ **Dining & Attractions**
  - Restaurant recommendations with dietary preferences
  - Top attractions and points of interest
  - Special interest activities and experiences

- 💰 **Budget Planning**
  - Cost estimates for accommodations, food, and activities
  - Money-saving tips and recommendations
  - Budget level customization (low, moderate, high)

- ♿ **Accessibility Information**
  - Wheelchair-accessible attractions
  - Special needs accommodations
  - Travel tips for accessibility

- 🌍 **Location-Specific Features**
  - Local customs and etiquette
  - Transportation options
  - Cultural insights and recommendations

## Technologies Used

- **Frontend**: Streamlit
- **AI/ML**: 
  - Google Gemini Pro
  - LangChain
  - Local LLM support (Ollama)
- **APIs**: 
  - OpenWeather API
  - Web Search Integration
- **Data Processing**: BeautifulSoup4, Requests

## Setup

1. Clone the repository:
```bash
git clone https://github.com/Soumo-git-hub/Travel-Agent.git

cd travel-agent
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your API keys:
```
OPENWEATHER_API_KEY=your_openweather_api_key
GEMINI_API_KEY=your_gemini_api_key
LLM_MODE=google  # or 'local' for local LLM
```

## Running Locally

1. Start the Streamlit app:
```bash
streamlit run app.py
```

2. Open your browser and navigate to `http://localhost:8501`

## Usage

1. Start a new chat by clicking the "Start New Chat" button
2. Tell the AI where you want to travel
3. Provide additional information like:
   - Duration of stay
   - Budget level
   - Interests and preferences
   - Any special requirements
4. The AI will generate a personalized itinerary
5. Ask follow-up questions about specific aspects of your trip
6. Download your itinerary as a markdown file

## Project Structure

```
travel-agent/
├── .streamlit/
│   └── config.toml      # Streamlit configuration
├── app.py              # Main application file
├── requirements.txt    # Python dependencies
├── README.md          # Project documentation
├── LICENSE            # MIT License
└── .gitignore         # Git ignore rules
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Google Gemini for AI capabilities
- OpenWeather for weather data
- Streamlit for the web framework
- All contributors and users of the project