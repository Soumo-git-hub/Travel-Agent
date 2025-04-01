import os
import streamlit as st
import requests
import json
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import google.generativeai as genai
from langchain_community.llms import FakeListLLM
import warnings
from langchain_core.callbacks import CallbackManager
from langchain_core.callbacks.base import BaseCallbackHandler
from googlesearch import search
import time
from bs4 import BeautifulSoup
import random

# Set page configuration
st.set_page_config(
    page_title="Travel Agent",
    page_icon="✈️",
    layout="wide"
)

# Custom CSS for loading animation
st.markdown("""
<style>
.loading-dots {
    display: none;  /* Hidden by default */
    color: #2ecc71;  /* Green color */
    font-weight: 500;  /* Medium weight */
    font-size: 1.1em;  /* Slightly larger text */
    padding: 8px 12px;  /* Add padding */
    background-color: rgba(46, 204, 113, 0.1);  /* Light green background */
    border-radius: 4px;  /* Rounded corners */
    margin: 4px 0;  /* Add margin */
    white-space: nowrap;  /* Prevent text wrapping */
}
.loading-dots::after {
    content: '...';
    animation: dots 1.4s infinite;
    display: inline-block;
}
@keyframes dots {
    0%, 20% { content: '.'; }
    40% { content: '..'; }
    60% { content: '...'; }
    80%, 100% { content: ''; }
}
</style>
""", unsafe_allow_html=True)

# Import Streamlit config handler
try:
    from streamlit_config import setup_streamlit_secrets
    # Setup Streamlit secrets if running in cloud
    setup_streamlit_secrets()
except ImportError:
    print("Streamlit config not found, using local .env only")

# Load environment variables
load_dotenv()

# Suppress specific warnings
warnings.filterwarnings("ignore", message=".*TokenCalcHandler.*")
warnings.filterwarnings("ignore", message=".*extra_headers is not default parameter.*")
warnings.filterwarnings("ignore", message=".*The method `BaseTool.__call__` was deprecated.*")

# Update the environment setup section
try:
    # Try getting variables from Streamlit secrets first
    OPENWEATHER_API_KEY = st.secrets["OPENWEATHER_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    LLM_MODE = st.secrets.get("LLM_MODE", "google")
except Exception as e:
    # Fall back to local .env if not in Streamlit Cloud
    load_dotenv()
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    LLM_MODE = os.getenv("LLM_MODE", "google")

# Remove any hardcoded API keys
if not OPENWEATHER_API_KEY:
    st.error("OpenWeather API key not found. Please configure it in your environment.")

if not GEMINI_API_KEY:
    st.error("Gemini API key not found. Please configure it in your environment.")

# Define base URLs and model info
LOCAL_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1")

# Configure Google AI if key is available
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

print(f"Starting in {LLM_MODE} mode...")

# Create a custom callback handler to handle the tokenization errors
class SimpleTokenHandler(BaseCallbackHandler):
    def __init__(self):
        super().__init__()

    def on_llm_start(self, serialized, prompts, **kwargs):
        pass

    def on_llm_end(self, response, **kwargs):
        pass

# Setup LLM
def setup_llm():
    global LLM_MODE
    llm = None
    
    # Create a callback manager with our simple token handler
    callback_manager = CallbackManager([SimpleTokenHandler()])
    
    if LLM_MODE == "google" and GEMINI_API_KEY:
        try:
            # Initialize Gemini model
            model = genai.GenerativeModel('gemini-pro')
            llm = model
            print("Using Google Gemini model")
            return llm
        except Exception as e:
            print(f"Error connecting to Google AI: {str(e)}")
            print("Falling back to local mode...")
            LLM_MODE = "local"
    
    # Try local mode if Google mode failed or was selected initially
    if LLM_MODE == "local":
        try:
            # Try connecting to Ollama
            print("Trying local Ollama...")
            response = requests.get(f"{LOCAL_API_BASE}/models")
            
            if response.status_code == 200:
                models = response.json().get("data", [])
                available_models = [model.get("id") for model in models]
                
                print(f"Available models: {available_models}")
                
                # Check for llama3.2 models first, then llama3, otherwise use first available
                preferred_models = ["llama3.2:8b", "llama3.2:70b", "llama3.2:1b", "llama3.2", "llama3", "mistral", "phi"]
                model_to_use = None
                
                for model in preferred_models:
                    if model in available_models:
                        model_to_use = model
                        break
                
                # If none of the preferred models are available, use the first one
                if not model_to_use and available_models:
                    model_to_use = available_models[0]
                
                if model_to_use:
                    print(f"Using local model: {model_to_use}")
                    llm = ChatOpenAI(
                        openai_api_base=LOCAL_API_BASE,
                        openai_api_key="ollama",  # Ollama doesn't need a real key
                        model=model_to_use,
                        temperature=0.7,
                        callbacks=[SimpleTokenHandler()]
                    )
                else:
                    raise Exception("No models available in Ollama")
            else:
                raise Exception(f"Ollama returned status code {response.status_code}")
        except Exception as e:
            print(f"Error connecting to local LLM: {str(e)}")
            print("WARNING: Using a limited functionality mode due to missing API keys")
            llm = FakeListLLM(responses=["I'm a simple AI assistant without full capabilities right now. Please configure a valid LLM in your settings."])
    
    return llm

# Initialize LLM
llm = setup_llm()

# Define the search function with improved error handling and rate limiting
def search_web(query, num_results=5, timeout=15):
    """Perform a web search and return structured results with improved robustness"""
    if not query or not query.strip():
        return []
        
    try:
        # Perform the search
        search_results = []
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        # Use an improved cache mechanism with expiration
        if "search_cache" not in st.session_state:
            st.session_state.search_cache = {}
        if "search_cache_timestamps" not in st.session_state:
            st.session_state.search_cache_timestamps = {}
        
        # Check cache with expiration (5 minutes)
        cache_key = f"{query}_{num_results}"
        current_time = time.time()
        if cache_key in st.session_state.search_cache:
            cache_age = current_time - st.session_state.search_cache_timestamps.get(cache_key, 0)
            if cache_age < 300:  # 5 minutes expiration
                print("Using cached search result")
                return st.session_state.search_cache[cache_key]
        
        # Perform the search with the correct parameters
        search_urls = list(search(query, num_results=num_results * 2))  # Get more results to filter
        
        for url in search_urls:
            try:
                # Get the webpage content with increased timeout and rotating user agents
                headers = {
                    'User-Agent': random.choice(user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                # Add retry mechanism
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        response = requests.get(url, timeout=timeout, headers=headers)
                        if response.status_code == 200:
                            break
                        elif response.status_code == 429:  # Too Many Requests
                            if retry < max_retries - 1:
                                time.sleep(random.uniform(2, 5))
                                continue
                    except requests.Timeout:
                        if retry < max_retries - 1:
                            time.sleep(random.uniform(1, 3))
                            continue
                        raise
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Get title with improved cleaning
                    title = soup.title.string if soup.title else url
                    title = re.sub(r'\s*\|.*$', '', title)  # Remove website name
                    title = re.sub(r'\s*-\s*.*$', '', title)  # Remove separator and rest
                    title = re.sub(r'\s+', ' ', title).strip()  # Clean up whitespace
                    
                    # Get description with improved extraction
                    description = ""
                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                    if meta_desc:
                        description = meta_desc.get('content', '')
                    else:
                        # Try multiple methods to get description
                        for tag in ['p', 'div']:
                            for element in soup.find_all(tag, class_=lambda x: x and ('description' in x.lower() or 'summary' in x.lower())):
                                description = element.text.strip()
                                if len(description) > 50:  # Ensure meaningful content
                                    break
                            if description:
                                break
                        
                        if not description:
                            # Get first meaningful paragraph
                            for p in soup.find_all('p'):
                                text = p.text.strip()
                                if len(text) > 50 and not any(x in text.lower() for x in ['copyright', 'all rights reserved', 'privacy policy']):
                                    description = text[:200] + "..."
                                    break
                    
                    # Clean up description with improved filtering
                    description = re.sub(r'Visit.*?\.com', '', description, flags=re.IGNORECASE)
                    description = re.sub(r'https?://.*$', '', description)
                    description = re.sub(r'www\..*$', '', description)
                    description = re.sub(r'\s+', ' ', description).strip()
                    
                    # Additional quality checks
                    if (title and description and 
                        len(title) > 5 and 
                        len(description) > 20 and
                        not any(x in url.lower() for x in ['advertisement', 'sponsored', 'promoted'])):
                        search_results.append({
                            'title': title,
                            'url': url,
                            'description': description
                        })
                        
                        if len(search_results) >= num_results:
                            break
                            
            except Exception as e:
                print(f"Error processing URL {url}: {str(e)}")
                continue
            
            # Add a randomized delay to avoid rate limiting
            time.sleep(random.uniform(1.5, 3.0))
        
        # Cache the result with timestamp
        st.session_state.search_cache[cache_key] = search_results
        st.session_state.search_cache_timestamps[cache_key] = current_time
        
        return search_results
    except Exception as e:
        print(f"Error in web search: {str(e)}")
        return []

# Define the search tool
@tool
def search_tool(query: str) -> str:
    """Search the web for travel information"""
    try:
        results = search_web(query)
        if not results:
            return "No search results found."
        
        # Format results in a structured way
        formatted_results = "Here are the relevant search results:\n\n"
        for i, result in enumerate(results, 1):
            formatted_results += f"{i}. {result['title']}\n"
            formatted_results += f"   URL: {result['url']}\n"
            formatted_results += f"   Description: {result['description']}\n\n"
        
        return formatted_results
    except Exception as e:
        return f"Error performing search: {str(e)}"

# Custom tool for weather information with improved error handling
@tool
def get_weather(location):
    """Get detailed weather information for a location with improved robustness."""
    try:
        if not OPENWEATHER_API_KEY:
            return "Weather information is currently unavailable. Please try again later."
            
        # Clean up location name with improved handling
        location = location.replace("In ", "").replace("in ", "")
        location = location.split(' Is A Great Choice')[0].strip()
        location = location.split(' For')[0].strip()
        location = re.sub(r'\s+', ' ', location).strip()
        
        if not location:
            return "Please specify a city name to get weather information."
            
        # Check cache first
        cache_key = f"weather_{location}"
        current_time = time.time()
        
        if "weather_cache" not in st.session_state:
            st.session_state.weather_cache = {}
        if "weather_cache_timestamps" not in st.session_state:
            st.session_state.weather_cache_timestamps = {}
            
        # Check if we have a valid cached result (5 minutes expiration)
        if cache_key in st.session_state.weather_cache:
            cache_age = current_time - st.session_state.weather_cache_timestamps.get(cache_key, 0)
            if cache_age < 300:  # 5 minutes expiration
                return st.session_state.weather_cache[cache_key]
        
        # Try with different country codes and formats
        urls = [
            f"https://api.openweathermap.org/data/2.5/weather?q={location},JP&appid={OPENWEATHER_API_KEY}&units=metric",
            f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHER_API_KEY}&units=metric",
            f"https://api.openweathermap.org/data/2.5/weather?q={location},US&appid={OPENWEATHER_API_KEY}&units=metric",
            f"https://api.openweathermap.org/data/2.5/weather?q={location},GB&appid={OPENWEATHER_API_KEY}&units=metric"
        ]
        
        weather_data = None
        for url in urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    weather_data = response.json()
                    break
                elif response.status_code == 404:
                    continue
                elif response.status_code == 429:  # Rate limit
                    time.sleep(1)  # Wait before trying next URL
            except requests.RequestException:
                continue
        
        if not weather_data:
            return f"Unable to fetch weather data for {location}. Please check if the city name is correct."
        
        # Extract weather information
        weather = {
            "location": weather_data["name"],
            "country": weather_data["sys"]["country"],
            "temperature": round(weather_data["main"]["temp"], 1),
            "feels_like": round(weather_data["main"]["feels_like"], 1),
            "description": weather_data["weather"][0]["description"].capitalize(),
            "humidity": weather_data["main"]["humidity"],
            "wind_speed": round(weather_data["wind"]["speed"], 1),
            "pressure": weather_data["main"]["pressure"],
            "visibility": round(weather_data["visibility"] / 1000, 1),  # Convert to km
            "sunrise": datetime.fromtimestamp(weather_data["sys"]["sunrise"]).strftime("%H:%M"),
            "sunset": datetime.fromtimestamp(weather_data["sys"]["sunset"]).strftime("%H:%M")
        }
        
        # Generate detailed weather report
        weather_report = f"🌤️ Weather Report for {weather['location']}, {weather['country']}\n\n"
        weather_report += f"Current Conditions: {weather['description']}\n"
        weather_report += f"Temperature: {weather['temperature']}°C (feels like {weather['feels_like']}°C)\n"
        weather_report += f"Humidity: {weather['humidity']}%\n"
        weather_report += f"Wind Speed: {weather['wind_speed']} m/s\n"
        weather_report += f"Pressure: {weather['pressure']} hPa\n"
        weather_report += f"Visibility: {weather['visibility']} km\n"
        weather_report += f"Sunrise: {weather['sunrise']}\n"
        weather_report += f"Sunset: {weather['sunset']}\n\n"
        
        # Add weather advice based on conditions
        if weather['temperature'] > 30:
            weather_report += "🌡️ Hot weather alert! Stay hydrated and avoid prolonged sun exposure.\n"
        elif weather['temperature'] < 5:
            weather_report += "❄️ Cold weather alert! Dress warmly and be prepared for chilly conditions.\n"
        
        if weather['humidity'] > 80:
            weather_report += "💧 High humidity! It might feel warmer than the actual temperature.\n"
        
        if weather['wind_speed'] > 10:
            weather_report += "💨 Strong winds! Hold onto your belongings and be careful with umbrellas.\n"
        
        if weather['visibility'] < 5:
            weather_report += "🌫️ Low visibility! Take extra care when traveling.\n"
        
        # Cache the result
        st.session_state.weather_cache[cache_key] = weather_report
        st.session_state.weather_cache_timestamps[cache_key] = current_time
        
        return weather_report
            
    except Exception as e:
        print(f"Weather API error: {str(e)}")
        return f"Error getting weather information for {location}. Please try again later."

# Define the functions that will serve as our lightweight web search
def direct_web_search(query, location=""):
    """
    Perform a direct web search with a simplified approach
    """
    try:
        # Add the destination to make search more specific if provided
        search_query = query
        if location and location.strip():
            if location.lower() not in query.lower():
                search_query = f"{query} {location}"
        
        print(f"Searching for: {search_query}")
        
        # Perform the search
        results = search_web(search_query)
        
        if not results:
            return f"No information found for '{search_query}'. Please try a different search term."
        
        # Format results
        formatted_result = "Here are the relevant search results:\n\n"
        for i, result in enumerate(results, 1):
            formatted_result += f"{i}. {result['title']}\n"
            formatted_result += f"   URL: {result['url']}\n"
            formatted_result += f"   Description: {result['description']}\n\n"
        
        return formatted_result
            
    except Exception as e:
        print(f"Web search error: {str(e)}")
        return f"Error searching for '{query}'. Please try again."

# Improved function to extract travel information from user messages
def extract_info_directly(messages):
    """Extract travel information directly from user messages with improved pattern matching."""
    info = {
        "destination": "",
        "duration": "",
        "budget": "",
        "preferences": [],
        "dietary_preferences": "",
        "accommodation_preferences": "",
        "travel_date": "",
        "accessibility_needs": "",
        "special_interests": []
    }
    
    # Combine all messages into one text
    text = " ".join(messages).lower()
    
    # Extract destination with improved pattern matching
    destination_patterns = [
        r"(?:visit|travel to|going to|planning a trip to|vacation in|holiday in|trip to)\s+([a-zA-Z\s,]+?)(?:\s+for|\s+in|\s+on|\s+during|\.|$)",
        r"(?:visit|travel to|going to|planning a trip to|vacation in|holiday in|trip to)\s+([a-zA-Z\s,]+)",
        r"i want to visit\s+([a-zA-Z\s,]+)",
        r"i would like to visit\s+([a-zA-Z\s,]+)",
        r"i'm planning to visit\s+([a-zA-Z\s,]+)",
        r"i am planning to visit\s+([a-zA-Z\s,]+)"
    ]
    
    for pattern in destination_patterns:
        destination_match = re.search(pattern, text)
        if destination_match:
            # Clean up the destination name
            destination = destination_match.group(1).strip().title()
            # Remove any duplicate words and clean up
            words = destination.split()
            cleaned_words = []
            for word in words:
                if word not in cleaned_words and word.lower() not in ['for', 'is', 'a', 'great', 'choice', 'and', 'the', 'to', 'here', 'are', 'some', 'top', 'attractions', 'i', 'recommend']:
                    cleaned_words.append(word)
            info["destination"] = " ".join(cleaned_words)
            break
    
    # Extract duration with improved pattern matching
    duration_patterns = [
        r'(?:for|planning a|stay for|trip of|vacation of|holiday of)\s+(\d+)\s*(?:day|days|night|nights)',
        r'\b(\d+)\s*(?:day|days|night|nights)\b',
        r'(?:duration|period|length) of\s+(\d+)\s*(?:day|days|night|nights)'
    ]
    
    for pattern in duration_patterns:
        duration_match = re.search(pattern, text)
        if duration_match:
            info["duration"] = f"{duration_match.group(1)} days"
            break
    
    # If no duration is specified, default to 5 days
    if not info["duration"]:
        info["duration"] = "5 days"
    
    # Extract travel date with improved pattern matching
    date_patterns = [
        r'(?:in|during|for)\s+(?:the\s+)?(?:month\s+of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)',
        r'(?:planning for|going in|traveling in)\s+(?:the\s+)?(?:month\s+of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)',
        r'(?:date|when).*?(january|february|march|april|may|june|july|august|september|october|november|december)'
    ]
    
    for pattern in date_patterns:
        date_match = re.search(pattern, text)
        if date_match:
            info["travel_date"] = date_match.group(1).title()
            break
    
    # Extract budget with improved pattern matching
    budget_patterns = {
        "low": ["budget", "cheap", "inexpensive", "affordable", "economical", "low cost", "low-cost", "low budget", "low-budget"],
        "moderate": ["moderate", "medium", "mid-range", "mid range", "average", "reasonable"],
        "high": ["luxury", "expensive", "high-end", "high end", "premium", "deluxe", "upscale"]
    }
    
    for budget_level, keywords in budget_patterns.items():
        if any(keyword in text for keyword in keywords):
            info["budget"] = budget_level
            break
    
    # Extract preferences with improved pattern matching
    preference_patterns = {
        "art": ["art", "museum", "gallery", "exhibition", "painting", "sculpture"],
        "historical": ["history", "historical", "heritage", "ancient", "ruins", "monument", "landmark"],
        "cultural": ["culture", "cultural", "tradition", "traditional", "local customs", "festival"],
        "nature": ["nature", "park", "garden", "outdoor", "hiking", "trekking", "mountain", "beach", "lake", "river", "wildlife"],
        "food": ["food", "restaurant", "cuisine", "gastronomy", "culinary", "dining", "eat", "local food"],
        "adventure": ["adventure", "thrill", "exciting", "adrenaline", "extreme", "sports", "activity"],
        "relaxation": ["relax", "relaxation", "spa", "wellness", "peaceful", "quiet", "calm", "tranquil"],
        "shopping": ["shopping", "shop", "mall", "market", "boutique", "store"],
        "nightlife": ["nightlife", "bar", "club", "pub", "party", "entertainment"],
        "technology": ["technology", "tech", "gadget", "electronics", "innovation", "digital"]
    }
    
    for preference, keywords in preference_patterns.items():
        if any(keyword in text for keyword in keywords):
            if preference not in info["preferences"]:
                info["preferences"].append(preference)
    
    # Extract special interests
    special_interest_patterns = {
        "broadway": ["broadway", "theater", "theatre", "show", "musical", "play"],
        "wine": ["wine", "vineyard", "winery", "wine tasting"],
        "photography": ["photography", "photo", "camera", "picture"],
        "architecture": ["architecture", "building", "design", "structure"],
        "literature": ["literature", "book", "author", "literary", "bookstore"],
        "music": ["music", "concert", "festival", "live music", "band"],
        "sports": ["sports", "game", "match", "stadium", "arena"]
    }
    
    for interest, keywords in special_interest_patterns.items():
        if any(keyword in text for keyword in keywords):
            if interest not in info["special_interests"]:
                info["special_interests"].append(interest)
    
    # Extract dietary preferences
    dietary_patterns = {
        "vegetarian": ["vegetarian", "no meat", "without meat"],
        "vegan": ["vegan", "plant-based", "plant based", "no animal products"],
        "gluten-free": ["gluten-free", "gluten free", "no gluten"],
        "halal": ["halal"],
        "kosher": ["kosher"]
    }
    
    for diet, keywords in dietary_patterns.items():
        if any(keyword in text for keyword in keywords):
            info["dietary_preferences"] = diet
            break
    
    # Extract accommodation preferences
    accommodation_patterns = {
        "luxury": ["luxury hotel", "5 star", "five star", "high-end hotel", "premium accommodation"],
        "budget": ["budget hotel", "cheap hotel", "hostel", "affordable accommodation", "low-cost hotel"],
        "moderate": ["moderate hotel", "mid-range hotel", "3 star", "three star", "standard hotel"],
        "apartment": ["apartment", "airbnb", "rental", "flat"],
        "resort": ["resort", "all-inclusive", "spa resort"]
    }
    
    for accommodation, keywords in accommodation_patterns.items():
        if any(keyword in text for keyword in keywords):
            info["accommodation_preferences"] = accommodation
            break
    
    # Extract accessibility needs
    if any(word in text for word in ["wheelchair", "accessible", "disability", "mobility", "handicap"]):
        info["accessibility_needs"] = "wheelchair"
    
    return info

# Improved function to search for attractions
def search_attractions(destination, preferences=""):
    """Search for attractions based on destination and preferences with improved filtering."""
    try:
        if not destination or not destination.strip():
            return ["Please specify a destination to search for attractions."]
            
        print(f"Searching for attractions in {destination} with preferences: {preferences}")
        
        # Build query based on preferences
        query = f"Top tourist attractions in {destination}, Japan"
        if preferences:
            preference_list = [p.strip() for p in preferences.split(',')]
            if len(preference_list) == 1:
                query = f"Top {preference_list[0]} attractions in {destination}, Japan"
            else:
                preference_str = " and ".join(preference_list)
                query = f"Top {preference_str} attractions in {destination}, Japan"
        
        # Perform the search
        print(f"Searching with query: {query}")
        results = search_web(query)
        
        if not results:
            return [f"No attraction data available for {destination}. Please try a different search query."]
        
        # Format results with improved filtering
        formatted_attractions = []
        excluded_terms = ['restaurant', 'hotel', 'accommodation', 'booking', 'tripadvisor', 'expedia', 'top 10', 'best']
        
        for result in results:
            if not result or not isinstance(result, dict):
                continue
                
            title = result.get('title', '').strip()
            description = result.get('description', '').strip()
            
            # Skip results that are likely not attractions or are from wrong location
            if any(term in title.lower() for term in excluded_terms) or 'delhi' in title.lower():
                continue
                
            if title and description and len(title) > 5:
                # Clean up the title and description
                title = re.sub(r'\s*\|.*$', '', title)
                title = re.sub(r'\s*-\s*.*$', '', title)
                
                formatted_attraction = f"{title} - {description}"
                formatted_attractions.append(formatted_attraction)
        
        if formatted_attractions:
            return formatted_attractions
        else:
            # Return default Tokyo attractions if no search results
            return [
                "Senso-ji Temple - Ancient Buddhist temple in Asakusa, Tokyo's oldest temple",
                "Tokyo Skytree - Tallest structure in Japan with observation decks",
                "Shibuya Crossing - Famous pedestrian crossing and entertainment area",
                "Meiji Shrine - Shinto shrine dedicated to Emperor Meiji",
                "Tsukiji Outer Market - Famous fish market with fresh seafood and local food"
            ]
    
    except Exception as e:
        print(f"Error in search_attractions: {e}")
        return ["Error searching for attractions. Please try again."]

# Improved function to search for restaurants
def search_restaurants(destination, dietary_preferences=""):
    """Search for restaurants based on destination and dietary preferences with improved filtering."""
    try:
        if not destination or not destination.strip():
            return ["Please specify a destination to search for restaurants."]
            
        print(f"Searching for restaurants in {destination} with preferences: {dietary_preferences}")
        
        # Build query based on preferences
        query = f"Best restaurants in {destination}, Japan"
        if dietary_preferences:
            query = f"Best {dietary_preferences} restaurants in {destination}, Japan"
        
        # Perform the search
        print(f"Searching with query: {query}")
        results = search_web(query)
        
        if not results:
            return [f"No restaurant data available for {destination}. Please try a different search query."]
        
        # Format results with improved filtering
        formatted_restaurants = []
        restaurant_keywords = ['restaurant', 'café', 'cafe', 'bistro', 'eatery', 'dining', 'food']
        
        for result in results:
            if not result or not isinstance(result, dict):
                continue
                
            title = result.get('title', '').strip()
            description = result.get('description', '').strip()
            
            # Check if this is likely a restaurant and in the correct location
            is_restaurant = any(keyword in title.lower() or keyword in description.lower() for keyword in restaurant_keywords)
            is_correct_location = 'tokyo' in title.lower() or 'japan' in title.lower()
            
            if title and description and len(title) > 5 and is_restaurant and is_correct_location:
                # Clean up the title and description
                title = re.sub(r'\s*\|.*$', '', title)
                title = re.sub(r'\s*-\s*.*$', '', title)
                
                formatted_restaurant = f"{title} - {description}"
                formatted_restaurants.append(formatted_restaurant)
        
        if formatted_restaurants:
            return formatted_restaurants
        else:
            # Return default Tokyo restaurants if no search results
            return [
                "Sukiyabashi Jiro - World-famous sushi restaurant in Ginza",
                "Tsukiji Tama Sushi - Fresh sushi in Tsukiji market area",
                "Ichiran Ramen - Popular ramen chain with private booths",
                "Gonpachi Nishiazabu - Traditional Japanese restaurant",
                "Robot Restaurant - Unique dining experience in Shinjuku"
            ]
    
    except Exception as e:
        print(f"Error in search_restaurants: {e}")
        return ["Error searching for restaurants. Please try again."]

# Improved function to search for accommodations
def search_accommodations(destination, preference="moderate"):
    """Search for accommodations based on destination and preference with improved filtering."""
    try:
        # Clean up destination name
        destination = destination.split(' Is A Great Choice')[0].strip()
        destination = destination.split(' For')[0].strip()
        
        if not destination:
            return ["Please specify a destination to search for hotels."]
            
        print(f"Searching for accommodations in {destination} with preference: {preference}")
        
        # Build query based on preferences
        query = f"Best hotels in {destination}"
        if preference.lower() != "any":
            if "low" in preference.lower() or "budget" in preference.lower():
                query = f"Best budget hotels in {destination}"
            elif "moderate" in preference.lower() or "mid" in preference.lower():
                query = f"Best mid-range hotels in {destination}"
            elif "high" in preference.lower() or "luxury" in preference.lower():
                query = f"Best luxury hotels in {destination}"
            elif "apartment" in preference.lower():
                query = f"Best apartments or vacation rentals in {destination}"
            elif "resort" in preference.lower():
                query = f"Best resorts in {destination}"
            else:
                query = f"Best {preference} hotels in {destination}"
        
        # Perform the search
        print(f"Searching with query: {query}")
        results = search_web(query)
        
        if not results:
            # Try a simpler search if the first one didn't work
            simple_query = f"hotels in {destination}"
            print(f"Trying simpler search: {simple_query}")
            results = search_web(simple_query)
        
        if not results:
            return [f"No hotel data available for {destination}. Please try a different search query."]
        
        # Format results with improved filtering
        formatted_accommodations = []
        accommodation_keywords = ['hotel', 'inn', 'resort', 'lodge', 'accommodation', 'stay', 'apartment', 'rental']
        excluded_terms = ['booking.com', 'tripadvisor', 'expedia', 'hotels.com', 'agoda', 'best hotels', 'top hotels']
        
        for result in results:
            if not result or not isinstance(result, dict):
                continue
                
            # Clean up the title and description
            title = result.get('title', '').split(' - ')[0].strip()
            # Remove website names and extra information
            title = re.sub(r'\s*\|.*$', '', title)
            title = re.sub(r'\s*-\s*.*$', '', title)
            title = re.sub(r'\s*\d{4}.*$', '', title)
            
            description = result.get('description', '').split('.')[0].strip()  # Take first sentence only
            
            # Check if this is likely an accommodation
            is_accommodation = any(keyword in title.lower() or keyword in description.lower() for keyword in accommodation_keywords)
            is_excluded = any(term in title.lower() or term in description.lower() for term in excluded_terms)
            
            if title and description and len(title) > 5 and is_accommodation and not is_excluded:
                formatted_accommodation = f"{title} - {description}"
                formatted_accommodations.append(formatted_accommodation)
        
        if formatted_accommodations:
            return formatted_accommodations
        else:
            return [f"No specific hotel information found for {destination}. Here are some general recommendations:\n" +
                   "- Consider staying in the city center for easy access to attractions\n" +
                   "- Look for hotels near metro stations for convenient transportation\n" +
                   "- Check for hotels with good reviews on major booking platforms\n" +
                   "- Consider boutique hotels for a more authentic experience"]
    
    except Exception as e:
        print(f"Error in search_accommodations: {e}")
        return [f"Error searching for hotels in {destination}. Here are some general recommendations:\n" +
                "- Consider staying in the city center for easy access to attractions\n" +
                "- Look for hotels near metro stations for convenient transportation\n" +
                "- Check for hotels with good reviews on major booking platforms\n" +
                "- Consider boutique hotels for a more authentic experience"]

# Function to search for accessible attractions
def search_accessible_attractions(destination):
    """Search for wheelchair accessible attractions in a destination."""
    try:
        if not destination or not destination.strip():
            return ["Please specify a destination to search for accessible attractions."]
            
        print(f"Searching for accessible attractions in {destination}")
        
        # Build query for accessible attractions
        query = f"Wheelchair accessible attractions in {destination}"
        
        # Perform the search
        results = search_web(query)
        
        if not results:
            # Try a more general search if the first one didn't work
            query = f"Accessible tourism {destination}"
            results = search_web(query)
        
        if not results:
            return [f"No specific accessibility information found for {destination}. Here are some general recommendations:\n" +
                   "- Contact attractions directly to inquire about accessibility features\n" +
                   "- Look for attractions with 'accessible' or 'wheelchair friendly' labels\n" +
                   "- Consider museums and modern attractions which typically have better accessibility\n" +
                   "- Check if the city has an accessibility guide for tourists"]
        
        # Format results
        formatted_attractions = []
        for result in results:
            if not result or not isinstance(result, dict):
                continue
                
            title = result.get('title', '').strip()
            description = result.get('description', '').strip()
            
            if title and description and len(title) > 5:
                # Clean up the title and description
                title = re.sub(r'\s*\|.*$', '', title)
                title = re.sub(r'\s*-\s*.*$', '', title)
                
                formatted_attraction = f"{title} - {description}"
                formatted_attractions.append(formatted_attraction)
        
        if formatted_attractions:
            return formatted_attractions
        else:
            return [f"No specific accessibility information found for {destination}. Here are some general recommendations:\n" +
                   "- Contact attractions directly to inquire about accessibility features\n" +
                   "- Look for attractions with 'accessible' or 'wheelchair friendly' labels\n" +
                   "- Consider museums and modern attractions which typically have better accessibility\n" +
                   "- Check if the city has an accessibility guide for tourists"]
    
    except Exception as e:
        print(f"Error in search_accessible_attractions: {e}")
        return ["Error searching for accessible attractions. Please try again."]

# Function to search for special interest activities
def search_special_interest(destination, interest):
    """Search for activities related to a special interest in a destination."""
    try:
        if not destination or not destination.strip():
            return ["Please specify a destination to search for activities."]
            
        if not interest or not interest.strip():
            return ["Please specify an interest to search for activities."]
            
        print(f"Searching for {interest} activities in {destination}")
        
        # Build query based on interest
        query = f"Best {interest} experiences in {destination}"
        
        # Perform the search
        results = search_web(query)
        
        if not results:
            return [f"No specific {interest} information found for {destination}. Please try a different search term."]
        
        # Format results
        formatted_activities = []
        for result in results:
            if not result or not isinstance(result, dict):
                continue
                
            title = result.get('title', '').strip()
            description = result.get('description', '').strip()
            
            if title and description and len(title) > 5:
                # Clean up the title and description
                title = re.sub(r'\s*\|.*$', '', title)
                title = re.sub(r'\s*-\s*.*$', '', title)
                
                formatted_activity = f"{title} - {description}"
                formatted_activities.append(formatted_activity)
        
        if formatted_activities:
            return formatted_activities
        else:
            return [f"No specific {interest} information found for {destination}. Please try a different search term."]
    
    except Exception as e:
        print(f"Error in search_special_interest: {e}")
        return [f"Error searching for {interest} activities in {destination}. Please try again."]

# Improved function to generate travel recommendations
def generate_recommendations():
    """Generate detailed travel recommendations with specific attractions and activities."""
    try:
        destination = st.session_state.travel_info.get('destination', '')
        duration = st.session_state.travel_info.get('duration', '')
        budget = st.session_state.travel_info.get('budget', 'moderate')
        preferences = st.session_state.travel_info.get('preferences', [])
        
        if not destination or not duration:
            return "I need more information about your destination and travel duration to generate recommendations."
        
        # Clean up destination name for weather API
        clean_destination = destination.split(' Here')[0].strip()
        
        # Get weather information
        weather_info = get_weather(clean_destination)
        
        # Start building the itinerary
        itinerary = f"# Your {duration} Itinerary for {destination}\n\n"
        itinerary += f"## Current Weather\n{weather_info}\n\n"
        itinerary += f"## Budget Level\n{budget.capitalize()}\n\n"
        
        if preferences:
            itinerary += "## Your Interests\n" + ", ".join(preferences) + "\n\n"
        
        # Get specific attractions based on preferences
        attractions = search_attractions(destination, preferences[0] if preferences else "")
        restaurants = search_restaurants(destination)
        
        # Create day-by-day itinerary
        itinerary += "## Day-by-Day Itinerary\n"
        
        # Define different types of activities for variety based on preferences
        morning_activities = {
            "food": [
                "Visit Tsukiji Outer Market for fresh seafood and local breakfast",
                "Start your day with a traditional Japanese breakfast at a local café",
                "Explore the food stalls at Ameyoko Market",
                "Visit a local bakery for fresh Japanese pastries",
                "Take a food tour in Asakusa"
            ],
            "culture": [
                "Visit Senso-ji Temple in Asakusa",
                "Explore Meiji Shrine and its peaceful gardens",
                "Visit the Imperial Palace East Gardens",
                "Take a traditional tea ceremony class",
                "Visit a local shrine for morning prayers"
            ],
            "technology": [
                "Visit the Miraikan Science Museum",
                "Explore the Sony ExploraScience Museum",
                "Visit the Panasonic Center Tokyo",
                "Check out the latest gadgets at Bic Camera",
                "Visit the Gundam Base Tokyo"
            ]
        }
        
        afternoon_activities = {
            "food": [
                "Take a sushi-making class",
                "Visit a sake brewery for tasting",
                "Explore the food halls at department stores",
                "Take a ramen tour in different neighborhoods",
                "Visit a wagyu beef restaurant"
            ],
            "culture": [
                "Visit the Tokyo National Museum",
                "Explore the Edo-Tokyo Museum",
                "Visit a traditional Japanese garden",
                "Take a calligraphy class",
                "Visit a local art gallery"
            ],
            "technology": [
                "Visit Akihabara Electric Town",
                "Explore the Digital Art Museum",
                "Visit the National Museum of Emerging Science",
                "Check out the latest tech at Yodobashi Camera",
                "Visit the Ghibli Museum"
            ]
        }
        
        evening_activities = {
            "food": [
                "Dine at a traditional izakaya",
                "Try street food at a night market",
                "Visit a themed restaurant",
                "Take a food tour in Shibuya",
                "Dine at a robot restaurant"
            ],
            "culture": [
                "Watch a traditional performance",
                "Visit a local festival",
                "Take a night walk in a historic district",
                "Visit a local bar in Golden Gai",
                "Watch a sumo match"
            ],
            "technology": [
                "Visit the teamLab Borderless Museum",
                "Explore the nightlife in Odaiba",
                "Visit a gaming arcade",
                "Take a night photography tour",
                "Visit a VR gaming center"
            ]
        }
        
        # Generate unique itinerary for each day
        for day in range(1, int(duration.split()[0]) + 1):
            itinerary += f"\n### Day {day}\n"
            
            # Morning
            itinerary += "**Morning:**\n"
            if preferences:
                # Select activities based on preferences
                for preference in preferences:
                    if preference in morning_activities:
                        activity = random.choice(morning_activities[preference])
                        itinerary += f"- {activity}\n"
                        break
            else:
                itinerary += "- Start your day with a visit to a local café\n"
            
            # Afternoon
            itinerary += "\n**Afternoon:**\n"
            if preferences:
                # Select activities based on preferences
                for preference in preferences:
                    if preference in afternoon_activities:
                        activity = random.choice(afternoon_activities[preference])
                        itinerary += f"- {activity}\n"
                        break
            else:
                itinerary += "- Visit a local museum or art gallery\n"
            
            # Evening
            itinerary += "\n**Evening:**\n"
            if preferences:
                # Select activities based on preferences
                for preference in preferences:
                    if preference in evening_activities:
                        activity = random.choice(evening_activities[preference])
                        itinerary += f"- {activity}\n"
                        break
            else:
                itinerary += "- Enjoy dinner at a local restaurant\n"
        
        # Add specific recommendations
        itinerary += "\n## Additional Recommendations\n"
        
        # Key Attractions
        itinerary += "\n### Key Attractions\n"
        if attractions:
            for i, attraction in enumerate(attractions[:5], 1):
                itinerary += f"{i}. {attraction}\n"
        
        # Recommended Restaurants
        itinerary += "\n### Recommended Restaurants\n"
        if restaurants:
            for i, restaurant in enumerate(restaurants[:5], 1):
                itinerary += f"{i}. {restaurant}\n"
        
        # Accommodation Options
        itinerary += "\n### Accommodation Options\n"
        budget_levels = {
            "low": "Budget hotels and hostels in areas like Asakusa or Ueno",
            "moderate": "Mid-range hotels in Shibuya, Shinjuku, or Ginza",
            "high": "Luxury hotels in Roppongi, Marunouchi, or the Tokyo Station area"
        }
        itinerary += budget_levels.get(budget, budget_levels["moderate"]) + "\n"
        
        # Transportation Tips
        itinerary += "\n### Transportation Tips\n"
        itinerary += "- Purchase a Suica or Pasmo card for convenient public transport\n"
        itinerary += "- Consider getting a JR Pass if planning day trips\n"
        itinerary += "- Use the efficient subway system for city travel\n"
        itinerary += "- Download the Tokyo Subway Navigation app\n"
        itinerary += "- Keep your transport card topped up\n"
        
        # Add budget breakdown with more realistic estimates for Tokyo
        itinerary += "\n### Estimated Budget Breakdown\n"
        
        # Calculate rough budget estimates based on budget level and destination
        budget_multipliers = {"low": 0.7, "moderate": 1.0, "high": 1.5}
        multiplier = budget_multipliers.get(budget, 1.0)
        
        # Base costs adjusted for Tokyo
        accommodation_cost = 200 * multiplier  # per night
        food_cost = 100 * multiplier  # per day
        activities_cost = 50 * multiplier  # per day
        transport_cost = 30 * multiplier  # per day
        
        total_accommodation = accommodation_cost * int(duration.split()[0])
        total_food = food_cost * int(duration.split()[0])
        total_activities = activities_cost * int(duration.split()[0])
        total_transport = transport_cost * int(duration.split()[0])
        total_cost = total_accommodation + total_food + total_activities + total_transport
        
        itinerary += f"- Accommodation: ${total_accommodation:.0f}\n"
        itinerary += f"- Food: ${total_food:.0f}\n"
        itinerary += f"- Activities: ${total_activities:.0f}\n"
        itinerary += f"- Transportation: ${total_transport:.0f}\n"
        itinerary += f"- Total: Approximately ${total_cost:.0f}\n"
        
        # Add money-saving tips
        itinerary += "\n### Money-Saving Tips\n"
        itinerary += "- Look for free walking tours and attractions\n"
        itinerary += "- Use public transportation instead of taxis\n"
        itinerary += "- Eat at local markets and street food vendors\n"
        itinerary += "- Consider staying in hostels or budget hotels\n"
        itinerary += "- Look for city passes that include multiple attractions\n"
        itinerary += "- Visit temples and shrines (many are free)\n"
        itinerary += "- Take advantage of happy hours at restaurants\n"
        itinerary += "- Use convenience stores for snacks and basic meals\n"
        
        # Add practical tips
        itinerary += "\n### Practical Tips\n"
        itinerary += "- Keep a copy of your passport and important documents\n"
        itinerary += "- Learn basic Japanese phrases\n"
        itinerary += "- Download offline maps and translation apps\n"
        itinerary += "- Keep emergency contact numbers handy\n"
        itinerary += "- Follow local customs and dress codes\n"
        itinerary += "- Carry cash (many places don't accept cards)\n"
        itinerary += "- Get travel insurance\n"
        itinerary += "- Keep your hotel address in Japanese\n"
        
        return itinerary
        
    except Exception as e:
        print(f"Error generating recommendations: {str(e)}")
        return "I apologize, but I encountered an error while generating your travel recommendations. Please try again."

# Improved function to generate conversational responses
def generate_conversational_response(user_input, travel_info, itinerary_generated=False):
    """Generate a more natural conversational response based on user input and travel context with improved context handling."""
    destination = travel_info.get('destination', '')
    user_input_lower = user_input.lower()
    
    # Different greeting variants with more personality
    greetings = [
        "Hi there! I'm your AI travel companion, ready to help plan your perfect adventure!",
        "Hello! I'm excited to help you create an unforgettable journey.",
        "Welcome! I'm here to make your travel planning smooth and enjoyable.",
        "Greetings! Let's plan an amazing journey together!",
        "Hi! I'm your personal travel assistant, ready to help you explore the world!"
    ]
    
    # If this is a new conversation and we don't have destination yet
    if not destination and ("hi" in user_input_lower or "hello" in user_input_lower or len(user_input_lower) < 20):
        return random.choice(greetings) + " Where would you like to travel to?"
    
    # If we have all the necessary information, generate itinerary
    if (destination and 
        travel_info.get('duration') and 
        not itinerary_generated and 
        len(user_input_lower.split()) > 10):  # More detailed message
        
        # Generate the itinerary with improved context
        itinerary = generate_recommendations()
        st.session_state.itinerary = itinerary
        
        return "I've crafted a personalized itinerary for your trip! You can find it above. Would you like to:\n\n" + \
               "1. Get more details about any specific day or activity\n" + \
               "2. Learn about local transportation options\n" + \
               "3. Find restaurant recommendations\n" + \
               "4. Get weather information for your travel dates\n" + \
               "5. Learn about local customs and etiquette"
    
    # If user just provided their destination
    if destination and ("visit" in user_input_lower or "travel to" in user_input_lower or "going to" in user_input_lower):
        # Get initial weather info for the destination
        weather_info = get_weather(destination)
        
        return f"Great choice! {destination} is an exciting destination. {weather_info}\n\n" + \
               "To help me create the perfect itinerary, could you tell me:\n\n" + \
               "1. How many days are you planning to stay?\n" + \
               "2. What's your budget level (low, moderate, or high)?\n" + \
               "3. What interests you most about this destination? (e.g., food, culture, history, nature)\n" + \
               "4. Are you traveling with any specific requirements? (e.g., accessibility needs, dietary restrictions)"
    
    # If user provided destination but no duration
    if destination and not travel_info.get('duration') and not "day" in user_input_lower:
        return f"Perfect! {destination} has so much to offer. To create a personalized itinerary, I need to know:\n\n" + \
               "1. How many days are you planning to stay?\n" + \
               "2. What's your budget level (low, moderate, or high)?\n" + \
               "3. What interests you most about this destination?\n" + \
               "4. Are you traveling with any specific requirements?"
    
    # If user provided destination and duration but no preferences
    if destination and travel_info.get('duration') and not travel_info.get('preferences') and not itinerary_generated:
        return f"I'll help you plan your {travel_info.get('duration')} trip to {destination}. To create a personalized itinerary, could you share some of your interests or preferences? For example:\n\n" + \
               "- Are you interested in history, art, or culture?\n" + \
               "- Do you enjoy food experiences and trying local cuisine?\n" + \
               "- Are you interested in nature, shopping, or nightlife?\n" + \
               "- Do you have any dietary preferences or restrictions?\n" + \
               "- Are there any specific attractions you'd like to visit?\n" + \
               "- Do you prefer a relaxed pace or a more active itinerary?"
    
    # Handle follow-up questions about specific topics after itinerary was generated
    if itinerary_generated:
        if "transport" in user_input_lower or "getting around" in user_input_lower:
            return f"Getting around {destination} is straightforward. Here are some transportation tips:\n\n" + \
                   "- Public transportation is usually the most efficient option\n" + \
                   "- Consider purchasing a multi-day pass for convenience\n" + \
                   "- Download local transportation apps before your trip\n" + \
                   "- Keep some cash handy for taxis or smaller transit options\n" + \
                   "- Research peak hours to avoid crowds\n" + \
                   "- Consider ride-sharing services for flexibility\n\n" + \
                   "Would you like more specific information about transportation options?"
        elif "safety" in user_input_lower or "safe" in user_input_lower:
            return f"{destination} is generally safe for tourists, but here are some important safety tips:\n\n" + \
                   "- Keep your belongings secure and be aware of your surroundings\n" + \
                   "- Avoid isolated areas at night\n" + \
                   "- Keep emergency contact numbers handy\n" + \
                   "- Make copies of important documents\n" + \
                   "- Follow local customs and dress codes\n" + \
                   "- Stay hydrated and protect yourself from the sun\n" + \
                   "- Be cautious with street food and water\n" + \
                   "- Keep your hotel address with you at all times"
        elif "weather" in user_input_lower or "climate" in user_input_lower:
            return None  # Let the existing weather function handle this
        elif "currency" in user_input_lower or "money" in user_input_lower:
            return f"Here's what you need to know about money in {destination}:\n\n" + \
                   "- Check the local currency and current exchange rates\n" + \
                   "- Major credit cards are widely accepted in most tourist areas\n" + \
                   "- Keep some local currency for small purchases\n" + \
                   "- ATMs are usually the best way to get local currency\n" + \
                   "- Inform your bank about your travel dates\n" + \
                   "- Consider using a travel-friendly credit card\n" + \
                   "- Keep emergency cash in a separate location\n" + \
                   "- Be aware of common tourist scams"
        elif "language" in user_input_lower or "speak" in user_input_lower:
            return f"Language tips for {destination}:\n\n" + \
                   "- Learn a few basic phrases in the local language\n" + \
                   "- Download a translation app for offline use\n" + \
                   "- English is widely spoken in tourist areas\n" + \
                   "- Keep a phrasebook or digital dictionary handy\n" + \
                   "- Even simple greetings in the local language are appreciated\n" + \
                   "- Consider taking a basic language class before your trip\n" + \
                   "- Use hand gestures and body language when needed\n" + \
                   "- Learn numbers and basic directions"
        elif "budget" in user_input_lower or "cost" in user_input_lower or "expensive" in user_input_lower:
            budget_level = travel_info.get('budget', 'moderate')
            if budget_level == "low":
                return f"Here are some budget-friendly tips for {destination}:\n\n" + \
                       "- Stay in hostels or budget hotels\n" + \
                       "- Use public transportation\n" + \
                       "- Eat at local markets and street food vendors\n" + \
                       "- Take advantage of free attractions and walking tours\n" + \
                       "- Look for student discounts if applicable\n" + \
                       "- Visit during off-peak seasons\n" + \
                       "- Book accommodations in advance\n" + \
                       "- Use free walking tour apps"
            elif budget_level == "high":
                return f"{destination} offers many luxury experiences:\n\n" + \
                       "- 5-star hotels and luxury accommodations\n" + \
                       "- Fine dining restaurants\n" + \
                       "- Private tours and exclusive experiences\n" + \
                       "- High-end shopping opportunities\n" + \
                       "- Premium transportation options\n" + \
                       "- VIP access to attractions\n" + \
                       "- Luxury spa treatments\n" + \
                       "- Private guides and concierge services"
            else:
                return f"With a moderate budget in {destination}, you can:\n\n" + \
                       "- Stay in comfortable mid-range hotels\n" + \
                       "- Mix local eateries with some upscale restaurants\n" + \
                       "- Experience most attractions without breaking the bank\n" + \
                       "- Use a combination of public transport and occasional taxis\n" + \
                       "- Find good value in guided tours and activities\n" + \
                       "- Visit popular attractions during off-peak hours\n" + \
                       "- Look for combo tickets and passes\n" + \
                       "- Stay in central locations for convenience"
    
    # If user asks a vague question about where to go
    if any(phrase in user_input_lower for phrase in ["where should i go", "recommend a place", "good place to visit", "somewhere nice", "vacation ideas"]):
        return "I'd be happy to help you plan a vacation! To provide personalized recommendations, I need some information:\n\n" + \
               "1. What type of destination interests you?\n" + \
               "   - Beach destination\n" + \
               "   - City with cultural experiences\n" + \
               "   - Mountain retreat\n" + \
               "   - Historical sites\n" + \
               "   - Adventure destination\n" + \
               "   - Foodie paradise\n" + \
               "   - Shopping destination\n" + \
               "   - Nature and wildlife\n\n" + \
               "2. How long are you planning to travel?\n\n" + \
               "3. What's your budget level (low, moderate, or high)?\n\n" + \
               "4. Any specific interests or requirements?\n" + \
               "   - Food experiences\n" + \
               "   - Art and culture\n" + \
               "   - Outdoor activities\n" + \
               "   - Shopping\n" + \
               "   - Nightlife\n" + \
               "   - Family-friendly activities\n" + \
               "   - Accessibility needs\n" + \
               "   - Language preferences"
    
    # If user mentions special requirements like accessibility
    if "wheelchair" in user_input_lower or "accessible" in user_input_lower or "disability" in user_input_lower:
        if destination:
            return f"I'll help you plan an accessible trip to {destination}. Here's what you should know:\n\n" + \
                   "- Many attractions have wheelchair access and facilities\n" + \
                   "- Public transportation often has accessibility features\n" + \
                   "- Hotels offer accessible rooms\n" + \
                   "- Many restaurants are wheelchair-friendly\n" + \
                   "- Look for accessible tour operators\n" + \
                   "- Check for accessible parking options\n" + \
                   "- Research medical facilities and pharmacies\n" + \
                   "- Consider hiring local assistance if needed\n\n" + \
                   "Would you like me to focus on accessible attractions and transportation options in your itinerary?"
        else:
            return "I can help you plan an accessible trip. Many destinations have improved their accessibility features in recent years. To provide the best recommendations, could you tell me:\n\n" + \
                   "1. Where would you like to travel to?\n" + \
                   "2. How long are you planning to stay?\n" + \
                   "3. What's your budget level?\n" + \
                   "4. What interests you most about the destination?\n" + \
                   "5. Any specific accessibility requirements?"
    
    # If user mentions dietary restrictions
    if any(diet in user_input_lower for diet in ["vegetarian", "vegan", "gluten-free", "food allergy", "dietary"]):
        if destination:
            return f"I'll make sure to include {travel_info.get('dietary_preferences', 'dietary-friendly')} restaurant recommendations for your trip to {destination}. Here's what you should know:\n\n" + \
                   "- Many restaurants now offer good options for various dietary needs\n" + \
                   "- Local markets often have fresh, suitable ingredients\n" + \
                   "- Some areas may have dedicated dietary-friendly restaurants\n" + \
                   "- It's helpful to learn how to communicate your dietary needs in the local language\n" + \
                   "- Research common ingredients in local cuisine\n" + \
                   "- Look for specialty food stores\n" + \
                   "- Consider downloading dietary translation apps\n" + \
                   "- Keep emergency snacks handy\n\n" + \
                   "Would you like me to create an itinerary with a focus on suitable dining options?"
        else:
            return "I can help you find destinations with great options for your dietary preferences. To provide the best recommendations, could you tell me:\n\n" + \
                   "1. Where would you like to travel to?\n" + \
                   "2. How long are you planning to stay?\n" + \
                   "3. What's your budget level?\n" + \
                   "4. What interests you most about the destination?\n" + \
                   "5. Any specific dietary requirements?"
    
    # Handle follow-up questions about specific interests
    if any(word in user_input_lower for word in ["more", "tell me more", "what else", "other", "another"]):
        if destination:
            # Get additional recommendations based on existing preferences
            preferences = travel_info.get('preferences', [])
            if preferences:
                response = f"Here are more recommendations for {destination} based on your interests:\n\n"
                for preference in preferences:
                    if preference == "food":
                        restaurants = search_restaurants(destination, travel_info.get('dietary_preferences', ''))
                        response += "**Additional Food Experiences:**\n"
                        for restaurant in restaurants[3:6]:  # Get next 3 restaurants
                            response += f"- {restaurant}\n"
                        response += "\n"
                    elif preference == "technology":
                        tech_attractions = search_special_interest(destination, "technology")
                        response += "**More Technology Spots:**\n"
                        for attraction in tech_attractions[3:6]:
                            response += f"- {attraction}\n"
                        response += "\n"
                    elif preference == "art":
                        art_attractions = search_attractions(destination, "art")
                        response += "**Additional Art & Museums:**\n"
                        for attraction in art_attractions[3:6]:
                            response += f"- {attraction}\n"
                        response += "\n"
                    elif preference == "culture":
                        cultural_attractions = search_attractions(destination, "cultural")
                        response += "**More Cultural Experiences:**\n"
                        for attraction in cultural_attractions[3:6]:
                            response += f"- {attraction}\n"
                        response += "\n"
                response += "\nWould you like to know more about any specific aspect of your trip?"
                return response
    
    return None  # Return None if no conversational response is generated

# Improved function to generate responses
def generate_response(prompt, travel_info):
    """Generate a response based on user input and travel information with improved handling."""
    try:
        # Clean up destination name
        destination = travel_info.get('destination', '').split(' For')[0].strip()
        user_input_lower = prompt.lower()
        
        # Handle beach destination queries
        if "beach" in user_input_lower or "beaches" in user_input_lower:
            if not destination:
                # Suggest popular beach destinations
                return "Here are some great beach destinations for your vacation:\n\n" + \
                       "1. **Bali, Indonesia**\n" + \
                       "   - Beautiful beaches, rich culture, and excellent food\n" + \
                       "   - Perfect for a week-long stay\n" + \
                       "   - Moderate budget options available\n\n" + \
                       "2. **Phuket, Thailand**\n" + \
                       "   - Stunning beaches, vibrant nightlife, and delicious cuisine\n" + \
                       "   - Great value for money\n" + \
                       "   - Easy to reach from major cities\n\n" + \
                       "3. **Barcelona, Spain**\n" + \
                       "   - City beaches with Mediterranean charm\n" + \
                       "   - Excellent food scene and cultural attractions\n" + \
                       "   - Perfect for combining beach and city experiences\n\n" + \
                       "4. **Cancun, Mexico**\n" + \
                       "   - Caribbean beaches with crystal clear waters\n" + \
                       "   - Rich Mayan culture and delicious Mexican cuisine\n" + \
                       "   - All-inclusive options available\n\n" + \
                       "5. **Gold Coast, Australia**\n" + \
                       "   - Long stretches of beautiful beaches\n" + \
                       "   - Great food scene and outdoor activities\n" + \
                       "   - Family-friendly options\n\n" + \
                       "Would you like more information about any of these destinations? Or would you prefer to explore other beach destinations?"
            else:
                # Search for beach attractions in the specified destination
                beach_attractions = search_attractions(destination, "beach")
                if beach_attractions:
                    return f"Here are some great beach experiences in {destination}:\n\n" + \
                           "\n".join([f"- {attraction}" for attraction in beach_attractions[:5]]) + \
                           "\n\nWould you like to know more about beach activities, water sports, or beachfront accommodations?"
                else:
                    return f"While {destination} might not be known for its beaches, I can help you find other attractions and activities. Would you like to explore:\n\n" + \
                           "1. Cultural attractions\n" + \
                           "2. Food experiences\n" + \
                           "3. Outdoor activities\n" + \
                           "4. Shopping areas\n" + \
                           "5. Nightlife options"

        # Check for mixed interests in the prompt
        if any(word in user_input_lower for word in ["love", "interested in", "like", "enjoy", "want to"]):
            interests = []
            if "food" in user_input_lower or "restaurant" in user_input_lower:
                interests.append("food")
            if "technology" in user_input_lower or "tech" in user_input_lower:
                interests.append("technology")
            if "art" in user_input_lower or "museum" in user_input_lower:
                interests.append("art")
            if "culture" in user_input_lower or "cultural" in user_input_lower:
                interests.append("culture")
            if "shopping" in user_input_lower:
                interests.append("shopping")
            if "nature" in user_input_lower or "outdoor" in user_input_lower:
                interests.append("nature")
            if "beach" in user_input_lower:
                interests.append("beach")
            
            if interests:
                response = f"Great! I'll help you explore {destination} focusing on {', '.join(interests)}. Here are some recommendations:\n\n"
                
                # Get relevant recommendations for each interest
                for interest in interests:
                    if interest == "food":
                        restaurants = search_restaurants(destination, travel_info.get('dietary_preferences', ''))
                        response += "**Food Experiences:**\n"
                        for restaurant in restaurants[:3]:
                            response += f"- {restaurant}\n"
                        response += "\n"
                    
                    elif interest == "technology":
                        tech_attractions = search_special_interest(destination, "technology")
                        response += "**Technology Spots:**\n"
                        for attraction in tech_attractions[:3]:
                            response += f"- {attraction}\n"
                        response += "\n"
                    
                    elif interest == "art":
                        art_attractions = search_attractions(destination, "art")
                        response += "**Art & Museums:**\n"
                        for attraction in art_attractions[:3]:
                            response += f"- {attraction}\n"
                        response += "\n"
                    
                    elif interest == "culture":
                        cultural_attractions = search_attractions(destination, "cultural")
                        response += "**Cultural Experiences:**\n"
                        for attraction in cultural_attractions[:3]:
                            response += f"- {attraction}\n"
                        response += "\n"
                    
                    elif interest == "shopping":
                        shopping_attractions = search_attractions(destination, "shopping")
                        response += "**Shopping Areas:**\n"
                        for attraction in shopping_attractions[:3]:
                            response += f"- {attraction}\n"
                        response += "\n"
                    
                    elif interest == "nature":
                        nature_attractions = search_attractions(destination, "nature")
                        response += "**Nature & Outdoor:**\n"
                        for attraction in nature_attractions[:3]:
                            response += f"- {attraction}\n"
                        response += "\n"
                    
                    elif interest == "beach":
                        beach_attractions = search_attractions(destination, "beach")
                        response += "**Beach Experiences:**\n"
                        for attraction in beach_attractions[:3]:
                            response += f"- {attraction}\n"
                        response += "\n"
                
                response += "\nWould you like me to create a complete itinerary incorporating these interests?"
                return response

        # Check for weather queries - handle various formats
        if any(word in user_input_lower for word in ["weather", "temperature", "climate", "rain", "sunny", "forecast", "whats weather", "what's weather", "whats the weather", "what's the weather", "weather in", "weather there"]):
            # Extract location from the query if it's not in travel_info
            location = destination
            if not location:
                # Try to extract location from the prompt
                location_match = re.search(r"weather in (\w+)", user_input_lower)
                if location_match:
                    location = location_match.group(1).title()
                elif "weather there" in user_input_lower and st.session_state.travel_info.get('destination'):
                    location = st.session_state.travel_info['destination'].split(' For')[0].strip()
            
            if location:
                weather_info = get_weather(location)
                return weather_info
            else:
                return "Which city would you like to know the weather for?"
        
        # Check for specific queries first
        if any(word in user_input_lower for word in ["hotel", "stay", "accommodation", "lodging", "place to sleep"]):
            if not destination:
                return "Please specify a destination first. Where would you like to stay?"
            accommodations = search_accommodations(destination, travel_info.get('accommodation_preferences', 'moderate'))
            return "Here are some recommended hotels for your stay:\n\n" + "\n".join([f"- {accommodation}" for accommodation in accommodations[:5]])
            
        elif any(word in user_input_lower for word in ["restaurant", "food", "eat", "dining", "cuisine", "meal"]):
            if not destination:
                return "Please specify a destination first. Where would you like to eat?"
            restaurants = search_restaurants(destination, travel_info.get('dietary_preferences', ''))
            return "Here are some restaurants you might enjoy:\n\n" + "\n".join([f"- {restaurant}" for restaurant in restaurants[:5]])
            
        elif any(word in user_input_lower for word in ["attraction", "visit", "see", "museum", "landmark", "sight"]):
            if not destination:
                return "Please specify a destination first. Where would you like to visit?"
            attractions = search_attractions(destination, ",".join(travel_info.get('preferences', [])))
            return "Here are some top attractions I recommend:\n\n" + "\n".join([f"- {attraction}" for attraction in attractions[:5]])
        
        # Check for itinerary generation request
        elif any(word in user_input_lower for word in ["itinerary", "plan", "schedule", "day by day", "what to do"]):
            if not destination:
                return "Please specify a destination first. Where would you like to plan your trip?"
            itinerary = generate_recommendations()
            st.session_state.itinerary = itinerary
            return "I've generated your complete travel itinerary! You can find it above. Would you like to know more about any specific aspect of your trip?"
        
        # Handle transportation queries
        elif any(word in user_input_lower for word in ["transport", "getting around", "travel within", "public transit", "bus", "train", "subway", "metro"]):
            if not destination:
                return "Please specify a destination first so I can provide transportation information."
            return f"Getting around {destination} is relatively straightforward. Public transportation is usually the most efficient option. Would you like more specific information about transportation options?"
        
        # Handle safety queries
        elif any(word in user_input_lower for word in ["safe", "safety", "dangerous", "crime", "secure"]):
            if not destination:
                return "Please specify a destination first so I can provide safety information."
            return f"{destination} is generally safe for tourists, but always exercise normal precautions as you would in any large city. Keep your belongings secure, be aware of your surroundings, and avoid isolated areas at night."
        
        # Handle currency/money queries
        elif any(word in user_input_lower for word in ["currency", "money", "cash", "exchange", "payment", "credit card"]):
            if not destination:
                return "Please specify a destination first so I can provide currency information."
            return f"Be sure to check the local currency for {destination} before your trip. Major credit cards are widely accepted in most tourist destinations, but it's always good to have some local currency for small purchases."
        
        # Handle language queries
        elif any(word in user_input_lower for word in ["language", "speak", "talk", "communicate", "phrase", "translation"]):
            if not destination:
                return "Please specify a destination first so I can provide language information."
            return f"It's always helpful to learn a few basic phrases in the local language when visiting {destination}. Even simple greetings can enhance your travel experience and show respect for the local culture."
        
        # Handle accessibility queries
        elif any(word in user_input_lower for word in ["wheelchair", "accessible", "disability", "mobility", "handicap"]):
            if not destination:
                return "Please specify a destination first so I can provide accessibility information."
            
            # Update travel info to include accessibility needs
            st.session_state.travel_info["accessibility_needs"] = "wheelchair"
            
            # Get accessible attractions
            attractions = search_accessible_attractions(destination)
            return f"Here are some wheelchair-accessible attractions in {destination}:\n\n" + "\n".join([f"- {attraction}" for attraction in attractions[:5]]) + "\n\nWould you like me to create a fully accessible itinerary for your trip?"
        
        # Handle special interest queries (Broadway, wine, etc.)
        for interest, keywords in {
            "broadway": ["broadway", "theater", "theatre", "show", "musical", "play"],
            "wine": ["wine", "vineyard", "winery", "wine tasting"],
            "photography": ["photography", "photo", "camera", "picture"],
            "architecture": ["architecture", "building", "design", "structure"],
            "literature": ["literature", "book", "author", "literary", "bookstore"],
            "music": ["music", "concert", "festival", "live music", "band"],
            "sports": ["sports", "game", "match", "stadium", "arena"]
        }.items():
            if any(keyword in user_input_lower for keyword in keywords):
                if not destination:
                    return f"I can help you find great {interest} experiences. Where would you like to travel to?"
                
                # Update travel info to include special interest
                if "special_interests" not in st.session_state.travel_info:
                    st.session_state.travel_info["special_interests"] = []
                if interest not in st.session_state.travel_info["special_interests"]:
                    st.session_state.travel_info["special_interests"].append(interest)
                
                # Get special interest activities
                activities = search_special_interest(destination, interest)
                return f"Here are some {interest} experiences in {destination}:\n\n" + "\n".join([f"- {activity}" for activity in activities[:5]]) + "\n\nI'll make sure to include these in your itinerary!"
        
        # Handle vague travel queries
        if any(phrase in user_input_lower for phrase in ["where should i go", "recommend a place", "good place to visit", "somewhere nice", "vacation ideas"]):
            return "I'd be happy to help you plan a vacation! To provide personalized recommendations, I need some information:\n\n" + \
                   "1. What type of destination interests you?\n" + \
                   "   - Beach destination\n" + \
                   "   - City with cultural experiences\n" + \
                   "   - Mountain retreat\n" + \
                   "   - Historical sites\n" + \
                   "   - Adventure destination\n" + \
                   "   - Foodie paradise\n" + \
                   "   - Shopping destination\n" + \
                   "   - Nature and wildlife\n\n" + \
                   "2. How long are you planning to travel?\n\n" + \
                   "3. What's your budget level (low, moderate, or high)?\n\n" + \
                   "4. Any specific interests or requirements?\n" + \
                   "   - Food experiences\n" + \
                   "   - Art and culture\n" + \
                   "   - Outdoor activities\n" + \
                   "   - Shopping\n" + \
                   "   - Nightlife\n" + \
                   "   - Family-friendly activities\n" + \
                   "   - Accessibility needs\n" + \
                   "   - Language preferences"
        
        # Handle single-word or very short responses
        if len(prompt.strip().split()) <= 2:
            if destination:
                return f"I can help you with information about {destination}. Would you like to know about:\n\n" + \
                       "1. Current weather conditions\n" + \
                       "2. Recommended hotels\n" + \
                       "3. Popular attractions\n" + \
                       "4. Restaurant recommendations\n" + \
                       "5. A complete day-by-day itinerary\n\n" + \
                       "Please choose a number or ask about any specific aspect!"
            else:
                return "Where would you like to travel to? I can help you plan your trip!"
        
        # Try to generate a conversational response
        conversational_response = generate_conversational_response(prompt, travel_info, bool(st.session_state.get('itinerary', None)))
        if conversational_response:
            return conversational_response
        
        # Default response
        if destination:
            return f"I can help you with information about {destination}. Would you like to know about:\n\n" + \
                   "1. Current weather conditions\n" + \
                   "2. Recommended hotels\n" + \
                   "3. Popular attractions\n" + \
                   "4. Restaurant recommendations\n" + \
                   "5. A complete day-by-day itinerary\n\n" + \
                   "Please choose a number or ask about any specific aspect!"
        else:
            return "Where would you like to travel to? I can help you plan your trip!"
            
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return "I apologize, but I encountered an error. Could you please rephrase your question?"

# Function to chat with LLM
def chat(prompt, history=None):
    """Send a message to the LLM and get a response"""
    try:
        if LLM_MODE == "google" and GEMINI_API_KEY:
            # Initialize Gemini model
            model = genai.GenerativeModel('gemini-pro')
            
            # Create chat history if provided
            chat = model.start_chat(history=history) if history else model
            
            # Generate response
            response = chat.send_message(prompt)
            return response.text
        else:
            # For local mode, use the existing chat function
            messages = []
            if history:
                for msg in history:
                    messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": prompt})
            
            response = llm.invoke(messages)
            return response.content
            
    except Exception as e:
        print(f"Error in chat function: {str(e)}")
        return "I apologize, but I encountered an error while processing your request. Please try again."

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []
if "travel_info" not in st.session_state:
    st.session_state.travel_info = {}
if "itinerary" not in st.session_state:
    st.session_state.itinerary = None
if "llm" not in st.session_state:
    st.session_state.llm = llm

# Create header with three columns
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.title("✈️ Travel Agent")

with col2:
    if st.button("Start New Chat"):
        st.session_state.messages = []
        st.session_state.travel_info = {}
        st.session_state.itinerary = None
        st.rerun()

# Create two columns for chat and itinerary with different widths
chat_col, itinerary_col = st.columns([2, 1])

# Display chat messages in the left column
with chat_col:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Display itinerary in a scrollable box in the right column
with itinerary_col:
    st.markdown("### 📋 Your Travel Itinerary")
    st.markdown("---")
    
    # Create a container with fixed height and scrolling
    itinerary_container = st.container()
    with itinerary_container:
        if st.session_state.itinerary:
            # Add custom CSS for fixed positioning and improved visibility
            st.markdown("""
                <style>
                .itinerary-box {
                    position: fixed;
                    top: 100px;
                    right: 20px;
                    height: calc(100vh - 120px);
                    overflow-y: auto;
                    padding: 20px;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    background-color: #ffffff;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    width: 400px;
                    z-index: 1000;
                }
                .itinerary-box::-webkit-scrollbar {
                    width: 8px;
                }
                .itinerary-box::-webkit-scrollbar-track {
                    background: #f1f1f1;
                    border-radius: 4px;
                }
                .itinerary-box::-webkit-scrollbar-thumb {
                    background: #888;
                    border-radius: 4px;
                }
                .itinerary-box::-webkit-scrollbar-thumb:hover {
                    background: #555;
                }
                /* Add animation for when itinerary appears */
                @keyframes slideIn {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                .itinerary-box {
                    animation: slideIn 0.3s ease-out;
                }
                /* Adjust main content margin to prevent overlap */
                .main .block-container {
                    max-width: calc(100% - 440px);
                    margin-right: 440px;
                }
                /* Style for the download button container */
                .download-container {
                    position: sticky;
                    top: 0;
                    background-color: #ffffff;
                    padding: 10px 0;
                    margin-bottom: 15px;
                    border-bottom: 1px solid #e0e0e0;
                    z-index: 1001;
                }
                /* Style for the download button */
                .stDownloadButton button {
                    width: 100%;
                    background-color: #2ecc71;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-weight: 500;
                    transition: background-color 0.3s;
                }
                .stDownloadButton button:hover {
                    background-color: #27ae60;
                }
                </style>
                """, unsafe_allow_html=True)
            
            # Create a container for the download button
            st.markdown('<div class="download-container">', unsafe_allow_html=True)
            
            # Add download button
            st.download_button(
                label="📥 Download Itinerary",
                data=st.session_state.itinerary,
                file_name="travel_itinerary.md",
                mime="text/markdown"
            )
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Wrap the itinerary in a div with the custom class
            st.markdown(f'<div class="itinerary-box">{st.session_state.itinerary}</div>', unsafe_allow_html=True)
        else:
            st.markdown("Your itinerary will appear here once generated.")

# Accept user input at the bottom
if prompt := st.chat_input("Plan your trip..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with chat_col:
        with st.chat_message("user"):
            st.markdown(prompt)
    
    # Extract travel information from user message
    travel_info = extract_info_directly([msg["content"] for msg in st.session_state.messages])
    
    # Update travel info in session state
    for key, value in travel_info.items():
        if value:  # Only update if the new value is not empty
            st.session_state.travel_info[key] = value
    
    # Generate response based on the extracted information
    with chat_col:
        with st.chat_message("assistant"):
            # Show loading animation only during response generation
            loading_placeholder = st.empty()
            loading_placeholder.markdown('<div class="loading-dots" style="display: inline-block;">Thinking</div>', unsafe_allow_html=True)
            
            response = generate_response(prompt, st.session_state.travel_info)
            
            # Clear loading animation and show response
            loading_placeholder.empty()
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})