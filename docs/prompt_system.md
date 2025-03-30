# Prompt System Documentation

## System Overview

The AI Travel Agent uses a multi-stage prompt system designed to guide the conversation flow and generate personalized travel itineraries. Each prompt serves a specific purpose in the travel planning process and ensures that the user experience is both informative and helpful.

## 1. Information Extraction Prompt

### Purpose
Extract essential travel details from natural user conversation.

### System Prompt
```
Extract travel information from the following conversation:
{user_messages}

Extract the following details:
- destination: The main travel destination
- budget: Budget level (low, moderate, high)
- duration: Duration of the trip in days
- dates: Travel dates if specified
- preferences: List of travel preferences (museums, nature, food, etc.)
- dietary_preferences: Any dietary restrictions or preferences
- accommodation_preferences: Preferred accommodation type

Format your response as JSON.
```

### User Input Example
"I'm planning to visit Tokyo for 5 days with a moderate budget. I love trying local food and visiting technology museums."

### Model Response Example
```json
{
  "destination": "Tokyo",
  "budget": "moderate",
  "duration": "5",
  "dates": "",
  "preferences": ["local food", "technology museums"],
  "dietary_preferences": "",
  "accommodation_preferences": ""
}
```

### Process Explanation
This prompt analyzes the user's natural language input and extracts structured data points that will be used to personalize the travel recommendations. The system uses pattern recognition to identify key information without requiring the user to fill out forms.

## 2. Clarification Prompt

### Purpose
Identify missing critical information and proactively request it from the user.

### System Prompt
```
You are a helpful travel assistant. Based on the information provided so far, identify what key details are missing to create a personalized travel itinerary.

Current information:
- Destination: {destination}
- Duration: {duration}
- Budget: {budget}
- Preferences: {preferences}
- Dietary preferences: {dietary_preferences}
- Accommodation preferences: {accommodation_preferences}

Ask ONLY for the most important missing information. Prioritize destination, duration, and budget, then interests and preferences. Phrase your question conversationally.
```

### User Input Example
"I want to visit Tokyo."

### Model Response Example
"How many days are you planning to spend in Tokyo? Also, could you share what your budget range is (low, moderate, or high)? This will help me create a more tailored itinerary for you."

### Process Explanation
This prompt enables the system to maintain a natural conversation flow while gathering necessary information. Instead of bombarding users with questions, it strategically requests the most critical missing details based on what's already known.

## 3. Recommendation Prompt

### Purpose
Generate personalized attraction, restaurant, and accommodation recommendations based on user preferences.

### System Prompt
```
Create a list of tailored recommendations for {destination} based on the following user preferences:
- Budget: {budget}
- Interests: {preferences}
- Dietary preferences: {dietary_preferences}
- Accommodation preferences: {accommodation_preferences}

Use the following information to inform your recommendations:
{attractions_data}
{restaurants_data}
{accommodations_data}

Format your response with clear sections for attractions, dining, and accommodations. For each recommendation, include:
1. Name
2. Brief description
3. Why it matches the user's preferences
4. Approximate cost (if available)
```

### Web Search Integration
This prompt utilizes web search results to provide up-to-date information about attractions, restaurants, and accommodations, ensuring recommendations are current and accurate.

### User Input Example
"Show me some recommendations for Tokyo with my preferences."

### Model Response Example
```
## Recommendations for Tokyo

### Attractions
1. **TeamLab Borderless Digital Art Museum**
   - Immersive digital art experience with interactive installations
   - Perfect for your interest in technology and modern experiences
   - Admission: ¥3,200 (~$22)

2. **Akihabara Electric Town**
   - Technology district with electronics shops, gaming centers, and tech museums
   - Ideal for your technology interests
   - Free to explore (shopping costs vary)

3. **Tsukiji Outer Market**
   - Food paradise with vendors selling fresh seafood and local specialties
   - Great for your interest in local food
   - Varies based on what you eat (¥1,000-3,000 or $7-20 for a good meal)

### Restaurants
1. **Gonpachi Nishi-Azabu**
   - Famous restaurant known for inspiring the Kill Bill movie set
   - Offers a range of Japanese dishes with moderate pricing
   - Average meal: ¥3,000-5,000 ($20-35)

2. **Uobei Shibuya**
   - High-tech conveyor belt sushi restaurant with tablet ordering
   - Combines your interests in technology and food
   - Budget-friendly at ¥100-200 per plate ($0.70-1.40)

### Accommodations
1. **Mitsui Garden Hotel Ginza Premier**
   - Mid-range hotel with excellent city views and modern amenities
   - Centrally located with easy access to major attractions
   - ¥18,000-25,000 per night ($120-170)

2. **Wired Hotel Tokyo**
   - Tech-focused boutique hotel with modern design
   - Located in Asakusa with easy access to historical sites
   - ¥15,000-20,000 per night ($100-140)
```

### Process Explanation
This prompt combines user preferences with real-time data to create tailored recommendations. By searching for current information about the destination, the system ensures suggestions are relevant and accurate, while still aligning with the user's specific interests and budget constraints.

## 4. Itinerary Generation Prompt

### Purpose
Create a comprehensive day-by-day travel plan based on all gathered information.

### System Prompt
```
Create a detailed {duration}-day itinerary for {destination} with the following parameters:
- Budget level: {budget}
- Interests: {preferences}
- Dietary preferences: {dietary_preferences}
- Accommodation: {accommodation_preferences}

Use the following curated information:
{attractions_data}
{restaurants_data}
{accommodations_data}
{weather_data}

For each day, include:
1. Morning, afternoon, and evening activities
2. Recommended meal options that respect dietary preferences
3. Transportation between locations
4. Estimated costs for activities and meals
5. Practical tips relevant to that day's activities

Format the itinerary in a clear, readable way with day headers, timing information, and logically grouped activities based on proximity.
```

### User Input Example
"Please generate my Tokyo itinerary."

### Model Response Example
```
# 5-Day Tokyo Itinerary (Moderate Budget)

## Weather Forecast
Current weather in Tokyo: Clear sky, 18°C/64°F

## Day 1: Arrival & Tokyo Highlights

**Morning:**
- Arrive at Narita/Haneda Airport
- Purchase a 5-day Tokyo Metro pass (¥2,900/~$20)
- Check in to your hotel (Mitsui Garden Hotel Ginza Premier)

**Afternoon:**
- Visit Tokyo Skytree for panoramic city views (¥3,100/~$21)
- Explore Asakusa and Senso-ji Temple (Free)
- Try street food at Nakamise Shopping Street (¥1,000-2,000/~$7-14)

**Evening:**
- Dinner at Gonpachi Nishi-Azabu (¥3,000-5,000/~$20-35)
- Night views at Tokyo Metropolitan Government Building Observatory (Free)

**Transportation Tips:** Use your metro pass. The Asakusa Line connects many of today's destinations.

## Day 2: Technology & Modern Tokyo

**Morning:**
- TeamLab Borderless Digital Art Museum (¥3,200/~$22)
  *Book tickets online in advance to avoid long lines*

**Afternoon:**
- Lunch at Uobei Shibuya, high-tech conveyor belt sushi (¥1,500/~$10)
- Explore Akihabara Electric Town (Free to explore)
- Visit Tokyo Anime Center (Free)

**Evening:**
- Dinner at TY Harbor - modern restaurant with vegetarian options (¥4,000/~$27)
- Evening walk through illuminated Shibuya Crossing (Free)

**Transportation Tips:** Take the Yamanote Line between Shibuya and Akihabara. Most tech stores in Akihabara close around 8pm.

[Days 3-5 continue with similar detailed breakdown]

## Estimated Total Budget
- Accommodations: ¥75,000-100,000 ($510-680) for 5 nights
- Food: ¥30,000-45,000 ($200-300)
- Activities: ¥20,000-30,000 ($135-200)
- Transportation: ¥5,000-8,000 ($34-55)
- Total: Approximately ¥130,000-183,000 ($880-1,235)

## Money-Saving Tips
- Use your metro pass instead of taxis
- Many temples and gardens have free entry days
- Convenience stores (konbini) like 7-Eleven offer quality, affordable meals
- Look for lunch specials at restaurants that would be pricier for dinner
```

### Process Explanation
This prompt synthesizes all collected information to create a practical, day-by-day plan that respects the user's preferences, budget constraints, and logistical considerations. It organizes activities logically by location to minimize transit time and includes helpful tips to enhance the travel experience.

## Prompt Chaining Strategy

The system employs a strategic prompt chaining approach where each prompt builds upon information gathered by previous prompts:

1. **Initial Conversation** → Information Extraction Prompt
2. **Missing Information** → Clarification Prompt
3. **Sufficient Information** → Recommendation Prompt
4. **User Approval** → Itinerary Generation Prompt

This approach creates a natural conversation flow while efficiently collecting the information needed to provide personalized recommendations.

## Handling Flexible Inputs

The system can handle various input formats through:

- **Regex Pattern Matching**: Identifies dates, numbers, and destinations in different formats
- **Keyword Detection**: Recognizes preference indicators (e.g., "I love," "I enjoy," "I prefer")
- **Contextual Understanding**: Maintains conversation context to interpret follow-up messages

## Conclusion

The multi-stage prompt system enables the AI Travel Agent to provide a personalized, conversational planning experience that mimics human travel agent interactions. By strategically gathering information, suggesting relevant options, and creating detailed itineraries, the system helps users plan memorable trips aligned with their specific preferences and constraints. 