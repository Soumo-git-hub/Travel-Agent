# AI Travel Agent

An AI-powered travel planning assistant that provides personalized travel itineraries based on user preferences, budget, duration and interests.

## Features

- **Intelligent Information Extraction**: Automatically extracts travel details from user conversations
- **Personalized Recommendations**: Suggests attractions, restaurants and accommodations based on specific preferences
- **Web Search Integration**: Uses real-time web search to provide up-to-date information
- **Detailed Itineraries**: Creates day-by-day itineraries with morning, afternoon, and evening activities
- **Flexible Input Handling**: Can process both structured and conversational inputs
- **Dietary & Accessibility Awareness**: Incorporates dietary preferences and mobility concerns

## Technologies Used

- **Streamlit**: For the web interface and deployment
- **LangChain**: For LLM tools and workflow management
- **OpenAI/Ollama**: For natural language processing
- **SerpAPI/DuckDuckGo**: For web search capabilities
- **OpenWeather API**: For weather information

## System Architecture

The application uses a multi-stage prompt system:

1. **Information Extraction**: Identifies key travel details from user input
2. **Clarification Prompts**: Proactively requests missing information
3. **Recommendations**: Generates curated suggestions aligned with preferences
4. **Itinerary Generation**: Creates comprehensive day-by-day travel plans

## Setup & Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with API keys (use `.env.template` as reference)
4. Run the application: `streamlit run app.py`

## API Keys Required

- **OpenAI API Key** (recommended) or use local Ollama for LLM functionality
- **SerpAPI Key** (optional but recommended for better search results)
- **OpenWeather API Key** (for weather information)

## Prompt System Design

The system employs carefully designed prompts for different stages:

- **Extraction Prompt**: Identifies destination, duration, budget, preferences, etc.
- **Clarification Prompt**: Asks targeted questions about missing information
- **Suggestion Prompt**: Presents destination-specific recommendations
- **Itinerary Prompt**: Creates a logical day-by-day plan with timing considerations

See `PROMPT_SYSTEM.md` for detailed documentation of all prompt templates.

## Demo

The application is hosted at: [AI Travel Agent Demo](https://your-demo-link-here)

## Using the Application

1. Tell the agent about your travel plans in conversational language
2. The agent will extract information and ask for clarifications if needed
3. Review suggested attractions, restaurants, and accommodations
4. Request a detailed itinerary when ready
5. Get a comprehensive day-by-day plan with timing and budget considerations

## Sample Interactions

**User**: "I want to visit Tokyo for 5 days with a moderate budget. I love food experiences and technology."

**Assistant**: [Extracts information, asks clarifying questions, and provides recommendations]

**User**: "Generate an itinerary for me."

**Assistant**: [Creates a 5-day Tokyo itinerary with food and technology focus]

## Contributors

- Your Name

## License

MIT License

## Supported Destinations

Paris, London, New York, Tokyo, Rome, Barcelona, Sydney, Dubai, Bangkok, Venice

## Web Search Feature

The application uses a tiered approach to web search:

1. **SerpAPI Search**: Primary search provider (requires API key)
2. **DuckDuckGo Search**: Fallback search when SerpAPI is unavailable or fails
3. **Built-in Data**: Extensive fallback dataset for popular destinations

All search results are cached to improve performance and reduce API calls.

## Usage Example

```
User: "I'm planning a 5-day trip to Paris in March. I'm interested in art and history, 
       I'm vegetarian, and I prefer moderate hotels." 