# AI Travel Agent

An intelligent travel assistant powered by AI that helps users plan trips, find destinations, and create personalized itineraries based on preferences, budget, and travel dates.

## Table of Contents
- [Demo](#demo)
- [Overview](#overview)
- [Technologies Used](#technologies-used)
- [Features](#features)
- [Setup & Installation](#setup--installation)
- [API Keys Required](#api-keys-required)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Demo

Experience the application live at: [AI Travel Agent Demo](https://soumo-travel-agent-app.streamlit.app)

## Overview

This AI-powered travel assistant uses natural language processing to understand your travel needs and preferences. It can recommend destinations, create detailed itineraries, provide weather forecasts, suggest activities, and offer budget-friendly options for your next adventure.

## Technologies Used

- **Streamlit**: For creating the interactive web interface and cloud deployment
- **LangChain**: For LLM tools integration, workflow management, and agent orchestration
- **OpenAI/Ollama**: For advanced natural language processing and understanding
- **SerpAPI/DuckDuckGo**: For real-time web search capabilities and up-to-date travel information
- **OpenWeather API**: For accurate weather forecasts at destinations
- **Python**: Core programming language for backend logic and data processing

## Features

- **Personalized Travel Recommendations**: Get destination suggestions based on your interests
- **Intelligent Itinerary Planning**: Create optimized day-by-day travel plans
- **Real-time Weather Information**: Access current and forecasted weather for better planning
- **Budget-conscious Options**: Find accommodations and activities that match your budget
- **Cultural Insights**: Learn about local customs, traditions, and must-see attractions
- **Interactive Chat Interface**: Communicate naturally with the AI assistant
- **Multi-modal Responses**: Receive information in text, lists, and structured formats

## Setup & Installation

1. Clone this repository:  `git clone https://github.com/Soumo-git-hub/Travel-Agent.git`
2. Navigate to the project directory: `cd Travel-Agent`
3. Install dependencies: `pip install -r requirements.txt`
4. Create a `.env` file with API keys (use `.env.template` as reference)
5. Run the application: `streamlit run app.py`

## API Keys Required

- **OpenAI API Key** (recommended) or use local Ollama for LLM functionality
- **SerpAPI Key** (optional but recommended for better search results)
- **OpenWeather API Key** (for weather information)

## Usage

The application can be run in two modes:
- **Streamlit UI**: `python -m streamlit run app.py` - For interactive web interface
- **API Server**: `python run_server.py --mode api` - For headless operation or integration with other services

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - Copyright (c) 2023 Soumyadyuti Dey

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files, to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software.