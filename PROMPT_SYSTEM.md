# AI Travel Agent Prompt System Documentation

This document provides a detailed explanation of the multi-step prompt system used in the AI Travel Agent application, including real examples of each prompt type.

## Overview

The AI Travel Agent uses a sophisticated prompt system to guide users through the travel planning process. The system consists of four main prompt types:

1. Information Extraction
2. Proactive Clarification
3. Curated Suggestions
4. Itinerary Generation

Each prompt type serves a specific purpose in the conversation flow and helps create a personalized travel planning experience.

## 1. Information Extraction Prompt

### Purpose
Extract key travel details from user messages to build a comprehensive travel profile.

### Implementation
The extraction process uses regex pattern matching, keyword identification, and natural language processing to identify travel parameters such as destination, budget, duration, and preferences.

### Example

**System Prompt:**
```
Extract travel information from the following conversation:
{user_messages}

Extract the following details:
- destination: The main travel destination
- budget: Budget level (low, moderate, high)
- duration: Duration of the trip in days
- dates: Travel dates if specified
- purpose: Purpose of travel (leisure, business, etc.)
- preferences: List of travel preferences (museums, nature, food, etc.)
- dietary_preferences: Any dietary restrictions or preferences
- mobility_concerns: Any mobility issues or walking limitations
- accommodation_preferences: Preferred accommodation type

Format your response as JSON.
```

**User Input:**
"I'm planning a trip to Paris for 5 days in March. I love art and history, and I'm vegetarian. I prefer moderate hotels."

**Extracted Information:**
```json
{
  "destination": "Paris",
  "budget": "moderate",
  "duration": "5",
  "dates": "March",
  "purpose": "leisure",
  "preferences": ["art", "history"],
  "dietary_preferences": "vegetarian",
  "mobility_concerns": "",
  "accommodation_preferences": "moderate hotels"
}
```

## 2. Proactive Clarification Prompt

### Purpose
Identify missing key information and proactively ask users to provide it, ensuring a complete travel profile.

### Implementation
The system analyzes the travel_info dictionary for empty or missing values, then generates appropriate questions to fill these gaps.

### Example

**System Logic:**
```python
# Check if destination is provided but duration is missing
if travel_info["destination"] and not travel_info["duration"]:
    return f"How many days are you planning to spend in {travel_info['destination']}? This will help me create a better itinerary for you."
```

**When User Says:**
"I want to visit London."

**Assistant Response:**
"How many days are you planning to spend in London? This will help me create a better itinerary for you."

**When User Has Multiple Missing Fields:**
"I'm going to Rome."

**Assistant Response:**
"To create a better itinerary for Rome, could you tell me how many days you'll be staying, your budget level (low, moderate, or high), and activities you're interested in (art, history, food, etc.)?"

## 3. Curated Suggestions Prompt

### Purpose
Present focused recommendations before creating a full itinerary, allowing users to refine their preferences.

### Implementation
The system retrieves destination-specific information using web searches and formats it into a helpful overview.

### Example

**System Logic:**
```python
# Generate curated suggestions for a destination
suggestion_text = f"## Curated Suggestions for {destination}\n\n"

# Add attractions based on preferences
suggestion_text += "### Top Attractions\n"
attractions = search_attractions(destination)
suggestion_text += attractions + "\n\n"

# Add restaurant and accommodation suggestions
# ...
```

**When User Says:**
"I want to plan a trip to Tokyo."

**Assistant Response:**
```
## Curated Suggestions for Tokyo

### Top Attractions
Tokyo's attractions include the Tokyo Skytree, Senso-ji Temple, Meiji Shrine, Shibuya Crossing, Tokyo Disneyland, Ueno Park, and the Imperial Palace. Don't miss the vibrant neighborhoods of Shinjuku, Harajuku, and Akihabara.

### Recommended Dining Options
Tokyo has more Michelin-starred restaurants than any other city globally. From sushi at Tsukiji Market to izakaya pubs, ramen shops, and department store food halls, the options are endless. Try conveyor belt sushi, yakitori, tempura, and don't miss the unique themed cafes in Akihabara and Harajuku.

### Best Places to Stay
Tokyo's accommodations range from luxury hotels to traditional ryokans and capsule hotels. Shinjuku and Shibuya are ideal for first-time visitors, while Tokyo Station area offers convenient transportation. Budget travelers should consider business hotels like Tokyu Stay or capsule hotels. For a luxury experience, try the Park Hyatt or Aman Tokyo.

Would you like me to create a detailed day-by-day itinerary based on these suggestions? Just let me know how many days you'll be staying, and I'll customize it for you.
```

## 4. Itinerary Generation Prompt

### Purpose
Create a comprehensive day-by-day travel plan that incorporates all user preferences and requirements.

### Implementation
The system synthesizes all gathered information to create a logical schedule with morning, afternoon, and evening activities adjusted for user preferences, dietary needs, and mobility concerns.

### Example

**System Logic:**
```python
# Build the itinerary
itinerary = f"# {duration}-Day Itinerary for {destination}\n\n"

# Add sections for weather, preferences, etc.
# ...

# Create daily breakdown
itinerary += "## Daily Itinerary\n"

# Adjust itinerary based on user needs
has_mobility_issues = mobility_concerns and any(term in mobility_concerns.lower() 
                     for term in ["wheelchair", "mobility", "walking", "stairs"])
```

**When User Says:**
"Yes, please create an itinerary for 3 days in Paris. I love art and I'm vegetarian."

**Assistant Response:**
```
# 3-Day Itinerary for Paris

## Current Weather
Weather in Paris: light rain, Temperature: 8.5°C, Humidity: 93%, Wind Speed: 2.57 m/s

## Budget Level
Moderate

## Your Preferences
Art

## Dietary Preferences
Vegetarian

### Restaurant Recommendations for Your Dietary Needs
Vegetarian options in Paris include Hank Vegan Burger, Le Grenier de Notre-Dame, and Le Potager du Marais. Many regular restaurants also offer vegetarian options - just ask.

## Daily Itinerary

### Day 1: Eiffel Tower & Champs-Élysées
**Morning:** Arrive and check into your accommodation. Have a croissant and coffee at a local café to start your Parisian experience.

**Afternoon:** Visit the iconic Eiffel Tower (€19.40 for elevator access to the top). Pro tip: Book tickets online in advance to avoid long lines. Afterward, stroll through Champ de Mars gardens for great photo opportunities.

**Evening:** Enjoy dinner at Hank Vegan Burger or Le Potager du Marais, both offering excellent vegetarian and vegan options in central Paris.

### Day 2: Louvre & Tuileries
**Morning:** Visit the Louvre Museum when it opens (9am) to see the Mona Lisa with fewer crowds (€17 admission). Focus on major works like Venus de Milo and Winged Victory if you're short on time.

**Afternoon:** Have lunch at Café Marly with views of the Louvre pyramid. After lunch, stroll through Tuileries Garden and visit Musée de l'Orangerie to see Monet's Water Lilies (€12.50).

**Evening:** Dine in the vibrant Le Marais district at Breizh Café for excellent vegetarian galettes or try Le Potager du Marais for traditional French dishes prepared vegetarian-style.

### Day 3: Montmartre & Sacré-Cœur
**Morning:** Explore the artistic neighborhood of Montmartre. Visit Sacré-Cœur Basilica (free entry) for panoramic city views and explore the artists' square at Place du Tertre.

**Afternoon:** Have lunch at La Maison Rose, a picturesque pink café with vegetarian options. Visit the Salvador Dalí Museum (€13) and walk past the famous Moulin Rouge.

**Evening:** Enjoy a final dinner at Soya, a trendy vegetarian restaurant in the 11th arrondissement offering creative plant-based cuisine in a beautiful setting.

## Personalized Recommendations Based on Your Preferences

**Art:** For art lovers in Paris, don't miss the Louvre and Musée d'Orsay, but also consider the Pompidou Center for modern art, Musée de l'Orangerie for Monet's Water Lilies, and the Rodin Museum for sculpture. The artists' square at Place du Tertre in Montmartre is perfect for seeing artists at work and perhaps purchasing an original piece.

## Transportation Tips
The Paris Metro is extensive and easy to use. Consider purchasing a 'carnet' of 10 tickets (€16.90) or a Paris Visite pass for unlimited travel. For day trips, use the RER commuter trains.

## Budget Tips
- Mix high-end attractions with free activities
- Consider mid-range hotels or vacation rentals
- Try a mix of restaurants, from casual to nicer establishments
- Look for city passes that include multiple attractions
```

## Prompt Chaining Logic

The prompts work together in a strategic sequence:

1. **Initial Extraction**: When a user first mentions travel plans, information extraction identifies key details.
2. **Clarification**: If essential information is missing, clarification prompts ask for specific details.
3. **Suggestion Phase**: Once enough information is available, curated suggestions are presented.
4. **Itinerary Creation**: After user feedback on suggestions, a detailed itinerary is generated.

This multi-step approach ensures that users receive increasingly personalized recommendations as more information becomes available, creating a natural conversation flow that mimics human travel planning assistance.

## Handling Edge Cases

The prompt system includes special handling for:

- **Vague Inputs**: "I want to go somewhere nice" → "What kind of destination interests you? Beach, city, mountains, or something else?"
- **Unsupported Destinations**: "I want to go to [unsupported city]" → "I don't have detailed information about that destination yet. Here are destinations I can help with..."
- **Comparison Requests**: "Compare Paris and London" → Structured comparison of weather, attractions, dining, etc.
- **Special Requirements**: Dietary restrictions and mobility concerns are seamlessly incorporated into recommendations

## Conclusion

The AI Travel Agent's prompt system combines structured data extraction with conversational flexibility to create a helpful, personalized travel planning experience. By progressively building a profile of the traveler's needs and preferences, it can provide increasingly tailored recommendations that consider practical aspects like accessibility and dietary requirements while focusing on the traveler's interests and budget. 