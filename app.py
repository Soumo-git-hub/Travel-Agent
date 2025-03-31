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
GEMINI_API_KEY = st.secrets.get("google", {}).get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

# Define the LLM mode - options: "google", "local"
LLM_MODE = st.secrets.get("general", {}).get("LLM_MODE", os.getenv("LLM_MODE", "google")).lower()

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
    """Perform a web search and return structured results"""
    if not query or not query.strip():
        return []
        
    try:
        # Perform the search
        search_results = []
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
        ]
        
        # Use a simple cache mechanism to avoid duplicate searches
        if "search_cache" not in st.session_state:
            st.session_state.search_cache = {}
        
        # Check cache first
        cache_key = f"{query}_{num_results}"
        if cache_key in st.session_state.search_cache:
            print("Using cached search result")
            return st.session_state.search_cache[cache_key]
        
        # Perform the search with the correct parameters
        search_urls = list(search(query, num_results=num_results))
        
        for url in search_urls:
            try:
                # Get the webpage content with increased timeout and rotating user agents
                headers = {'User-Agent': random.choice(user_agents)}
                response = requests.get(url, timeout=timeout, headers=headers)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Get title
                    title = soup.title.string if soup.title else url
                    title = re.sub(r'\s*\|.*$', '', title)  # Remove website name
                    title = re.sub(r'\s*-\s*.*$', '', title)  # Remove separator and rest
                    
                    # Get description
                    description = ""
                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                    if meta_desc:
                        description = meta_desc.get('content', '')
                    else:
                        # Try to get first paragraph
                        p = soup.find('p')
                        if p:
                            description = p.text[:200] + "..."
                    
                    # Clean up description
                    description = re.sub(r'Visit.*?\.com', '', description, flags=re.IGNORECASE)
                    description = re.sub(r'https?://.*$', '', description)
                    description = re.sub(r'www\..*$', '', description)
                    
                    if title and description and len(title) > 5:
                        search_results.append({
                            'title': title.strip(),
                            'url': url,
                            'description': description.strip()
                        })
            except requests.Timeout:
                print(f"Timeout while processing URL {url}")
                continue
            except Exception as e:
                print(f"Error processing URL {url}: {str(e)}")
                continue
            
            # Add a small delay to avoid rate limiting
            time.sleep(random.uniform(1.5, 2.5))  # Randomized delay between 1.5-2.5 seconds
        
        # Cache the result
        st.session_state.search_cache[cache_key] = search_results
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
def get_weather(location, date=None):
    """Get weather information for a location. If date is not provided, current weather is returned."""
    try:
        # Clean up location name
        location = location.split(' Is A Great Choice')[0].strip()
        location = location.split(' For')[0].strip()  # Remove 'For' suffix
        
        if not location:
            return "Please specify a city name to get weather information."
        
        # Check if date is in the future but within 5 days
        future_date = False
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                days_diff = (date_obj - datetime.now()).days
                future_date = days_diff > 5
            except ValueError:
                return f"Invalid date format. Please use YYYY-MM-DD format."
        
        if not date or not future_date:
            # Current weather or weather for next 5 days
            # Try with country code first
            urls = [
                f"https://api.openweathermap.org/data/2.5/weather?q={location},IN&appid={OPENWEATHER_API_KEY}&units=metric",  # Try with India country code
                f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHER_API_KEY}&units=metric"  # Try without country code
            ]
            
            for url in urls:
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        weather = {
                            "location": location,
                            "temperature": data["main"]["temp"],
                            "description": data["weather"][0]["description"],
                            "humidity": data["main"]["humidity"],
                            "wind_speed": data["wind"]["speed"],
                            "feels_like": data["main"]["feels_like"]
                        }
                        return f"Weather in {location}: {weather['description']}, Temperature: {weather['temperature']}°C (feels like {weather['feels_like']}°C), Humidity: {weather['humidity']}%, Wind Speed: {weather['wind_speed']} m/s"
                    elif response.status_code == 404:
                        continue  # Try next URL if this one fails
                    else:
                        print(f"Weather API error: Status code {response.status_code}")
                except requests.RequestException as e:
                    print(f"Request error for weather API: {str(e)}")
            
            return f"Unable to fetch weather data for {location}. Please check if the city name is correct."
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
        r"(?:visit|travel to|going to|planning a trip to|vacation in|holiday in|trip to)\s+([a-zA-Z\s,]+)"
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
                if word not in cleaned_words and word.lower() not in ['for', 'is', 'a', 'great', 'choice', 'and', 'the', 'to']:
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
            
            # Skip results that are likely not attractions
            if any(term in title.lower() for term in excluded_terms):
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
            return [f"No specific attraction information found for {destination}. Here are some general recommendations:\n" +
                   "- Visit the city's main landmarks and historical sites\n" +
                   "- Explore local museums and cultural centers\n" +
                   "- Check out popular parks and gardens\n" +
                   "- Experience local markets and shopping areas"]
    
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
        query = f"Best restaurants in {destination}"
        if dietary_preferences:
            query = f"Best {dietary_preferences} restaurants in {destination}"
        
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
            
            # Check if this is likely a restaurant
            is_restaurant = any(keyword in title.lower() or keyword in description.lower() for keyword in restaurant_keywords)
            
            if title and description and len(title) > 5 and is_restaurant:
                # Clean up the title and description
                title = re.sub(r'\s*\|.*$', '', title)
                title = re.sub(r'\s*-\s*.*$', '', title)
                
                formatted_restaurant = f"{title} - {description}"
                formatted_restaurants.append(formatted_restaurant)
        
        if formatted_restaurants:
            return formatted_restaurants
        else:
            return [f"No specific restaurant information found for {destination}. Here are some general recommendations:\n" +
                   "- Try local cuisine at traditional restaurants\n" +
                   "- Visit popular food markets and street food areas\n" +
                   "- Check out cafes and casual dining spots\n" +
                   "- Look for restaurants with good reviews on major platforms"]
    
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
    """Generate travel recommendations based on collected information with improved formatting."""
    try:
        destination = st.session_state.travel_info['destination']
        duration = st.session_state.travel_info.get('duration', '5 days')
        budget = st.session_state.travel_info.get('budget', 'moderate')
        preferences = st.session_state.travel_info.get('preferences', [])
        special_interests = st.session_state.travel_info.get('special_interests', [])
        travel_date = st.session_state.travel_info.get('travel_date', '')
        accessibility_needs = st.session_state.travel_info.get('accessibility_needs', '')
        dietary_preferences = st.session_state.travel_info.get('dietary_preferences', '')
        
        # Clean up destination name
        destination = destination.split(' Is A Great Choice')[0].strip()
        destination = destination.split(' For')[0].strip()
        
        # Get weather info
        weather_info = get_weather(destination)
        
        # Get attractions, restaurants, and accommodations
        if accessibility_needs:
            attractions = search_accessible_attractions(destination)
        else:
            attractions = search_attractions(destination, ",".join(preferences))
            
        restaurants = search_restaurants(destination, dietary_preferences)
        accommodations = search_accommodations(destination, st.session_state.travel_info.get('accommodation_preferences', 'moderate'))
        
        # Get special interest activities if any
        special_activities = []
        for interest in special_interests:
            activities = search_special_interest(destination, interest)
            special_activities.extend(activities[:2])  # Add top 2 activities for each interest
        
        # Create the itinerary with improved formatting
        itinerary = f"# Your {duration} Itinerary for {destination.title()}\n\n"
        
        # Add travel date if available
        if travel_date:
            itinerary += f"**Travel Month:** {travel_date}\n\n"
        
        # Add weather info
        itinerary += f"## Current Weather\n{weather_info}\n\n"
        
        # Add budget level
        itinerary += f"## Budget Level\n{budget.title() if budget else 'Not specified'}\n\n"
        
        # Add preferences section
        if preferences:
            itinerary += "## Your Interests\n"
            for preference in preferences:
                itinerary += f"- {preference.title()}\n"
            itinerary += "\n"
        
        # Add dietary preferences if specified
        if dietary_preferences:
            itinerary += f"## Dietary Preferences\n{dietary_preferences.title()}\n\n"
        
        # Add accessibility information if needed
        if accessibility_needs:
            itinerary += f"## Accessibility Information\n"
            itinerary += f"This itinerary includes wheelchair-accessible attractions and recommendations.\n\n"
        
        # Add day-by-day itinerary
        itinerary += "## Day-by-Day Itinerary\n\n"
        num_days = int(duration.split()[0])
        
        for day in range(1, num_days + 1):
            itinerary += f"### Day {day}\n"
            
            # Morning activities
            itinerary += "**Morning:**\n"
            morning_attractions = attractions[day-1:day+1] if day <= len(attractions) else []
            for attraction in morning_attractions:
                itinerary += f"- {attraction}\n"
            if not morning_attractions:
                itinerary += "- Start your day with a visit to a local café\n"
                itinerary += "- Explore the city's historic district\n"
            
            # Afternoon activities
            itinerary += "\n**Afternoon:**\n"
            afternoon_attractions = attractions[day+1:day+3] if day+1 < len(attractions) else []
            
            # Add special interest activities if available
            if special_activities and day <= len(special_activities):
                afternoon_attractions = [special_activities[day-1]] + afternoon_attractions
                
            for attraction in afternoon_attractions:
                itinerary += f"- {attraction}\n"
            if not afternoon_attractions:
                itinerary += "- Visit a local museum or art gallery\n"
                itinerary += "- Take a guided walking tour\n"
            
            # Evening activities
            itinerary += "\n**Evening:**\n"
            evening_restaurant = restaurants[day-1] if day <= len(restaurants) else restaurants[0] if restaurants else "No specific restaurant recommendation"
            itinerary += f"- Dinner at: {evening_restaurant}\n"
            itinerary += "- Enjoy a night walk along the city's landmarks\n"
            itinerary += "- Experience local nightlife or entertainment\n"
            
            itinerary += "\n"
        
        # Add general recommendations
        itinerary += "## Additional Recommendations\n\n"
        
        # Add attractions section with descriptions
        itinerary += "### Key Attractions\n"
        for attraction in attractions[:5]:
            itinerary += f"- {attraction}\n"
        itinerary += "\n"
        
        # Add restaurants section with descriptions
        itinerary += "### Recommended Restaurants\n"
        for restaurant in restaurants[:5]:
            itinerary += f"- {restaurant}\n"
        itinerary += "\n"
        
        # Add accommodations section with descriptions
        itinerary += "### Accommodation Options\n"
        for accommodation in accommodations[:3]:
            itinerary += f"- {accommodation}\n"
        
        # Add special interest section if applicable
        if special_interests:
            itinerary += "\n### Special Interest Activities\n"
            for activity in special_activities:
                itinerary += f"- {activity}\n"
        
        # Add transportation tips
        itinerary += "\n### Transportation Tips\n"
        itinerary += "- Consider purchasing a local transportation pass for convenience\n"
        itinerary += "- Use ride-sharing apps for destinations not easily accessible by public transport\n"
        itinerary += "- Download offline maps before your trip\n"
        
        # Add budget breakdown with more detailed estimates
        itinerary += "\n### Estimated Budget Breakdown\n"
        
        # Calculate rough budget estimates based on budget level and destination
        budget_multipliers = {"low": 0.7, "moderate": 1.0, "high": 1.5}
        multiplier = budget_multipliers.get(budget, 1.0)
        
        # Base costs (these would ideally be adjusted based on destination research)
        accommodation_cost = 100 * multiplier  # per night
        food_cost = 50 * multiplier  # per day
        activities_cost = 30 * multiplier  # per day
        transport_cost = 20 * multiplier  # per day
        
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
        
        # Add practical tips
        itinerary += "\n### Practical Tips\n"
        itinerary += "- Keep a copy of your passport and important documents\n"
        itinerary += "- Learn basic phrases in the local language\n"
        itinerary += "- Download offline maps and translation apps\n"
        itinerary += "- Keep emergency contact numbers handy\n"
        itinerary += "- Check local customs and dress codes\n"
        
        return itinerary
        
    except Exception as e:
        print(f"Error generating recommendations: {str(e)}")
        return "I apologize, but I encountered an error while generating your travel recommendations. Please try again."

# Improved function to generate conversational responses
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
    
    # If this is a new conversation and we don't have destination yet
    if not destination and ("hi" in user_input_lower or "hello" in user_input_lower or len(user_input_lower) < 20):
        return random.choice(greetings) + " Where would you like to travel to?"
    
    # If we have all the necessary information, generate itinerary
    if (destination and 
        travel_info.get('duration') and 
        not itinerary_generated and 
        len(user_input_lower.split()) > 10):  # More detailed message
        
        # Generate the itinerary
        itinerary = generate_recommendations()
        st.session_state.itinerary = itinerary
        
        return "I've generated your travel itinerary! You can find it above. Would you like to know more about any specific aspect of your trip?"
    
    # If user just provided their destination
    if destination and ("visit" in user_input_lower or "travel to" in user_input_lower or "going to" in user_input_lower):
        return f"{destination} is a great choice! To help you plan better, could you tell me:\n\n" + \
               "1. How many days are you planning to stay?\n" + \
               "2. What's your budget level (low, moderate, or high)?\n" + \
               "3. What interests you most about this destination? (e.g., food, culture, history, nature)"
    
    # If user provided destination but no duration
    if destination and not travel_info.get('duration') and not "day" in user_input_lower:
        return f"Great! {destination} has a lot to offer. To create a personalized itinerary, I need to know:\n\n" + \
               "1. How many days are you planning to stay?\n" + \
               "2. What's your budget level (low, moderate, or high)?\n" + \
               "3. What interests you most about this destination?"
    
    # If user provided destination and duration but no preferences
    if destination and travel_info.get('duration') and not travel_info.get('preferences') and not itinerary_generated:
        return f"I'll help you plan your {travel_info.get('duration')} trip to {destination}. To create a personalized itinerary, could you share some of your interests or preferences? For example:\n\n" + \
               "- Are you interested in history, art, or culture?\n" + \
               "- Do you enjoy food experiences and trying local cuisine?\n" + \
               "- Are you interested in nature, shopping, or nightlife?\n" + \
               "- Do you have any dietary preferences or restrictions?\n" + \
               "- Are there any specific attractions you'd like to visit?"
    
    # If asking about specific topics after itinerary was generated
    if itinerary_generated:
        if "transport" in user_input_lower or "getting around" in user_input_lower:
            return f"Getting around {destination} is relatively straightforward. Here are some transportation tips:\n\n" + \
                   "- Public transportation is usually the most efficient option\n" + \
                   "- Consider purchasing a multi-day pass for convenience\n" + \
                   "- Download local transportation apps before your trip\n" + \
                   "- Keep some cash handy for taxis or smaller transit options\n\n" + \
                   "Would you like more specific information about transportation options?"
        elif "safety" in user_input_lower or "safe" in user_input_lower:
            return f"{destination} is generally safe for tourists, but here are some important safety tips:\n\n" + \
                   "- Keep your belongings secure and be aware of your surroundings\n" + \
                   "- Avoid isolated areas at night\n" + \
                   "- Keep emergency contact numbers handy\n" + \
                   "- Make copies of important documents\n" + \
                   "- Follow local customs and dress codes"
        elif "weather" in user_input_lower or "climate" in user_input_lower:
            return None  # Let the existing weather function handle this
        elif "currency" in user_input_lower or "money" in user_input_lower:
            return f"Here's what you need to know about money in {destination}:\n\n" + \
                   "- Check the local currency and current exchange rates\n" + \
                   "- Major credit cards are widely accepted in most tourist areas\n" + \
                   "- Keep some local currency for small purchases\n" + \
                   "- ATMs are usually the best way to get local currency\n" + \
                   "- Inform your bank about your travel dates"
        elif "language" in user_input_lower or "speak" in user_input_lower:
            return f"Language tips for {destination}:\n\n" + \
                   "- Learn a few basic phrases in the local language\n" + \
                   "- Download a translation app for offline use\n" + \
                   "- English is widely spoken in tourist areas\n" + \
                   "- Keep a phrasebook or digital dictionary handy\n" + \
                   "- Even simple greetings in the local language are appreciated"
        elif "budget" in user_input_lower or "cost" in user_input_lower or "expensive" in user_input_lower:
            budget_level = travel_info.get('budget', 'moderate')
            if budget_level == "low":
                return f"Here are some budget-friendly tips for {destination}:\n\n" + \
                       "- Stay in hostels or budget hotels\n" + \
                       "- Use public transportation\n" + \
                       "- Eat at local markets and street food vendors\n" + \
                       "- Take advantage of free attractions and walking tours\n" + \
                       "- Look for student discounts if applicable"
            elif budget_level == "high":
                return f"{destination} offers many luxury experiences:\n\n" + \
                       "- 5-star hotels and luxury accommodations\n" + \
                       "- Fine dining restaurants\n" + \
                       "- Private tours and exclusive experiences\n" + \
                       "- High-end shopping opportunities\n" + \
                       "- Premium transportation options"
            else:
                return f"With a moderate budget in {destination}, you can:\n\n" + \
                       "- Stay in comfortable mid-range hotels\n" + \
                       "- Mix local eateries with some upscale restaurants\n" + \
                       "- Experience most attractions without breaking the bank\n" + \
                       "- Use a combination of public transport and occasional taxis\n" + \
                       "- Find good value in guided tours and activities"
    
    # If user asks a vague question about where to go
    if any(phrase in user_input_lower for phrase in ["where should i go", "recommend a place", "good place to visit", "somewhere nice", "vacation ideas"]):
        return "I'd be happy to help you plan a vacation! To provide personalized recommendations, I need some information:\n\n" + \
               "1. What type of destination interests you?\n" + \
               "   - Beach destination\n" + \
               "   - City with cultural experiences\n" + \
               "   - Mountain retreat\n" + \
               "   - Historical sites\n" + \
               "   - Adventure destination\n\n" + \
               "2. How long are you planning to travel?\n\n" + \
               "3. What's your budget level (low, moderate, or high)?\n\n" + \
               "4. Any specific interests or requirements?\n" + \
               "   - Food experiences\n" + \
               "   - Art and culture\n" + \
               "   - Outdoor activities\n" + \
               "   - Shopping\n" + \
               "   - Nightlife"
    
    # If user mentions special requirements like accessibility
    if "wheelchair" in user_input_lower or "accessible" in user_input_lower or "disability" in user_input_lower:
        if destination:
            return f"I'll help you plan an accessible trip to {destination}. Here's what you should know:\n\n" + \
                   "- Many attractions have wheelchair access and facilities\n" + \
                   "- Public transportation often has accessibility features\n" + \
                   "- Hotels offer accessible rooms\n" + \
                   "- Many restaurants are wheelchair-friendly\n\n" + \
                   "Would you like me to focus on accessible attractions and transportation options in your itinerary?"
        else:
            return "I can help you plan an accessible trip. Many destinations have improved their accessibility features in recent years. To provide the best recommendations, could you tell me:\n\n" + \
                   "1. Where would you like to travel to?\n" + \
                   "2. How long are you planning to stay?\n" + \
                   "3. What's your budget level?\n" + \
                   "4. What interests you most about the destination?"
    
    # If user mentions dietary restrictions
    if any(diet in user_input_lower for diet in ["vegetarian", "vegan", "gluten-free", "food allergy", "dietary"]):
        if destination:
            return f"I'll make sure to include {travel_info.get('dietary_preferences', 'dietary-friendly')} restaurant recommendations for your trip to {destination}. Here's what you should know:\n\n" + \
                   "- Many restaurants now offer good options for various dietary needs\n" + \
                   "- Local markets often have fresh, suitable ingredients\n" + \
                   "- Some areas may have dedicated dietary-friendly restaurants\n" + \
                   "- It's helpful to learn how to communicate your dietary needs in the local language\n\n" + \
                   "Would you like me to create an itinerary with a focus on suitable dining options?"
        else:
            return "I can help you find destinations with great options for your dietary preferences. To provide the best recommendations, could you tell me:\n\n" + \
                   "1. Where would you like to travel to?\n" + \
                   "2. How long are you planning to stay?\n" + \
                   "3. What's your budget level?\n" + \
                   "4. What interests you most about the destination?"
    
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
                   "   - Adventure destination\n\n" + \
                   "2. How long are you planning to travel?\n\n" + \
                   "3. What's your budget level (low, moderate, or high)?\n\n" + \
                   "4. Any specific interests or requirements?\n" + \
                   "   - Food experiences\n" + \
                   "   - Art and culture\n" + \
                   "   - Outdoor activities\n" + \
                   "   - Shopping\n" + \
                   "   - Nightlife"
        
        # Handle single-word or very short responses
        if len(prompt.strip().split()) <= 2:
            if destination:
                return f"I can help you with information about {destination}. Would you like to know about:\n\n" + \
                       "1. Current weather conditions\n" + \
                       "2. Recommended hotels\n" + \
                       "3. Popular attractions\n" + \
                       "4. Restaurant recommendations\n" + \
                       "5. A complete day-by-day itinerary\n\n" + \
                       "Just let me know what interests you!"
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
                   "Just let me know what interests you!"
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
    if st.session_state.itinerary:
        st.download_button(
            label="Download Itinerary",
            data=st.session_state.itinerary,
            file_name="travel_itinerary.md",
            mime="text/markdown"
        )

with col3:
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
            # Add custom CSS for scrolling
            st.markdown("""
                <style>
                .itinerary-box {
                    height: 600px;
                    overflow-y: auto;
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    background-color: #f8f9fa;
                }
                </style>
                """, unsafe_allow_html=True)
            
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
    
    # Update travel info in session state, preserving existing values if not in new info
    for key, value in travel_info.items():
        if value:  # Only update if the new value is not empty
            st.session_state.travel_info[key] = value
    
    # Generate response based on the extracted information
    with chat_col:
        with st.chat_message("assistant"):
            response = generate_response(prompt, st.session_state.travel_info)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})