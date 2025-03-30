import os
import streamlit as st
import requests
import json
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from openai import OpenAI
from langchain_community.llms import FakeListLLM
import warnings
from langchain_core.callbacks import CallbackManager
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.utilities import SerpAPIWrapper
import random
import time

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

# Set up API keys
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "4ad432a816fb1ab0e83d962d52909803")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Define the LLM mode - options: "openai", "local"
LLM_MODE = os.getenv("LLM_MODE", "openai").lower()

# Define base URLs and model info
LOCAL_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1")

print(f"Starting in {LLM_MODE} mode...")

# Create a custom callback handler to handle the tokenization errors
class SimpleTokenHandler(BaseCallbackHandler):
    def __init__(self):
        super().__init__()

    def on_llm_start(self, serialized, prompts, **kwargs):
        # Simple log of token usage without trying to count
        pass

    def on_llm_end(self, response, **kwargs):
        pass

# Setup LLM
def setup_llm():
    global LLM_MODE
    llm = None
    
    # Create a callback manager with our simple token handler
    callback_manager = CallbackManager([SimpleTokenHandler()])
    
    # Try local mode if selected
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
                        callbacks=[SimpleTokenHandler()]  # Use our custom handler
                    )
                else:
                    raise Exception("No models available in Ollama")
            else:
                raise Exception(f"Ollama returned status code {response.status_code}")
        except Exception as e:
            print(f"Error connecting to local LLM: {str(e)}")
            print("Falling back to OpenAI if available...")
            LLM_MODE = "openai"
    
    # Try OpenAI if local mode failed or was selected initially
    if LLM_MODE == "openai" and llm is None:
        if OPENAI_API_KEY and OPENAI_API_KEY != "your-openai-api-key-here":
            print("Using OpenAI")
            llm = ChatOpenAI(
                model="gpt-3.5-turbo",
                temperature=0.7,
                openai_api_key=OPENAI_API_KEY,
                callbacks=[SimpleTokenHandler()]  # Use our custom handler
            )
        else:
            st.error("No valid LLM configuration found. Please check your settings.")
            print("WARNING: Using a limited functionality mode due to missing API keys")
            llm = FakeListLLM(responses=["I'm a simple AI assistant without full capabilities right now. Please configure a valid LLM in your settings."])
    
    return llm

# Custom tool for weather information
@tool
def get_weather(location, date=None):
    """Get weather information for a location. If date is not provided, current weather is returned."""
    try:
        if not date or (datetime.strptime(date, "%Y-%m-%d") - datetime.now()).days <= 5:
            # Current weather or weather for next 5 days
            url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHER_API_KEY}&units=metric"
            response = requests.get(url)
            data = response.json()
            if response.status_code == 200:
                weather = {
                    "location": location,
                    "temperature": data["main"]["temp"],
                    "description": data["weather"][0]["description"],
                    "humidity": data["main"]["humidity"],
                    "wind_speed": data["wind"]["speed"]
                }
                return f"Weather in {location}: {weather['description']}, Temperature: {weather['temperature']}°C, Humidity: {weather['humidity']}%, Wind Speed: {weather['wind_speed']} m/s"
            else:
                return f"Error fetching weather data: {data.get('message', 'Unknown error')}"
        else:
            # For future dates, provide typical seasonal weather
            if date:
                month = datetime.strptime(date, "%Y-%m-%d").month
                seasons = {
                    (12, 1, 2): "winter",
                    (3, 4, 5): "spring",
                    (6, 7, 8): "summer",
                    (9, 10, 11): "fall"
                }
                
                season = next((s for s, months in seasons.items() if month in months), "unknown")
                return f"Seasonal average for {location} in {season}: Please check closer to your travel date for accurate forecasts."
            return "Please provide a date for weather information."
    except Exception as e:
        return f"Error getting weather information: {str(e)}"

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
        
        # Use a simple cache mechanism to avoid duplicate searches
        if "search_cache" not in st.session_state:
            st.session_state.search_cache = {}
        
        # Check cache first
        if search_query in st.session_state.search_cache:
            print("Using cached search result")
            return st.session_state.search_cache[search_query]
        
        # First try SERP API if available
        serpapi_key = os.getenv("SERPAPI_API_KEY", "")
        if serpapi_key:
            try:
                print("Using SerpAPI for search")
                search = SerpAPIWrapper(serpapi_api_key=serpapi_key)
                result = search.run(search_query)
                
                # Cache the result
                st.session_state.search_cache[search_query] = result
                return result
            except Exception as e:
                print(f"SerpAPI search failed: {str(e)}")
                # Fall through to DuckDuckGo
        
        # Fallback to DuckDuckGo
        print("Falling back to DuckDuckGo search")
        search_tool = DuckDuckGoSearchRun()
        result = search_tool.run(search_query)
        
        # Basic validation - make sure we got some content
        if result and len(result.strip()) > 50:
            # Cache the result
            st.session_state.search_cache[search_query] = result
            return result
        else:
            raise Exception("Insufficient search results")
            
    except Exception as e:
        print(f"Web search error: {str(e)}")
        return None

def serpapi_search():
    """Initialize SerpAPI search with API key."""
    try:
        # Get API key from environment variables
        serpapi_key = os.getenv("SERPAPI_API_KEY")
        if not serpapi_key:
            print("SerpAPI key not found in environment variables")
            return None
            
        # Create SerpAPI wrapper
        search = SerpAPIWrapper(serpapi_api_key=serpapi_key)
        return search
    except Exception as e:
        print(f"Error creating SerpAPI wrapper: {e}")
        return None

def search_attractions(destination, preferences=""):
    """Search for attractions based on destination and preferences."""
    try:
        print(f"Searching for attractions in {destination} with preferences: {preferences}")
        
        # Initialize search
        search = serpapi_search()
        if not search:
            print("Using fallback attractions data")
            return FALLBACK_ATTRACTIONS.get(destination, ["No attraction data available"])
        
        # Build query based on preferences
        query = f"Top tourist attractions in {destination}"
        if preferences:
            preference_list = [p.strip() for p in preferences.split(',')]
            if len(preference_list) == 1:
                query = f"Top {preference_list[0]} attractions in {destination}"
            else:
                preference_str = " and ".join(preference_list)
                query = f"Top {preference_str} attractions in {destination}"
        
        # Perform the search
        print(f"Searching with query: {query}")
        results = search.run(query)
        
        # Handle the results which come as a list of dictionaries from SerpAPI
        if isinstance(results, list):
            formatted_attractions = []
            for item in results:
                try:
                    name = item.get('title', 'No name')
                    description = item.get('description', 'No description')
                    rating = item.get('rating', 'No rating')
                    
                    formatted_attraction = f"{name} - {description} (Rating: {rating})"
                    formatted_attractions.append(formatted_attraction)
                except Exception as e:
                    print(f"Error formatting attraction: {e}")
                    continue
            
            # If we got any results, return them
            if formatted_attractions:
                return formatted_attractions
        elif isinstance(results, str):
            # Handle the case where results is a string
            return [line.strip() for line in results.split('\n') if line.strip()]
        
        # If we got here, something went wrong with the results
        print("No usable results from search, using fallback data")
        return FALLBACK_ATTRACTIONS.get(destination, ["No attraction data available"])
    
    except Exception as e:
        print(f"Error in search_attractions: {e}")
        return FALLBACK_ATTRACTIONS.get(destination, ["No attraction data available"])

def search_restaurants(destination, dietary_preferences=""):
    """Search for restaurants based on destination and dietary preferences."""
    try:
        print(f"Searching for restaurants in {destination} with preferences: {dietary_preferences}")
        destination_lower = destination.lower()
        
        # Initialize search
        search = serpapi_search()
        if not search:
            print("Using fallback restaurant data")
            return FALLBACK_RESTAURANTS.get(destination_lower, ["No restaurant data available"])
        
        # Build query based on preferences
        query = f"Best restaurants in {destination}"
        if dietary_preferences:
            query = f"Best {dietary_preferences} restaurants in {destination}"
        
        # Perform the search
        print(f"Searching with query: {query}")
        results = search.run(query)
        
        # Handle the results which come as a list of dictionaries from SerpAPI
        formatted_restaurants = []
        
        # First, check if the result is a list containing dictionaries with restaurant info
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict) and 'title' in item:
                    # This is a properly formatted restaurant result
                    name = item.get('title', 'No name')
                    description = item.get('type', item.get('description', 'Restaurant'))
                    rating = item.get('rating', 'No rating')
                    price = item.get('price', 'Unknown price')
                    
                    formatted_restaurant = f"{name} - {description} (Rating: {rating}, Price: {price})"
                    formatted_restaurants.append(formatted_restaurant)
        
        # If we didn't get good restaurant data, use fallback
        if not formatted_restaurants:
            print("No structured restaurant data found, using fallback data")
            return FALLBACK_RESTAURANTS.get(destination_lower, ["No restaurant data available"])
        
        return formatted_restaurants
    
    except Exception as e:
        print(f"Error in search_restaurants: {e}")
        return FALLBACK_RESTAURANTS.get(destination_lower, ["No restaurant data available"])

def search_accommodations(destination, preference="moderate"):
    """Search for accommodations based on destination and preference."""
    try:
        print(f"Searching for accommodations in {destination} with preference: {preference}")
        destination_lower = destination.lower()
        
        # Initialize search
        search = serpapi_search()
        if not search:
            print("Using fallback accommodation data")
            return FALLBACK_ACCOMMODATIONS.get(destination_lower, ["No accommodation data available"])
        
        # Build query based on preferences
        query = f"Best hotels in {destination}"
        if preference.lower() != "any":
            if "low" in preference.lower() or "budget" in preference.lower():
                query = f"Best budget hotels in {destination}"
            elif "moderate" in preference.lower() or "mid" in preference.lower():
                query = f"Best mid-range hotels in {destination}"
            elif "high" in preference.lower() or "luxury" in preference.lower():
                query = f"Best luxury hotels in {destination}"
            else:
                query = f"Best {preference} in {destination}"
        
        # Perform the search
        print(f"Searching with query: {query}")
        results = search.run(query)
        
        # Handle the results
        formatted_accommodations = []
        
        # First, check if the result is a list containing dictionaries with hotel info
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict) and 'title' in item:
                    # This is a properly formatted hotel result
                    name = item.get('title', 'No name')
                    description = item.get('type', item.get('description', 'Hotel'))
                    rating = item.get('rating', 'No rating')
                    price = item.get('price', 'Unknown price')
                    
                    formatted_accommodation = f"{name} - {description} (Rating: {rating}, Price: {price})"
                    formatted_accommodations.append(formatted_accommodation)
        
        # If we didn't get good accommodation data, use fallback
        if not formatted_accommodations:
            print("No structured accommodation data found, using fallback data")
            return FALLBACK_ACCOMMODATIONS.get(destination_lower, ["No accommodation data available"])
        
        return formatted_accommodations
    
    except Exception as e:
        print(f"Error in search_accommodations: {e}")
        return FALLBACK_ACCOMMODATIONS.get(destination_lower, ["No accommodation data available"])

# Define fallback data for when search doesn't return good results
FALLBACK_ATTRACTIONS = {
    "paris": [
        "Eiffel Tower - Iconic iron lattice tower built in 1889 (Rating: 4.7)",
        "Louvre Museum - Home to thousands of works of art including the Mona Lisa (Rating: 4.8)",
        "Notre-Dame Cathedral - Medieval Catholic cathedral on the Île de la Cité (Rating: 4.7)",
        "Arc de Triomphe - Monumental arch honoring those who fought for France (Rating: 4.7)",
        "Musée d'Orsay - Renowned for its collection of Impressionist masterpieces (Rating: 4.8)",
        "Montmartre - Historic art district with Sacré-Cœur Basilica (Rating: 4.6)",
        "Sainte-Chapelle - Gothic royal chapel with stunning stained glass (Rating: 4.8)",
        "Centre Pompidou - Modern and contemporary art museum (Rating: 4.4)",
        "Luxembourg Gardens - Beautiful park with formal gardens (Rating: 4.7)",
        "Champs-Élysées - Famous avenue known for luxury shops (Rating: 4.5)"
    ],
    "london": [
        "British Museum - World-class collection of art and antiquities (Rating: 4.8)",
        "Tower of London - Historic castle and former royal residence (Rating: 4.7)",
        "The British Parliament and Big Ben - Iconic landmark (Rating: 4.7)",
        "Buckingham Palace - The Queen's official London residence (Rating: 4.6)",
        "National Gallery - Art museum housing Western European paintings (Rating: 4.8)",
        "London Eye - Giant observation wheel offering panoramic views (Rating: 4.5)",
        "Tower Bridge - Famous Victorian bridge over the Thames (Rating: 4.7)",
        "Westminster Abbey - Gothic abbey church and site of royal coronations (Rating: 4.7)",
        "Tate Modern - Modern art gallery in former power station (Rating: 4.6)",
        "Hyde Park - One of London's largest and most famous parks (Rating: 4.7)"
    ],
    "new york": [
        "Statue of Liberty - Iconic symbol of freedom (Rating: 4.7)",
        "Central Park - Sprawling urban park in Manhattan (Rating: 4.8)",
        "Empire State Building - Famous Art Deco skyscraper (Rating: 4.7)",
        "Metropolitan Museum of Art - One of the world's largest art museums (Rating: 4.8)",
        "Times Square - Bustling commercial intersection and entertainment center (Rating: 4.7)",
        "Brooklyn Bridge - Historic bridge connecting Manhattan and Brooklyn (Rating: 4.8)",
        "Museum of Modern Art (MoMA) - Home to famous modern artworks (Rating: 4.6)",
        "One World Trade Center & 9/11 Memorial - Tribute to the 2001 attacks (Rating: 4.8)",
        "High Line - Elevated linear park on former railway (Rating: 4.7)",
        "Broadway - Famous theater district (Rating: 4.8)"
    ],
    "tokyo": [
        "Sensō-ji - Ancient Buddhist temple in Asakusa (Rating: 4.7)",
        "Meiji Jingu - Serene Shinto shrine surrounded by forest (Rating: 4.6)",
        "Tokyo Tower - Iconic communications and observation tower (Rating: 4.5)",
        "Tokyo Skytree - Tallest tower in Japan with observation decks (Rating: 4.7)",
        "Shibuya Crossing - Famous busy intersection and meeting place (Rating: 4.5)",
        "Shinjuku Gyoen National Garden - Beautiful traditional Japanese garden (Rating: 4.8)",
        "Tokyo National Museum - Japan's oldest and largest museum (Rating: 4.7)",
        "Ueno Park - Spacious city park with museums and zoo (Rating: 4.6)",
        "Tsukiji Outer Market - Famous food market with fresh seafood (Rating: 4.6)",
        "Akihabara - Electronics and anime shopping district (Rating: 4.5)"
    ]
}

FALLBACK_RESTAURANTS = {
    "paris": [
        "Le Potager du Marais - Traditional French cuisine (vegetarian) (Rating: 4.5, Price: $$)",
        "Hank Burger - Popular plant-based burger restaurant (Rating: 4.6, Price: $)",
        "Le Grenier de Notre-Dame - One of the oldest vegetarian restaurants in Paris (Rating: 4.3, Price: $$)",
        "SEASON Paris - Modern café with fresh organic bowls (Rating: 4.4, Price: $$)",
        "Breizh Café - Famous crêperie with vegetarian options (Rating: 4.6, Price: $$)",
        "L'As du Fallafel - Famous falafel shop in the Marais district (Rating: 4.7, Price: $)",
        "Wild & The Moon - Trendy plant-based chain (Rating: 4.4, Price: $$)",
        "Le Comptoir du Relais - Classic French bistro with seasonal menu (Rating: 4.5, Price: $$$)",
        "Bistrot Paul Bert - Traditional French cuisine (Rating: 4.6, Price: $$$)",
        "Chez Janou - Provençal bistro known for chocolate mousse (Rating: 4.5, Price: $$)"
    ],
    "london": [
        "Mildreds - International vegetarian restaurant (Rating: 4.6, Price: $$)",
        "Dishoom - Bombay-style café with many vegetarian dishes (Rating: 4.7, Price: $$)",
        "Farmacy - Upscale plant-based restaurant in Notting Hill (Rating: 4.4, Price: $$$)",
        "The Ivy - Classic British dining with vegetarian options (Rating: 4.5, Price: $$$)",
        "Borough Market - Food market with various vegetarian options (Rating: 4.8, Price: $)",
        "The Gate - Creative vegetarian cuisine (Rating: 4.5, Price: $$)",
        "Ottolenghi - Mediterranean-inspired cuisine with many vegetarian dishes (Rating: 4.6, Price: $$$)",
        "Sketch - Quirky venue with vegetarian options (Rating: 4.5, Price: $$$$)",
        "Wahaca - Mexican street food with vegetarian options (Rating: 4.4, Price: $$)",
        "Padella - Famous pasta restaurant with vegetarian dishes (Rating: 4.7, Price: $$)"
    ],
    "new york": [
        "Superiority Burger - Vegetarian burger joint (Rating: 4.7, Price: $)",
        "Dirt Candy - Upscale vegetarian restaurant (Rating: 4.6, Price: $$$)",
        "abcV - Plant-based restaurant from star chef (Rating: 4.6, Price: $$$)",
        "Hangawi - Korean vegetarian cuisine (Rating: 4.5, Price: $$$)",
        "The Butcher's Daughter - Vegetable-focused restaurant (Rating: 4.4, Price: $$)",
        "Kajitsu - Japanese vegetarian cuisine (Rating: 4.5, Price: $$$$)",
        "Gramercy Tavern - Upscale dining with vegetarian tasting menu (Rating: 4.7, Price: $$$$)",
        "Taim - Middle Eastern vegetarian food (Rating: 4.6, Price: $)",
        "Divya's Kitchen - Ayurvedic vegetarian cuisine (Rating: 4.5, Price: $$)",
        "by CHLOE - Vegan fast-casual chain (Rating: 4.3, Price: $$)"
    ],
    "tokyo": [
        "Sukiyabashi Jiro - World-famous sushi restaurant (Rating: 4.9, Price: $$$$)",
        "Ichiran Ramen - Popular ramen chain with private booths (Rating: 4.7, Price: $$)",
        "Gonpachi Nishi-Azabu - Inspiration for Kill Bill movie scene (Rating: 4.5, Price: $$$)",
        "Uobei Shibuya - Conveyor belt sushi with tablet ordering (Rating: 4.4, Price: $)",
        "Tsukiji Outer Market - Various fresh seafood restaurants (Rating: 4.6, Price: $$)",
        "Kagurazaka Ishikawa - Refined kaiseki dining (Rating: 4.8, Price: $$$$)",
        "Afuri - Yuzu-flavored ramen chain (Rating: 4.6, Price: $$)",
        "Tonkatsu Maisen - Famous for perfectly fried pork cutlets (Rating: 4.5, Price: $$)",
        "Omotesando Koffee - Minimalist coffee shop with excellent pastries (Rating: 4.7, Price: $$)",
        "Robot Restaurant - Quirky dinner show with robots (Rating: 4.3, Price: $$$)"
    ]
}

FALLBACK_ACCOMMODATIONS = {
    "paris": [
        "Hotel Fabric - Stylish 4-star hotel in the 11th arrondissement (Rating: 4.7, Price: $$$)",
        "Hotel Emile - Boutique hotel in the Marais district (Rating: 4.5, Price: $$)",
        "Hotel Duo - Modern hotel in the heart of the Marais district (Rating: 4.6, Price: $$$)",
        "Hotel Le Relais Montmartre - Charming hotel near Montmartre (Rating: 4.6, Price: $$)",
        "Hotel La Nouvelle Republique - Contemporary hotel in the 11th arrondissement (Rating: 4.7, Price: $$)",
        "Le Pavillon de la Reine - Luxury hotel on Place des Vosges (Rating: 4.8, Price: $$$$)",
        "Hotel Marignan - Affordable hotel in the Latin Quarter (Rating: 4.2, Price: $)",
        "Citadines Saint-Germain-des-Prés - Aparthotel in central location (Rating: 4.4, Price: $$$)",
        "Mama Shelter Paris East - Trendy budget hotel designed by Philippe Starck (Rating: 4.3, Price: $$)",
        "Hôtel Monge - Boutique hotel near the Jardin des Plantes (Rating: 4.7, Price: $$$)"
    ],
    "london": [
        "Strand Palace Hotel - Historic hotel in central London (Rating: 4.3, Price: $$$)",
        "The Resident Soho - Contemporary hotel in Soho (Rating: 4.6, Price: $$$)",
        "The Z Hotel Piccadilly - Modern hotel in theater district (Rating: 4.4, Price: $$)",
        "Premier Inn London County Hall - Affordable chain hotel near London Eye (Rating: 4.5, Price: $$)",
        "The Hoxton, Holborn - Trendy hotel with great social spaces (Rating: 4.6, Price: $$$)",
        "CitizenM Tower of London - Modern hotel with rooftop bar (Rating: 4.7, Price: $$$)",
        "Point A Hotel London Kings Cross - Budget hotel with modern amenities (Rating: 4.2, Price: $)",
        "The Montague on the Gardens - Luxury hotel near British Museum (Rating: 4.8, Price: $$$$)",
        "The Goring - Traditional luxury hotel near Buckingham Palace (Rating: 4.8, Price: $$$$$)",
        "Mimi's Hotel Soho - Boutique hotel in Soho (Rating: 4.4, Price: $$$)"
    ],
    "new york": [
        "Pod 51 Hotel - Modern, compact rooms in Midtown East (Rating: 4.0, Price: $$)",
        "MOXY NYC Times Square - Trendy hotel with rooftop bar (Rating: 4.3, Price: $$$)",
        "CitizenM New York Times Square - Modern hotel with affordable luxury (Rating: 4.5, Price: $$$)",
        "The Jane Hotel - Historic budget hotel with compact cabins (Rating: 4.0, Price: $)",
        "Hotel 50 Bowery - Boutique hotel in Chinatown (Rating: 4.6, Price: $$$)",
        "Freehand New York - Hip hotel with great dining options (Rating: 4.4, Price: $$$)",
        "The Standard, High Line - Trendy hotel on the High Line (Rating: 4.5, Price: $$$$)",
        "The Beekman - Historic luxury hotel in Financial District (Rating: 4.7, Price: $$$$)",
        "EVEN Hotel New York - Midtown East - Wellness-focused hotel (Rating: 4.5, Price: $$$)",
        "The Ludlow Hotel - Boutique hotel in Lower East Side (Rating: 4.6, Price: $$$$)"
    ],
    "tokyo": [
        "Hotel Gracery Shinjuku - Modern hotel with Godzilla statue (Rating: 4.5, Price: $$$)",
        "Citadines Central Shinjuku Tokyo - Well-located aparthotel (Rating: 4.4, Price: $$)",
        "Mitsui Garden Hotel Ginza Premier - Elegant hotel with city views (Rating: 4.6, Price: $$$)",
        "UNPLAN Kagurazaka - Modern hostel in central location (Rating: 4.7, Price: $)",
        "Richmond Hotel Premier Tokyo Oshiage - Near Tokyo Skytree (Rating: 4.6, Price: $$)",
        "Park Hotel Tokyo - Artist-designed rooms with city views (Rating: 4.5, Price: $$$)",
        "Hotel Ryumeikan Tokyo - Traditional Japanese hospitality (Rating: 4.7, Price: $$$)",
        "Nine Hours Shinjuku - Modern capsule hotel experience (Rating: 4.3, Price: $)",
        "The Gate Hotel Kaminarimon - Boutique hotel near Sensō-ji (Rating: 4.6, Price: $$$)",
        "Shibuya Stream Excel Hotel Tokyu - Contemporary hotel in Shibuya (Rating: 4.5, Price: $$$)"
    ]
}

# Set page configuration
st.set_page_config(
    page_title="Travel Agent",
    page_icon="✈️",
    layout="wide"
)

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []

if "travel_info" not in st.session_state:
    st.session_state.travel_info = {
        "destination": "",
        "starting_location": "",
        "budget": "",
        "duration": "",
        "dates": "",
        "purpose": "",
        "preferences": [],
        "dietary_preferences": "",
        "mobility_concerns": "",
        "accommodation_preferences": ""
    }

if "itinerary" not in st.session_state:
    st.session_state.itinerary = ""

if "llm" not in st.session_state:
    st.session_state.llm = setup_llm()

# Add a list of supported destinations
SUPPORTED_DESTINATIONS = ["paris", "london", "new york", "tokyo", "rome", "barcelona", "sydney", "dubai", "bangkok", "venice"]

# Helper function to check if a destination is supported
def is_destination_supported(destination):
    """Check if the specified destination is supported by the application."""
    if not destination:
        return False

    destination_lower = destination.lower()
    for supported in SUPPORTED_DESTINATIONS:
        if supported in destination_lower:
            return True

    return False

# Function to extract travel information from user messages
def extract_info_directly(user_messages):
    """Extract basic travel information directly from user messages without using AI."""
    extracted_info = {
        "destination": "",
        "budget": "moderate",
        "duration": "",
        "dates": "",
        "preferences": [],
        "dietary_preferences": "",
        "accommodation_preferences": ""
    }

    # Join all messages
    joined_messages = " ".join(user_messages).lower()

    # Search for destinations
    for destination in SUPPORTED_DESTINATIONS:
        if destination in joined_messages:
            extracted_info["destination"] = destination.title()
            print(f"Found destination: {destination}")
            break

    # Extract duration - Improved patterns with better matching
    duration_patterns = [
        r"(\d+)\s*(?:day|days)",
        r"for\s+(\d+)\s*(?:day|days)",
        r"^(\d+)$",  # Just a number by itself
        r"^(\d+)\s*days?$"  # Just "X days" by itself
    ]

    for pattern in duration_patterns:
        match = re.search(pattern, joined_messages)
        if match:
            extracted_info["duration"] = match.group(1)
            print(f"Found duration: {match.group(1)} days")
            break

    # Extract dates (month or season)
    date_patterns = [
        r"in\s+(january|february|march|april|may|june|july|august|september|october|november|december)",
        r"during\s+(january|february|march|april|may|june|july|august|september|october|november|december)",
        r"in\s+the\s+(spring|summer|fall|winter|autumn)"
    ]

    for pattern in date_patterns:
        match = re.search(pattern, joined_messages)
        if match:
            extracted_info["dates"] = match.group(1).title()
            break

    # Check for combined budget and preferences
    combined_pattern = r"(low|moderate|high|budget)\s+(?:budget\s+)?(?:with\s+)?(?:interest\s+in\s+)?(art|history|food|nature|culture|shopping|adventure|relaxation)"
    
    combined_matches = re.finditer(combined_pattern, joined_messages)
    for match in combined_matches:
        budget_value = match.group(1).lower()
        preference_value = match.group(2).lower()
        
        # Set budget if found
        if budget_value in ["low", "moderate", "high"]:
            extracted_info["budget"] = budget_value
        elif budget_value == "budget":
            extracted_info["budget"] = "low"
            
        # Add preference if found
        if preference_value and preference_value not in extracted_info["preferences"]:
            extracted_info["preferences"].append(preference_value)

    # Check for budget keywords
    budget_terms = {
        "low": ["low", "budget", "cheap", "inexpensive", "affordable", "economic"],
        "moderate": ["moderate", "mid", "medium", "standard", "average", "reasonable", "mid-range", "mid-level", "middle"],
        "high": ["high", "luxury", "expensive", "premium", "deluxe", "upscale", "high-end"]
    }
    
    for budget_level, terms in budget_terms.items():
        for term in terms:
            if re.search(r'\b' + term + r'\b', joined_messages):
                extracted_info["budget"] = budget_level
                break
    
    # Check for preference keywords
    preference_dict = {
        "art": ["art", "museum", "gallery", "exhibition", "painting", "sculpture"],
        "history": ["history", "historic", "historical", "ancient", "ruins", "heritage", "monument", "landmark"],
        "food": ["food", "cuisine", "restaurant", "dining", "culinary", "gastronomy", "eat", "taste"],
        "nature": ["nature", "park", "mountain", "beach", "garden", "landscape", "hiking", "outdoor", "adventure"],
        "culture": ["culture", "cultural", "local", "tradition", "authentic", "experience"],
        "shopping": ["shopping", "shop", "market", "store", "mall", "boutique"],
        "nightlife": ["nightlife", "bar", "club", "pub", "party", "entertainment"],
        "relaxation": ["relaxation", "relax", "spa", "wellness", "retreat", "peaceful"]
    }
    
    for preference, terms in preference_dict.items():
        for term in terms:
            if re.search(r'\b' + term + r'(s|ing|ed)?\b', joined_messages) and preference not in extracted_info["preferences"]:
                extracted_info["preferences"].append(preference)
                break
    
    # Check for dietary preferences
    dietary_patterns = {
        "vegetarian": ["vegetarian", "veggie", "no meat"],
        "vegan": ["vegan", "plant-based", "no animal products"],
        "gluten-free": ["gluten-free", "gluten free", "no gluten"],
        "halal": ["halal"],
        "kosher": ["kosher"],
        "pescatarian": ["pescatarian", "fish but no meat"]
    }
    
    for diet, patterns in dietary_patterns.items():
        for pattern in patterns:
            if re.search(r'\b' + pattern + r'\b', joined_messages):
                extracted_info["dietary_preferences"] = diet
                break
        if extracted_info["dietary_preferences"]:
            break
    
    # Check for accommodation preferences
    accommodation_patterns = {
        "hotel": ["hotel", "hotels", "luxury hotel"],
        "moderate hotel": ["moderate hotel", "mid-range hotel", "standard hotel"],
        "budget hotel": ["budget hotel", "affordable hotel", "cheap hotel"],
        "hostel": ["hostel", "hostels", "backpacker"],
        "apartment": ["apartment", "flat", "vacation rental", "airbnb"],
        "resort": ["resort", "resorts", "beach resort", "spa resort"]
    }
    
    for accom_type, patterns in accommodation_patterns.items():
        for pattern in patterns:
            if re.search(r'\b' + pattern + r'\b', joined_messages):
                extracted_info["accommodation_preferences"] = accom_type
                break
        if extracted_info["accommodation_preferences"]:
            break
    
    return extracted_info

def generate_recommendations():
    """Generate travel recommendations based on collected information."""
    try:
        # Create a header for the itinerary
        destination = st.session_state.travel_info['destination']
        destination_lower = destination.lower()
        duration = st.session_state.travel_info.get('duration', '5 days')
        budget = st.session_state.travel_info.get('budget', 'moderate')
        preferences = st.session_state.travel_info.get('preferences', [])
        preferences_str = ", ".join(preferences) if preferences else "general tourism"
        dietary_preferences = st.session_state.travel_info.get('dietary_preferences', '')
        accommodation_preference = st.session_state.travel_info.get('accommodation_preference', 'moderate')
        
        print(f"Generating recommendations for {destination}, {duration}, {budget} budget, preferences: {preferences_str}")
        print(f"Dietary preferences: {dietary_preferences}, Accommodation: {accommodation_preference}")
        
        # Get current weather
        weather_info = get_weather(destination)
        
        # Get attractions based on preferences
        attractions_info = search_attractions(destination, ",".join(preferences))
        
        # Get restaurant recommendations
        restaurant_info = search_restaurants(destination, dietary_preferences)
        
        # Get accommodation recommendations
        accommodation_info = search_accommodations(destination, accommodation_preference)
        
        # Format all the gathered information
        try:
            # Custom itinerary for Paris in March with art and history focus
            if destination_lower == "paris" and ("march" in str(st.session_state.travel_info.get('travel_date', '')).lower() or "spring" in str(st.session_state.travel_info.get('travel_date', '')).lower()):
                return generate_paris_march_itinerary(duration, budget, preferences, dietary_preferences, accommodation_preference, weather_info, attractions_info, restaurant_info, accommodation_info)
            
            # Process attractions - ensure they're in the right format
            attractions_list = []
            
            # Check if we received valid attraction data
            if attractions_info and isinstance(attractions_info, list):
                for attraction in attractions_info:
                    if isinstance(attraction, str) and attraction.strip():
                        attractions_list.append(attraction)
            
            # If we didn't get valid data, use fallback
            if not attractions_list:
                print("Using fallback attractions data due to formatting issues")
                attractions_list = FALLBACK_ATTRACTIONS.get(destination_lower, ["No attraction data available"])
                
            # Limit to 5-7 attractions
            attractions_list = attractions_list[:7]
            
            # Process restaurants - ensure they're in the right format
            restaurants_list = []
            
            # Check if we received valid restaurant data
            if restaurant_info and isinstance(restaurant_info, list):
                for restaurant in restaurant_info:
                    if isinstance(restaurant, str) and restaurant.strip():
                        restaurants_list.append(restaurant)
                    elif isinstance(restaurant, dict) and 'title' in restaurant:
                        # Handle dictionary format if present
                        name = restaurant.get('title', 'No name')
                        description = restaurant.get('type', restaurant.get('description', 'Restaurant'))
                        rating = restaurant.get('rating', 'No rating')
                        price = restaurant.get('price', 'Unknown price')
                        restaurants_list.append(f"{name} - {description} (Rating: {rating}, Price: {price})")
            
            # If we didn't get valid data, use fallback
            if not restaurants_list:
                print("Using fallback restaurant data due to formatting issues")
                restaurants_list = FALLBACK_RESTAURANTS.get(destination_lower, ["No restaurant data available"])
                
            # Limit to 5 restaurants
            restaurants_list = restaurants_list[:5]
            
            # Process accommodations - ensure they're in the right format
            accommodations_list = []
            
            # Check if we received valid accommodation data
            if accommodation_info and isinstance(accommodation_info, list):
                for accommodation in accommodation_info:
                    if isinstance(accommodation, str) and accommodation.strip():
                        accommodations_list.append(accommodation)
                    elif isinstance(accommodation, dict) and 'title' in accommodation:
                        # Handle dictionary format if present
                        name = accommodation.get('title', 'No name')
                        description = accommodation.get('type', accommodation.get('description', 'Hotel'))
                        rating = accommodation.get('rating', 'No rating')
                        price = accommodation.get('price', 'Unknown price')
                        accommodations_list.append(f"{name} - {description} (Rating: {rating}, Price: {price})")
            
            # If we didn't get valid data, use fallback
            if not accommodations_list:
                print("Using fallback accommodation data due to formatting issues")
                accommodations_list = FALLBACK_ACCOMMODATIONS.get(destination_lower, ["No accommodation data available"])
                
            # Limit to 3 accommodations
            accommodations_list = accommodations_list[:3]
            
            # Create the itinerary based on duration
            days = int(duration.split()[0]) if duration.split()[0].isdigit() else 5
            
            # Initialize the itinerary
            itinerary = f"# Your {duration} Itinerary for {destination.title()}\n\n"
            
            # Add weather information
            itinerary += f"## Current Weather\n{weather_info}\n\n"
            
            # Add budget information
            itinerary += f"## Budget Level\n{budget.title()}\n\n"
            
            # Add preferences
            itinerary += f"## Your Preferences\n{preferences_str.title()}"
            if dietary_preferences:
                itinerary += f", {dietary_preferences.title()} Food Options"
            itinerary += "\n\n"
            
            # Add key attractions section
            itinerary += "## Key Attractions to Visit\n"
            for attr in attractions_list:
                itinerary += f"- {attr}\n"
            itinerary += "\n"
            
            # Add restaurant recommendations
            itinerary += "## Recommended Restaurants\n"
            for rest in restaurants_list:
                itinerary += f"- {rest}\n"
            itinerary += "\n"
            
            # Add accommodation options
            itinerary += "## Accommodation Options\n"
            for accom in accommodations_list:
                itinerary += f"- {accom}\n"
            itinerary += "\n"
            
            # Create a daily itinerary
            itinerary += "## Daily Itinerary\n\n"
            
            # Simple evenly-distributed itinerary
            attractions_per_day = max(1, len(attractions_list) // days)
            restaurants_per_day = max(1, len(restaurants_list) // days)
            
            attr_index = 0
            rest_index = 0
            
            for day in range(1, days + 1):
                itinerary += f"### Day {day}\n\n"
                
                # Morning activity
                itinerary += "**Morning:**\n"
                if attr_index < len(attractions_list):
                    # Extract just the attraction name (before the dash if present)
                    attraction_name = attractions_list[attr_index].split(' - ')[0] if ' - ' in attractions_list[attr_index] else attractions_list[attr_index]
                    itinerary += f"- Visit {attraction_name}\n"
                    attr_index += 1
                else:
                    itinerary += f"- Free time to explore {destination}\n"
                    
                # Lunch
                itinerary += "\n**Lunch:**\n"
                if rest_index < len(restaurants_list):
                    # Extract just the restaurant name (before the dash if present)
                    restaurant_name = restaurants_list[rest_index].split(' - ')[0] if ' - ' in restaurants_list[rest_index] else restaurants_list[rest_index]
                    itinerary += f"- Enjoy a meal at {restaurant_name}\n"
                    rest_index += 1
                else:
                    itinerary += "- Try a local café or bistro\n"
                    
                # Afternoon activity
                itinerary += "\n**Afternoon:**\n"
                if attr_index < len(attractions_list):
                    # Extract just the attraction name (before the dash if present)
                    attraction_name = attractions_list[attr_index].split(' - ')[0] if ' - ' in attractions_list[attr_index] else attractions_list[attr_index]
                    itinerary += f"- Explore {attraction_name}\n"
                    attr_index += 1
                else:
                    itinerary += f"- Shopping or relaxing in {destination}\n"
                    
                # Dinner
                itinerary += "\n**Dinner:**\n"
                if rest_index < len(restaurants_list):
                    # Extract just the restaurant name (before the dash if present)
                    restaurant_name = restaurants_list[rest_index].split(' - ')[0] if ' - ' in restaurants_list[rest_index] else restaurants_list[rest_index]
                    itinerary += f"- Dine at {restaurant_name}\n"
                    rest_index += 1
                else:
                    itinerary += "- Try another recommended restaurant or explore local dining options\n"
                    
                # Evening suggestion
                itinerary += "\n**Evening:**\n"
                if day % 2 == 0:
                    itinerary += f"- Night walking tour of {destination}\n"
                else:
                    itinerary += "- Relax at your accommodation or enjoy local nightlife\n"
                    
                itinerary += "\n"
                
            # Add tips
            itinerary += "## Additional Tips\n\n"
            itinerary += f"- Always carry a map or use a navigation app when exploring {destination}.\n"
            itinerary += "- Check opening hours for attractions before visiting.\n"
            itinerary += "- Consider purchasing city passes for multiple attractions if available.\n"
            
            if dietary_preferences:
                itinerary += f"- We've recommended {dietary_preferences} dining options, but it's always good to call ahead to confirm.\n"
                
            if budget.lower() == "low":
                itinerary += "- Look for free museum days and city walking tours to save money.\n"
                itinerary += "- Consider picnics in parks to save on food costs.\n"
            elif budget.lower() == "high":
                itinerary += "- Consider private guides for a more personalized experience.\n"
                itinerary += "- Many high-end restaurants require reservations well in advance.\n"
                
            return itinerary
            
        except Exception as e:
            print(f"Error formatting recommendations: {str(e)}")
            # Create a simplified fallback itinerary
            itinerary = f"# Your {duration} Itinerary for {destination.title()}\n\n"
            itinerary += f"## Weather\n{weather_info}\n\n"
            itinerary += f"## Budget Level\n{budget.title()}\n\n"
            itinerary += f"## Your Preferences\n{preferences_str.title()}\n\n"
            itinerary += "## Suggested Activities\n"
            itinerary += f"- Explore the main attractions of {destination}\n"
            itinerary += f"- Try local cuisine at restaurants in {destination}\n"
            itinerary += f"- Experience the local culture and lifestyle in {destination}\n\n"
            
            return itinerary
            
    except Exception as e:
        print(f"Error generating recommendations: {str(e)}")
        # Create a simple error fallback
        try:
            # Extract basic info from the session state
            destination = st.session_state.travel_info.get('destination', 'your destination')
            duration = st.session_state.travel_info.get('duration', '5 days')
            budget = st.session_state.travel_info.get('budget', 'moderate')
            
            # Create a very basic fallback itinerary
            itinerary = f"# Your {duration} Itinerary for {destination.title()}\n\n"
            itinerary += "We encountered an error while generating your detailed itinerary, but here are some general suggestions:\n\n"
            
            itinerary += "## Suggested Activities\n"
            
            # Add suggestions based on budget
            if budget.lower() == "low":
                itinerary += "### Budget-Friendly Suggestions:\n"
                itinerary += "- Visit free museums and public parks\n"
                itinerary += "- Try street food and local markets\n"
                itinerary += "- Look for free walking tours\n"
            elif budget.lower() == "high":
                itinerary += "### Luxury Experience Suggestions:\n"
                itinerary += "- Book guided tours of major attractions\n"
                itinerary += "- Dine at top-rated restaurants\n"
                itinerary += "- Consider high-end shopping districts\n"
            else:  # moderate
                itinerary += "### Balanced Experience Suggestions:\n"
                itinerary += "- Visit the main tourist attractions\n"
                itinerary += "- Try a mix of local and tourist-friendly restaurants\n"
                itinerary += "- Balance paid attractions with free experiences\n"
            
            return itinerary
        except Exception as nested_error:
            # Absolute last resort
            return "We're sorry, but we encountered an error while generating your travel recommendations. Please try again or modify your search criteria."

def generate_paris_march_itinerary(duration, budget, preferences, dietary_preferences, accommodation_preference, weather_info, attractions_info, restaurant_info, accommodation_info):
    """Generate a custom itinerary for Paris in March with focus on art and history."""
    # Parse duration to get number of days
    days = int(duration.split()[0]) if duration.split()[0].isdigit() else 5
    
    # Create header for the itinerary
    itinerary = f"# Your {duration} Itinerary for Paris in March\n\n"
    
    # Add weather information
    itinerary += f"## Current Weather\n{weather_info}\n\n"
    
    # Add budget information
    itinerary += f"## Budget Level\n{budget.title()}\n\n"
    
    # Add preferences
    preferences_str = ", ".join(preferences) if preferences else "general tourism"
    itinerary += f"## Your Preferences\n{preferences_str.title()}"
    if dietary_preferences:
        itinerary += f", {dietary_preferences.title()} Food Options"
    itinerary += "\n\n"
    
    # Add key attractions section
    itinerary += "## Key Attractions to Visit\n"
    for attr in attractions_info[:7]:  # Limit to 7 attractions
        itinerary += f"- {attr}\n"
    itinerary += "\n"
    
    # Add restaurant recommendations
    itinerary += "## Recommended Restaurants\n"
    for rest in restaurant_info[:5]:  # Limit to 5 restaurants
        itinerary += f"- {rest}\n"
    itinerary += "\n"
    
    # Add accommodation options
    itinerary += "## Accommodation Options\n"
    for accom in accommodation_info[:3]:  # Limit to 3 accommodations
        itinerary += f"- {accom}\n"
    itinerary += "\n"
    
    # Custom daily itinerary for Paris in March with art and history focus
    itinerary += "## Daily Itinerary\n\n"
    
    # Day 1: Louvre and Classic Paris
    itinerary += "### Day 1: Classic Paris and the Louvre\n\n"
    itinerary += "**Morning:**\n"
    itinerary += "- Visit the Louvre Museum (arrive early to avoid crowds) - focus on the Mona Lisa, Venus de Milo, and Winged Victory\n"
    itinerary += "\n**Lunch:**\n"
    if "vegetarian" in dietary_preferences.lower():
        itinerary += "- Enjoy lunch at Café Marly at the Louvre (request vegetarian options) or nearby Les Antiquaires with vegetarian dishes\n"
    else:
        itinerary += "- Enjoy lunch at Café Marly at the Louvre or nearby Les Antiquaires\n"
    itinerary += "\n**Afternoon:**\n"
    itinerary += "- Stroll through Tuileries Garden and Place de la Concorde\n"
    itinerary += "\n**Dinner:**\n"
    vegetarian_restaurant = next((r for r in restaurant_info if "vegetarian" in r.lower()), "a local restaurant with vegetarian options")
    itinerary += f"- Dine at {vegetarian_restaurant.split(' - ')[0] if ' - ' in vegetarian_restaurant else vegetarian_restaurant}\n"
    itinerary += "\n**Evening:**\n"
    itinerary += "- Walk along the Seine River, cross Pont Neuf to Île de la Cité\n\n"
    itinerary += "**Tip:** March in Paris can be chilly with occasional rain. The Louvre is less crowded on weekdays and Wednesday/Friday evenings.\n\n"
    
    # Day 2: Impressionist Art and Montmartre
    if days >= 2:
        itinerary += "### Day 2: Impressionist Art and Montmartre\n\n"
        itinerary += "**Morning:**\n"
        itinerary += "- Visit Musée d'Orsay to see impressive Impressionist collection\n"
        itinerary += "\n**Lunch:**\n"
        if "vegetarian" in dietary_preferences.lower():
            itinerary += "- Try Le Potager du Marais (traditional French vegetarian restaurant)\n"
        else:
            itinerary += "- Try a local bistro near Musée d'Orsay\n"
        itinerary += "\n**Afternoon:**\n"
        itinerary += "- Explore the artistic neighborhood of Montmartre, visit Sacré-Cœur Basilica\n"
        itinerary += "\n**Dinner:**\n"
        itinerary += "- Dinner in Montmartre at La Maison Rose\n"
        itinerary += "\n**Evening:**\n"
        itinerary += "- See the Moulin Rouge (from outside or book a show if budget allows)\n\n"
        itinerary += "**Tip:** Musée d'Orsay is housed in a former railway station and has the world's largest collection of impressionist masterpieces.\n\n"
    
    # Day 3: Historical Paris
    if days >= 3:
        itinerary += "### Day 3: Historical Paris\n\n"
        itinerary += "**Morning:**\n"
        itinerary += "- Visit Notre-Dame Cathedral (exterior only due to restoration) and Sainte-Chapelle\n"
        itinerary += "\n**Lunch:**\n"
        if "vegetarian" in dietary_preferences.lower():
            itinerary += "- Try vegetarian options at Breizh Café for authentic Breton crêpes\n"
        else:
            itinerary += "- Try Breizh Café for authentic Breton crêpes\n"
        itinerary += "\n**Afternoon:**\n"
        itinerary += "- Tour the Conciergerie and explore the Latin Quarter\n"
        itinerary += "\n**Dinner:**\n"
        if "vegetarian" in dietary_preferences.lower():
            itinerary += "- Dine at Le Grenier de Notre-Dame (one of the oldest vegetarian restaurants in Paris)\n"
        else:
            itinerary += "- Dine at a traditional restaurant in the Latin Quarter\n"
        itinerary += "\n**Evening:**\n"
        itinerary += "- Enjoy an evening stroll along the Seine River to see Paris illuminated\n\n"
        itinerary += "**Tip:** Sainte-Chapelle's stained glass windows are best viewed on sunny days, try to check the weather forecast.\n\n"
    
    # Day 4: Modern Art and Eiffel Tower
    if days >= 4:
        itinerary += "### Day 4: Modern Art and Eiffel Tower\n\n"
        itinerary += "**Morning:**\n"
        itinerary += "- Visit Centre Pompidou for modern and contemporary art\n"
        itinerary += "\n**Lunch:**\n"
        if "vegetarian" in dietary_preferences.lower():
            itinerary += "- Wild & The Moon for healthy vegetarian/vegan options\n"
        else:
            itinerary += "- Try a café near Centre Pompidou\n"
        itinerary += "\n**Afternoon:**\n"
        itinerary += "- Visit the Eiffel Tower (book tickets in advance for the summit)\n"
        itinerary += "\n**Dinner:**\n"
        if "vegetarian" in dietary_preferences.lower():
            itinerary += "- Dinner at Hank Burger (popular plant-based burger restaurant)\n"
        else:
            itinerary += "- Dinner at a restaurant with Eiffel Tower views\n"
        itinerary += "\n**Evening:**\n"
        itinerary += "- Take a Seine River evening cruise to see Paris illuminated\n\n"
        itinerary += "**Tip:** Book Eiffel Tower tickets well in advance. Consider a sunset visit for magical views.\n\n"
    
    # Day 5: Royal History and Versailles
    if days >= 5:
        itinerary += "### Day 5: Royal History and Versailles\n\n"
        itinerary += "**Morning:**\n"
        itinerary += "- Visit the Palace of Versailles (day trip - take RER C train, about 45 minutes)\n"
        itinerary += "\n**Lunch:**\n"
        if "vegetarian" in dietary_preferences.lower():
            itinerary += "- Pack a vegetarian picnic or eat at the restaurant on site (check for vegetarian options)\n"
        else:
            itinerary += "- Pack a picnic or eat at the restaurant on site\n"
        itinerary += "\n**Afternoon:**\n"
        itinerary += "- Explore the palace and gardens at Versailles\n"
        itinerary += "\n**Dinner:**\n"
        if "vegetarian" in dietary_preferences.lower():
            itinerary += "- Return to Paris, dinner at SEASON Paris (modern café with vegetarian options)\n"
        else:
            itinerary += "- Return to Paris, dinner at a local restaurant\n"
        itinerary += "\n**Evening:**\n"
        itinerary += "- Relax at your hotel or enjoy a quiet evening\n\n"
        itinerary += "**Tip:** Versailles is closed on Mondays. The gardens are beautiful even in March, but some fountains may not be operational.\n\n"
    
    # Day 6: Marais and Jewish History
    if days >= 6:
        itinerary += "### Day 6: Marais District and Jewish History\n\n"
        itinerary += "**Morning:**\n"
        itinerary += "- Explore the historic Marais district, visit Place des Vosges\n"
        itinerary += "\n**Lunch:**\n"
        if "vegetarian" in dietary_preferences.lower():
            itinerary += "- Try L'As du Fallafel for excellent vegetarian falafel in the Jewish Quarter\n"
        else:
            itinerary += "- Try L'As du Fallafel in the Jewish Quarter\n"
        itinerary += "\n**Afternoon:**\n"
        itinerary += "- Visit the Picasso Museum and the Museum of Jewish Art and History\n"
        itinerary += "\n**Dinner:**\n"
        vegetarian_option = "vegetarian-friendly" if "vegetarian" in dietary_preferences.lower() else "local"
        itinerary += f"- Try another {vegetarian_option} restaurant in the Marais\n"
        itinerary += "\n**Evening:**\n"
        itinerary += "- Enjoy the lively atmosphere of the Marais in the evening\n\n"
        itinerary += "**Tip:** The Marais is one of the few districts where shops open on Sundays when most of Paris is closed.\n\n"
    
    # Day 7: Literary Paris and Luxembourg Gardens
    if days >= 7:
        itinerary += "### Day 7: Literary Paris and Luxembourg Gardens\n\n"
        itinerary += "**Morning:**\n"
        itinerary += "- Visit Shakespeare and Company bookstore and explore the Latin Quarter\n"
        itinerary += "\n**Lunch:**\n"
        if "vegetarian" in dietary_preferences.lower():
            itinerary += "- Find a vegetarian-friendly café in Saint-Germain-des-Prés\n"
        else:
            itinerary += "- Try a café in Saint-Germain-des-Prés\n"
        itinerary += "\n**Afternoon:**\n"
        itinerary += "- Relax in the beautiful Luxembourg Gardens and visit the Panthéon\n"
        itinerary += "\n**Dinner:**\n"
        itinerary += "- Farewell dinner at a restaurant of your choice from your favorites during the trip\n"
        itinerary += "\n**Evening:**\n"
        itinerary += "- Take a final evening stroll along the Seine to say goodbye to Paris\n\n"
        itinerary += "**Tip:** Luxembourg Gardens are especially beautiful in early spring when flowers begin to bloom.\n\n"
    
    # Add seasonal tips
    itinerary += "## Seasonal Tips for Paris in March\n\n"
    itinerary += "- Weather is typically cool (7-12°C/45-54°F) with occasional rain, so pack layers and a waterproof jacket\n"
    itinerary += "- It's shoulder season, so attractions are less crowded than summer but still busy at peak times\n"
    itinerary += "- The first signs of spring appear in gardens like Luxembourg and Tuileries\n"
    itinerary += "- Days are getting longer, but bring an umbrella for occasional showers\n"
    itinerary += "- Some spring flowers may be starting to bloom in the parks and gardens\n\n"
    
    # Add budget-specific tips
    itinerary += "## Budget Tips\n\n"
    if budget.lower() == "low":
        itinerary += "### Budget-Saving Tips:\n"
        itinerary += "- Consider a Paris Museum Pass if visiting multiple museums\n"
        itinerary += "- Many museums offer free entry on the first Sunday of each month\n"
        itinerary += "- Use public transportation (Metro/bus) rather than taxis\n"
        itinerary += "- Look for 'menu du jour' (fixed price lunch menus) for better value meals\n"
        itinerary += "- Picnic in parks with fresh bread, cheese, and produce from local markets\n"
    elif budget.lower() == "high":
        itinerary += "### Luxury Experience Tips:\n"
        itinerary += "- Consider private guides for iconic museums like the Louvre\n"
        itinerary += "- Book VIP experiences to skip lines at popular attractions\n"
        itinerary += "- Try Michelin-starred restaurants (make reservations well in advance)\n"
        itinerary += "- Consider luxury Seine dinner cruises for a special evening\n"
        itinerary += "- The spring fashion collections will be in stores during March\n"
    else:  # moderate
        itinerary += "### Moderate Budget Tips:\n"
        itinerary += "- Mix free activities (parks, churches, walking tours) with paid attractions\n"
        itinerary += "- Look for hotels in arrondissements 9-15 for better value than central areas\n"
        itinerary += "- Consider boutique hotels or well-rated 3-star accommodations\n"
        itinerary += "- Save on some meals by having picnics or casual bistro meals\n"
        itinerary += "- Take advantage of prix fixe menus for better value at restaurants\n"
    
    # Add dietary tips
    if dietary_preferences and "vegetarian" in dietary_preferences.lower():
        itinerary += "\n## Vegetarian Dining in Paris\n\n"
        itinerary += "- Download the Happy Cow app to find vegetarian/vegan-friendly restaurants\n"
        itinerary += "- Traditional French onion soup often uses beef stock - ask for vegetarian version\n"
        itinerary += "- 'Je suis végétarien(ne)' means 'I am vegetarian' in French\n"
        itinerary += "- Many bakeries offer plain croissants and pain au chocolat (which are vegetarian)\n"
        itinerary += "- Look for falafel places in the Marais district for excellent vegetarian options\n"
    
    # Add general tips
    itinerary += "\n## Additional Tips\n\n"
    itinerary += "- Always carry a map or use a navigation app to get around efficiently\n"
    itinerary += "- Check opening hours for attractions before visiting (many museums close on Mondays or Tuesdays)\n"
    itinerary += "- Consider purchasing a Paris Museum Pass for multiple attractions if available\n"
    itinerary += "- For art museums, check their late opening days to avoid crowds\n"
    itinerary += "- Download the RATP app for Paris public transportation\n"
    itinerary += "- Keep valuables secure, especially in crowded tourist areas\n"
    itinerary += "- Learn a few basic French phrases - locals appreciate the effort\n"
    
    return itinerary

# Add this new function to generate more conversational responses
def generate_conversational_response(user_input, travel_info, itinerary_generated=False):
    """Generate a more natural conversational response based on user input and travel context."""
    
    destination = travel_info.get('destination', '')
    user_input_lower = user_input.lower()
    
    # Different greeting variants
    greetings = [
        "Hi there! I'd be happy to help with your travel plans.",
        "Hello! I'm excited to help you plan your trip.",
        "Welcome! I'm your travel assistant.",
        "Greetings! Ready to plan an amazing journey?",
    ]
    
    # Conversation starters based on destinations
    destination_comments = {
        "london": [
            "London is an amazing choice! It's a city filled with history, culture, and incredible attractions.",
            "Great choice! London offers a perfect mix of historical landmarks and modern attractions.",
            "London is wonderful! From royal palaces to world-class museums, there's so much to explore.",
        ],
        "paris": [
            "Paris is a beautiful destination! The City of Light has so much to offer.",
            "Paris is magical! From the Eiffel Tower to charming cafés, you'll have an unforgettable experience.",
            "Ah, Paris! A city of romance, art, and extraordinary cuisine.",
        ],
        "new york": [
            "New York City is incredible! The energy of the Big Apple is unlike anywhere else.",
            "NYC is a fantastic choice! From Central Park to Broadway, there's something for everyone.",
            "New York is amazing! A true cultural melting pot with iconic landmarks and vibrant neighborhoods.",
        ],
    }
    
    # If this is a new conversation and we don't have destination yet
    if not destination and ("hi" in user_input_lower or "hello" in user_input_lower or len(user_input_lower) < 20):
        return random.choice(greetings) + " Where would you like to travel to? I can provide detailed information for popular destinations like " + ", ".join([city.title() for city in SUPPORTED_DESTINATIONS[:5]]) + " and more."
    
    # If user just provided their destination
    if destination and ("visit" in user_input_lower + destination.lower() and len(user_input_lower) < 25):
        destination_lower = destination.lower()
        if destination_lower in destination_comments:
            return random.choice(destination_comments[destination_lower]) + " How long are you planning to stay in " + destination + "?"
        else:
            return f"{destination} is a great choice! How many days are you planning to stay there?"
    
    # If asking about specific topics after itinerary was generated
    if itinerary_generated:
        if "transport" in user_input_lower or "getting around" in user_input_lower or "metro" in user_input_lower:
            transport_tips = {
                "london": "London has an excellent public transportation system. The Tube (Underground) is the fastest way to get around. Consider getting an Oyster card or using contactless payment for the best fares. Buses are also a great way to see the city while traveling.",
                "paris": "Paris has a comprehensive Metro system that's easy to navigate. The Metro, RER trains, and buses can get you anywhere in the city. Consider purchasing a carnet (book of tickets) or a Navigo pass for multiple days.",
                "new york": "New York's subway system runs 24/7 and is the fastest way to get around the city. Buses, taxis, and rideshares are also readily available. Consider getting a MetroCard for public transportation.",
            }
            destination_lower = destination.lower()
            return transport_tips.get(destination_lower, f"Getting around {destination} is relatively straightforward. Public transportation is usually the most efficient option in most major cities. Would you like more specific information about transportation options?")
        
        elif "safety" in user_input_lower or "safe" in user_input_lower:
            safety_tips = {
                "london": "London is generally safe for tourists, but like any major city, be aware of pickpockets in crowded areas and tourist spots. The city has excellent emergency services and a visible police presence in most tourist areas.",
                "paris": "Paris is generally safe, but be cautious about pickpockets, especially in crowded tourist areas and on public transportation. Keep your belongings secure and be aware of common scams targeting tourists.",
                "new york": "New York City is much safer than it was decades ago. Still, stay alert, especially at night, and keep your valuables secure. Stick to well-lit, populated areas after dark.",
            }
            destination_lower = destination.lower()
            return safety_tips.get(destination_lower, f"{destination} is generally safe for tourists, but always exercise normal precautions as you would in any large city. Keep your belongings secure, be aware of your surroundings, and avoid isolated areas at night.")
        
        elif "weather" in user_input_lower or "climate" in user_input_lower:
            # Let the existing weather function handle this
            return None
        
        elif "currency" in user_input_lower or "money" in user_input_lower or "cash" in user_input_lower:
            currency_tips = {
                "london": "The UK uses the British Pound (£). Credit cards are widely accepted, but it's good to have some cash for small purchases. ATMs are widely available throughout London.",
                "paris": "France uses the Euro (€). Credit cards are accepted in most places, but some small shops and markets may prefer cash. ATMs are readily available throughout Paris.",
                "new york": "The US uses the US Dollar ($). Credit cards are accepted almost everywhere in New York. Tipping is customary for services (15-20% in restaurants).",
            }
            destination_lower = destination.lower()
            return currency_tips.get(destination_lower, f"Be sure to check the local currency for {destination} before your trip. Major credit cards are widely accepted in most tourist destinations, but it's always good to have some local currency for small purchases and places that don't accept cards.")
    
    # If none of the specific conditions match, return None to let the main response handling take over
    return None

# Define the Streamlit app UI
st.title("Travel Agent 🌍✈️")

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Function to clear session state
def clear_session():
    st.session_state.messages = []
    st.session_state.travel_info = {
        "destination": "",
        "starting_location": "",
        "budget": "",
        "duration": "",
        "dates": "",
        "purpose": "",
        "preferences": [],
        "dietary_preferences": "",
        "mobility_concerns": "",
        "accommodation_preferences": ""
    }
    st.session_state.itinerary = ""

# Add a button to clear the chat history
if st.button("Start New Conversation"):
    clear_session()
    st.experimental_rerun()

# Display the itinerary if it exists
if st.session_state.itinerary:
    with st.expander("Your Travel Itinerary", expanded=True):
        st.markdown(st.session_state.itinerary)

# Replace the expandable section with a download button
if st.session_state.itinerary:
    # Create a download button for the itinerary
    st.download_button(
        label="Download Your Itinerary",
        data=st.session_state.itinerary,
        file_name=f"{st.session_state.travel_info.get('destination', 'Travel')}_Itinerary.md",
        mime="text/markdown",
    )

# Accept user input
if prompt := st.chat_input("How can I help plan your next trip?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # Extract travel information from the user's messages
    user_messages = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
    travel_info = extract_info_directly(user_messages)
    
    # New print for debugging extraction
    print("Extracted travel info:", travel_info)
    
    # Track if any new info was provided in this message
    new_info_provided = False
    duration_just_provided = False
    
    # Update session state with the extracted travel info
    for key, value in travel_info.items():
        if value and st.session_state.travel_info.get(key) != value:  # Only update if new or changed value
            print(f"Updating {key} from '{st.session_state.travel_info.get(key)}' to '{value}'")
            st.session_state.travel_info[key] = value
            new_info_provided = True
            if key == "duration":
                duration_just_provided = True
    
    # Check if an itinerary has been generated already
    itinerary_exists = bool(st.session_state.itinerary)
    
    # RESPONSE PRIORITY LOGIC
    # 1. Weather queries
    # 2. Just provided duration with destination -> generate itinerary
    # 3. Conversational responses for destinations
    # 4. Special queries about attractions, restaurants, etc.
    # 5. Handling missing required information
    
    # Check for direct weather queries first (high priority)
    weather_words = ["weather", "whether", "temperature", "climate", "rain", "sunny", "forecast"]
    is_weather_query = any(word in prompt.lower() for word in weather_words)
    
    if is_weather_query:
        # Extract location from weather query if not using the destination from travel_info
        query_location = None
        prompt_words = prompt.lower().split()
        prepositions = ["in", "at", "for", "of"]
        
        for i, word in enumerate(prompt_words):
            if word in prepositions and i < len(prompt_words) - 1:
                possible_location = prompt_words[i+1].capitalize()
                # Check if this is a known city or location
                if possible_location.lower() in [city.lower() for city in SUPPORTED_DESTINATIONS]:
                    query_location = possible_location
                # If it's a multi-word city, try to combine
                elif i < len(prompt_words) - 2:
                    possible_multi_location = f"{prompt_words[i+1]} {prompt_words[i+2]}".title()
                    if possible_multi_location.lower() in [city.lower() for city in ["new york", "san francisco", "los angeles"]]:
                        query_location = possible_multi_location
                        
        location = query_location or st.session_state.travel_info.get('destination', '')
        if location:
            # Get weather info and respond directly
            response = get_weather(location)
        else:
            response = "Which city would you like to know the weather for?"
            
    # If user just provided duration and we have destination -> generate itinerary (second priority)
    elif duration_just_provided and st.session_state.travel_info.get('destination') and not itinerary_exists:
        print("User provided duration and we have destination. Generating itinerary immediately!")
        
        # Set default budget if not provided
        if not st.session_state.travel_info.get('budget'):
            st.session_state.travel_info['budget'] = 'moderate'
            
        # Generate the itinerary
        itinerary = generate_recommendations()
        st.session_state.itinerary = itinerary
        
        # Display the itinerary directly in the chat
        with st.chat_message("assistant"):
            st.markdown(itinerary)
            
        st.session_state.messages.append({"role": "assistant", "content": itinerary})
        
        # No need for additional response as the itinerary is now the response
        response = None
        
    # Check if this is a message that looks like a duration specification (3rd priority backup)
    elif (len(prompt.strip().split()) <= 3 and 
          re.search(r'\b\d+\s*(?:day|days)?\b', prompt.lower()) and 
          st.session_state.travel_info.get('destination') and 
          not itinerary_exists):
        
        print("Simple duration message detected. Generating itinerary via regex pattern match.")
        
        # Set default budget if not provided
        if not st.session_state.travel_info.get('budget'):
            st.session_state.travel_info['budget'] = 'moderate'
            
        # Generate the itinerary
        itinerary = generate_recommendations()
        st.session_state.itinerary = itinerary
        
        # Display the itinerary directly in the chat
        with st.chat_message("assistant"):
            st.markdown(itinerary)
            
        st.session_state.messages.append({"role": "assistant", "content": itinerary})
        
        # No need for additional response as the itinerary is now the response
        response = None
        
    # Try to generate a conversational response (4th priority)
    else:
        conversational_response = generate_conversational_response(prompt, st.session_state.travel_info, itinerary_exists)
        
        if conversational_response:
            response = conversational_response
            
        # If no conversational response was generated, follow specific logic
        else:
            # First check if we're missing essential travel information
            essential_info = ["destination", "duration"]  # Don't require budget, can default
            missing_info = [info for info in essential_info if not st.session_state.travel_info[info]]
            
            if missing_info:
                # Ask for missing information with more varied language
                if "destination" in missing_info:
                    responses = [
                        "Where would you like to travel to? I can help with detailed information for destinations like: ",
                        "Which city are you interested in visiting? I have great information about: ",
                        "I'd be happy to help plan your trip! Where are you heading? I know a lot about: "
                    ]
                    response = random.choice(responses) + ", ".join([city.title() for city in SUPPORTED_DESTINATIONS])
                elif "duration" in missing_info:
                    # If we have destination but need duration, ask specifically about it
                    destination = st.session_state.travel_info['destination']
                    responses = [
                        f"How long are you planning to stay in {destination}?",
                        f"How many days will you be spending in {destination}?",
                        f"What's the duration of your trip to {destination}?"
                    ]
                    response = random.choice(responses)
            
            # Handle specialized queries when we already have the basic info
            elif any(word in prompt.lower() for word in ["attraction", "visit", "see", "museum", "landmark", "sight"]):
                attractions = search_attractions(st.session_state.travel_info['destination'], ",".join(st.session_state.travel_info.get('preferences', [])))
                response = "Here are some top attractions I recommend:\n\n" + "\n".join([f"- {attraction}" for attraction in attractions[:5]])
                
            elif any(word in prompt.lower() for word in ["restaurant", "food", "eat", "dining", "cuisine", "meal"]):
                restaurants = search_restaurants(st.session_state.travel_info['destination'], st.session_state.travel_info.get('dietary_preferences', ''))
                response = "Here are some restaurants you might enjoy:\n\n" + "\n".join([f"- {restaurant}" for restaurant in restaurants[:5]])
                
            elif any(word in prompt.lower() for word in ["hotel", "stay", "accommodation", "lodging", "place to sleep"]):
                accommodations = search_accommodations(st.session_state.travel_info['destination'], st.session_state.travel_info.get('accommodation_preferences', 'moderate'))
                response = "Here are some accommodation options I recommend:\n\n" + "\n".join([f"- {accommodation}" for accommodation in accommodations[:5]])
                
            elif "expandable" in prompt.lower() or "section" in prompt.lower() or "showing" in prompt.lower() or "see" in prompt.lower() and "itinerary" in prompt.lower():
                # If user can't see the expandable section, show the itinerary directly
                if st.session_state.itinerary:
                    response = "I'll show your itinerary right here:\n\n" + st.session_state.itinerary
                else:
                    response = "I don't have an itinerary generated yet. Let me know your destination and how many days you'll be staying."
                
            elif "better" in prompt.lower() and "conversation" in prompt.lower() or "feedback" in prompt.lower() or "not working" in prompt.lower() or "issue" in prompt.lower():
                # Handle feedback about the app
                response = "I understand there's an issue with viewing the itinerary. I'll fix that by showing your itinerary directly in our chat instead of in a separate section. Let me know if you'd like to see your current itinerary."
                
            # Generate itinerary if we have all needed information and none exists yet
            elif not itinerary_exists:
                # Set default budget if not provided
                if not st.session_state.travel_info.get('budget'):
                    st.session_state.travel_info['budget'] = 'moderate'
                    
                # Generate the itinerary
                itinerary = generate_recommendations()
                st.session_state.itinerary = itinerary
                
                # Display the itinerary directly in the chat
                with st.chat_message("assistant"):
                    st.markdown(itinerary)
                    
                st.session_state.messages.append({"role": "assistant", "content": itinerary})
                
                # No need for additional response as the itinerary is now the response
                response = None
                
            # If we already have an itinerary, handle simple acknowledgments or questions
            else:
                # If user is giving a simple acknowledgment
                if len(prompt.strip().split()) <= 2 and any(word in prompt.lower() for word in ["ok", "sure", "yes", "thanks", "good", "great"]):
                    follow_up_questions = [
                        f"Great! Is there any part of the {st.session_state.travel_info['destination']} itinerary you'd like me to explain in more detail?",
                        f"Perfect. Would you like suggestions for local transportation in {st.session_state.travel_info['destination']}?",
                        f"Excellent! Would you like some tips about local customs or etiquette in {st.session_state.travel_info['destination']}?"
                    ]
                    response = random.choice(follow_up_questions)
                
                # Default response for other queries when we already have an itinerary
                else:
                    destination = st.session_state.travel_info['destination']
                    follow_up_questions = [
                        f"Is there anything specific about your {destination} trip you'd like to know more about?",
                        f"Would you like recommendations for shopping or souvenirs in {destination}?",
                        f"Can I help you with information about the local language or useful phrases for {destination}?"
                    ]
                    response = random.choice(follow_up_questions)
    
    # Display assistant response in chat message container (if we have one)
    if response:
        with st.chat_message("assistant"):
            st.markdown(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
