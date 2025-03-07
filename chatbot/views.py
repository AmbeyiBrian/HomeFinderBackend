import re
from functools import lru_cache
import json
import requests
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, Avg
import logging

# Import the specific models from your application
from properties.models import Property, PropertyType, Favorite, PropertyImage, Reservation
from users.models import CustomUser
from reviews.models import Review, Requests

# Set up logging
logger = logging.getLogger(__name__)

# Hugging Face API configuration
HF_API_URL = "https://api-inference.huggingface.co/models/"
INTENT_MODEL = "facebook/bart-large-mnli"  # Zero-shot classification model
NER_MODEL = "dslim/bert-base-NER"  # Named entity recognition model
SENTIMENT_MODEL = "distilbert-base-uncased-finetuned-sst-2-english"  # Sentiment analysis
HF_API_KEY = getattr(settings, 'HUGGING_FACE_API_KEY', '')  # Add safer fallback

# Verify API key is set
if not HF_API_KEY:
    logger.warning("HUGGING_FACE_API_KEY is not set. NLP features will be limited.")

HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}",
    "Content-Type": "application/json"
}

# Define domain-specific intents and example utterances for zero-shot classification
INTENTS = {
    "property_search": {
        "examples": ["I want to find a house", "Show me apartments for rent", "Looking for properties under $500k",
                    "Find me a 3 bedroom house", "I need a place in Nairobi", "What apartments are available?"],
        "action": "search_properties"
    },
    "property_details": {
        "examples": ["Tell me more about property 123", "What are the features of this house?",
                     "Can you describe this apartment?", "Show me property details", "Is this house still available?"],
        "action": "get_property_details"
    },
    "favorites": {
        "examples": ["Show my favorite properties", "What have I saved?", "My bookmarked listings",
                    "Add this to favorites", "Save this property", "Remove from my favorites"],
        "action": "handle_favorites"
    },
    "reviews": {
        "examples": ["Show reviews for property 123", "What do people think about this house?",
                     "I want to leave a review", "How is this property rated?", "Are there any good reviews?"],
        "action": "handle_reviews"
    },
    "user_account": {
        "examples": ["How do I create an account?", "Help me log in", "I want to register as an agent",
                    "Reset my password", "Update my profile", "Change my account details"],
        "action": "user_account_info"
    },
    "reservation": {
        "examples": ["How do I reserve a property?", "I want to book this house", "What's the reservation process?",
                    "Can I pay a booking fee?", "How does reservation work?", "Is there a deposit required?"],
        "action": "handle_reservation"
    }
}

# Entity types we want to extract
ENTITY_TYPES = ["LOC", "ORG", "MONEY", "NUMBER"]


@lru_cache(maxsize=128)
def detect_intent_hf(user_input):
    """Use Hugging Face's zero-shot classification to determine intent with better error handling and timeout"""
    intent_labels = list(INTENTS.keys())

    payload = {
        "inputs": user_input,
        "parameters": {"candidate_labels": intent_labels},
        "options": {"wait_for_model": True}
    }

    try:
        # Add timeout to prevent long processing times
        response = requests.post(
            f"{HF_API_URL}{INTENT_MODEL}", 
            headers=HEADERS, 
            json=payload,
            timeout=5  # 5-second timeout to ensure responsiveness
        )
        
        # Check if the request was successful
        if response.status_code != 200:
            logger.warning(f"API Error: {response.status_code} - {response.text}")
            return detect_intent_keywords(user_input)
            
        result = response.json()
        
        # Handle different response formats
        if isinstance(result, list) and len(result) > 0:
            result = result[0]  # Some models return a list

        # Get the highest scoring intent if score is above threshold
        if "scores" in result and max(result["scores"]) > 0.5:
            top_intent_index = result["scores"].index(max(result["scores"]))
            return result["labels"][top_intent_index]

        # Fallback to keyword matching if zero-shot confidence is low
        return detect_intent_keywords(user_input)
    except requests.exceptions.Timeout:
        logger.warning("Hugging Face API timeout - falling back to keyword matching")
        return detect_intent_keywords(user_input)
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error with Hugging Face intent detection: {str(e)}")
        return detect_intent_keywords(user_input)
    except Exception as e:
        logger.error(f"Error with Hugging Face intent detection: {str(e)}")
        # Fallback to keyword matching
        return detect_intent_keywords(user_input)


def detect_intent_keywords(user_input):
    """Enhanced keyword-based intent detection with better matching"""
    user_input = user_input.lower()

    # Direct pattern matching for specific intents
    reservation_patterns = ["reserve", "book", "booking", "reservation", "deposit"]
    if any(pattern in user_input for pattern in reservation_patterns):
        return "reservation"
        
    property_patterns = ["property", "house", "apartment", "home", "rent", "buy", "find", "search"]
    if any(pattern in user_input for pattern in property_patterns):
        return "property_search"
        
    favorites_patterns = ["favorite", "save", "bookmark", "like", "saved", "my list"]
    if any(pattern in user_input for pattern in favorites_patterns):
        return "favorites"
        
    account_patterns = ["account", "login", "register", "sign up", "profile", "password"]
    if any(pattern in user_input for pattern in account_patterns):
        return "user_account"
        
    review_patterns = ["review", "rating", "rate", "opinion", "feedback"]
    if any(pattern in user_input for pattern in review_patterns):
        return "reviews"
        
    detail_patterns = ["details", "more about", "describe", "features", "tell me about", "what is", "show me"]
    if any(pattern in user_input for pattern in detail_patterns):
        return "property_details"

    # Extract keywords from intent examples with weighted scoring
    intent_scores = {}
    for intent, config in INTENTS.items():
        words = set()
        for example in config["examples"]:
            words.update(example.lower().split())

        # Filter out common words
        keywords = [w for w in words if len(w) > 3]

        # Count keyword matches with weighting
        score = sum(2 if keyword in user_input else 0 for keyword in keywords)
        
        # Check for partial matches
        score += sum(1 for keyword in keywords if keyword[:4] in user_input)
        
        if score > 0:
            intent_scores[intent] = score

    # Return the intent with the highest score, or None if no matches
    if intent_scores:
        return max(intent_scores, key=intent_scores.get)
    return None


def extract_entities(user_input):
    """Extract named entities using Hugging Face NER model with better error handling"""
    if not HF_API_KEY:
        # Fallback to regex based entity extraction if no API key
        return extract_entities_regex(user_input)
        
    payload = {
        "inputs": user_input,
        "options": {"wait_for_model": True}
    }

    try:
        response = requests.post(
            f"{HF_API_URL}{NER_MODEL}", 
            headers=HEADERS, 
            json=payload,
            timeout=5
        )
        
        if response.status_code != 200:
            logger.warning(f"NER API Error: {response.status_code} - {response.text}")
            return extract_entities_regex(user_input)
            
        entities = response.json()

        # Process and group entities
        extracted = {}
        for entity in entities:
            if entity["entity_group"] in ENTITY_TYPES:
                entity_type = entity["entity_group"]
                entity_value = entity["word"]

                if entity_type not in extracted:
                    extracted[entity_type] = []

                # Clean up entity value
                if entity_type == "MONEY" and entity_value.startswith("$"):
                    entity_value = entity_value[1:]

                extracted[entity_type].append(entity_value)

        return extracted
    except Exception as e:
        logger.error(f"Error with entity extraction: {str(e)}")
        return extract_entities_regex(user_input)


def extract_entities_regex(user_input):
    """Extract entities using regex patterns as a fallback"""
    extracted = {}
    
    # Extract location entities
    loc_match = re.search(r'in\s+([A-Za-z\s]+)(?:,\s*([A-Za-z\s]+))?', user_input)
    if loc_match:
        extracted["LOC"] = [loc_match.group(1).strip()]
        if loc_match.group(2):
            extracted["LOC"].append(loc_match.group(2).strip())
    
    # Extract monetary values
    money_matches = re.findall(r'\$?(\d[\d,]*\.?\d*)k?', user_input)
    if money_matches:
        extracted["MONEY"] = money_matches
    
    # Extract numbers
    number_matches = re.findall(r'\b(\d+)\b', user_input)
    if number_matches:
        extracted["NUMBER"] = number_matches
    
    return extracted


def analyze_sentiment(user_input):
    ...
    try:
        response = requests.post(
            f"{HF_API_URL}{SENTIMENT_MODEL}",
            headers=HEADERS,
            json=payload,
            timeout=5
        )

        if response.status_code != 200:
            logger.warning(f"Sentiment API Error: {response.status_code} - {response.text}")
            return {"label": "NEUTRAL", "score": 0.5}

        result = response.json()

        # Ensure result is a list and extract the first item
        if isinstance(result, list) and len(result) > 0:
            return result[0]  # Return the first item as a dictionary

        return {"label": "NEUTRAL", "score": 0.5}  # Fallback if result is not as expected
    except Exception as e:
        logger.error(f"Error with sentiment analysis: {str(e)}")
        return {"label": "NEUTRAL", "score": 0.5}


def search_properties(user_input, context=None, entities=None):
    """Enhanced property search using extracted entities and context"""
    query = Q()

    # Use context from previous conversation if available
    if context and 'property_filters' in context:
        existing_filters = context['property_filters']
        if 'listing_type' in existing_filters:
            query &= Q(listing_type=existing_filters['listing_type'])
        if 'bedrooms' in existing_filters:
            query &= Q(bedrooms=existing_filters['bedrooms'])
        if 'max_price' in existing_filters:
            query &= Q(price__lte=existing_filters['max_price'])
        if 'location' in existing_filters:
            query &= (Q(city__icontains=existing_filters['location']) |
                      Q(state__icontains=existing_filters['location']))

    # Process entities if available
    if entities:
        # Handle location entities
        if 'LOC' in entities:
            location = entities['LOC'][0]  # Use first location entity
            query &= (Q(city__icontains=location) | Q(state__icontains=location))

        # Handle money entities (price)
        if 'MONEY' in entities:
            try:
                max_price = int(entities['MONEY'][0].replace(',', ''))
                if 'k' in user_input.lower():
                    max_price *= 1000
                query &= Q(price__lte=max_price)
            except ValueError:
                pass

        # Handle number entities (bedrooms)
        if 'NUMBER' in entities and "bed" in user_input.lower():
            try:
                bedrooms = int(entities['NUMBER'][0])
                query &= Q(bedrooms=bedrooms)
            except ValueError:
                pass

    # Fallback to regex patterns if entity extraction failed
    if not entities or (
            'LOC' not in entities and
            'MONEY' not in entities and
            'NUMBER' not in entities
    ):
        # Determine listing type
        if "rent" in user_input.lower():
            query &= Q(listing_type='rent')
        elif any(word in user_input.lower() for word in ["buy", "sale", "purchase"]):
            query &= Q(listing_type='sale')

        # Extract bedrooms
        bedroom_match = re.search(r'(\d+)\s*bed', user_input.lower())
        if bedroom_match:
            bedrooms = bedroom_match.group(1)
            query &= Q(bedrooms=int(bedrooms))

        # Extract price
        price_match = re.search(r'under\s*\$?(\d+)(?:,(\d+))?k?', user_input.lower())
        if price_match:
            # Handle formats like $500, $500k, $1,500, etc.
            if price_match.group(2):  # Comma format like 1,500
                max_price = int(price_match.group(1)) * 1000 + int(price_match.group(2))
            else:
                max_price = int(price_match.group(1))
                if 'k' in user_input[price_match.end():price_match.end() + 1].lower():
                    max_price *= 1000

            query &= Q(price__lte=max_price)

        # Extract location (city or state)
        city_match = re.search(r'in\s+([A-Za-z\s]+)', user_input.lower())
        if city_match:
            location = city_match.group(1).strip()
            # Try to match with city or state
            query &= (Q(city__icontains=location) | Q(state__icontains=location))

    # Extract property type
    property_types = PropertyType.objects.all().values_list('name', flat=True)
    for prop_type in property_types:
        if prop_type.lower() in user_input.lower():
            query &= Q(property_type__name__icontains=prop_type)
            break

    # Always filter for available properties unless specifically asking for others
    if "sold" in user_input.lower():
        query &= Q(status='sold')
    elif "pending" in user_input.lower():
        query &= Q(status='pending')
    else:
        query &= Q(status='available')

    # Get properties with the constructed query
    properties = Property.objects.filter(query).order_by('price')[:5]

    # Store filters in context for later reference
    property_filters = {}
    if "rent" in user_input.lower():
        property_filters['listing_type'] = 'rent'
    elif any(word in user_input.lower() for word in ["buy", "sale", "purchase"]):
        property_filters['listing_type'] = 'sale'

    bedroom_match = re.search(r'(\d+)\s*bed', user_input.lower())
    if bedroom_match:
        property_filters['bedrooms'] = int(bedroom_match.group(1))

    price_match = re.search(r'under\s*\$?(\d+)(?:,(\d+))?k?', user_input.lower())
    if price_match:
        if price_match.group(2):
            property_filters['max_price'] = int(price_match.group(1)) * 1000 + int(price_match.group(2))
        else:
            max_price = int(price_match.group(1))
            if 'k' in user_input[price_match.end():price_match.end() + 1].lower():
                max_price *= 1000
            property_filters['max_price'] = max_price

    city_match = re.search(r'in\s+([A-Za-z\s]+)', user_input.lower())
    if city_match:
        property_filters['location'] = city_match.group(1).strip()

    # Return both properties and filters for context
    return properties, property_filters


def format_property_response(properties, context=None):
    """Format property search results into a response message"""
    if not properties:
        return ("I couldn't find any properties matching your criteria. Would you like to broaden your search?",
                {"properties": []})

    if properties.count() == 1:
        prop = properties[0]
        response = (f"I found 1 property: {prop.title} - a {prop.bedrooms} bedroom "
                    f"{prop.property_type.name if prop.property_type else 'property'} "
                    f"in {prop.city}, {prop.state} for ${int(prop.price):,}.")

        # Add a primary image URL if available
        primary_image = PropertyImage.objects.filter(property=prop, is_primary=True).first()
        if primary_image:
            response += f" You can view the primary image at {primary_image.image.url}"

        return response, {"properties": [{"id": prop.id, "title": prop.title}]}
    else:
        count = properties.count()
        response = f"I found {count} properties matching your criteria:\n\n"

        property_list = []
        for i, prop in enumerate(properties, 1):
            response += (f"{i}. {prop.title} - {prop.bedrooms} bed, "
                         f"${int(prop.price):,} in {prop.city}\n")
            property_list.append({"id": prop.id, "title": prop.title, "index": i})

        response += "\nWould you like more details about any of these properties?"
        return response, {"properties": property_list}


def get_property_details(user_input, context=None, entities=None):
    """Get detailed information about a specific property using NER or context"""
    property_id = None

    # First try to get property ID from entities
    if entities and 'NUMBER' in entities:
        try:
            property_id = int(entities['NUMBER'][0])
        except ValueError:
            pass

    # Try regex pattern if entity extraction failed
    if not property_id:
        property_id_match = re.search(r'property\s*(\d+)', user_input.lower())
        if property_id_match:
            property_id = int(property_id_match.group(1))

    # Try to get property from index reference (property 1, 2, etc.)
    if not property_id and context and 'properties' in context:
        index_match = re.search(r'(?:property|listing|number)\s*(\d+)', user_input.lower())
        if index_match:
            index = int(index_match.group(1))
            for prop in context['properties']:
                if prop.get('index') == index:
                    property_id = prop.get('id')
                    break

    # If no specific property was mentioned, check if only one was in context
    if not property_id and context and 'properties' in context and len(context['properties']) == 1:
        property_id = context['properties'][0].get('id')

    # If still no property found, ask for clarification
    if not property_id:
        return ("Which property would you like details about? Please provide a property ID or number from the list.",
                None)

    try:
        # Try to find the property
        property = Property.objects.get(id=property_id)

        # Get average rating
        avg_rating = Review.objects.filter(property=property).aggregate(Avg('rating'))['rating__avg']
        rating_text = f"{avg_rating:.1f}/5" if avg_rating else "No ratings yet"

        # Count images
        image_count = PropertyImage.objects.filter(property=property).count()

        # Check if property has active reservation
        has_reservation = Reservation.objects.filter(
            property=property,
            status__in=['pending', 'confirmed']
        ).exists()
        reservation_status = "Currently Reserved" if has_reservation else "Available for Reservation"

        # Build detailed response
        response = f"### {property.title} ###\n\n"
        response += f"Price: ${int(property.price):,}\n"
        response += f"Type: {property.property_type.name if property.property_type else 'Not specified'}\n"
        response += f"Status: {property.get_status_display()}\n"
        response += f"Reservation: {reservation_status}\n"
        response += f"Size: {property.bedrooms} bed, {int(property.bathrooms)} bath, {property.square_feet} sq ft\n"
        response += f"Location: {property.address}, {property.city}, {property.state} {property.zip_code}\n"
        response += f"Rating: {rating_text}\n"
        response += f"Images: {image_count} available\n\n"
        response += f"Description: {property.description[:200]}...\n\n"
        response += "Would you like to schedule a viewing, reserve this property, or have questions about it?"

        # Return response and current property context
        return response, {"current_property": {"id": property.id, "title": property.title}}
    except Property.DoesNotExist:
        return f"I couldn't find a property with ID {property_id}. Please check the ID and try again.", None


def handle_favorites(user_input, context=None, user=None):
    """Handle user favorite properties with user context"""
    if not user or not user.is_authenticated:
        return ("To view or manage your favorite properties, please log in to your account. "
                "You can save properties you like by clicking the heart icon on any property listing."), None

    # Check if user wants to add current property to favorites
    action = "view"
    if any(word in user_input.lower() for word in ["add", "save", "favorite", "like"]):
        action = "add"
    elif any(word in user_input.lower() for word in ["remove", "delete", "unfavorite", "unlike"]):
        action = "remove"

    # Add to favorites
    if action == "add" and context and 'current_property' in context:
        property_id = context['current_property']['id']
        try:
            property = Property.objects.get(id=property_id)
            favorite, created = Favorite.objects.get_or_create(user=user, property=property)
            if created:
                return f"I've added {property.title} to your favorites!", None
            else:
                return f"This property is already in your favorites.", None
        except Property.DoesNotExist:
            return "I couldn't find that property to add to your favorites.", None

    # Remove from favorites
    if action == "remove" and context and 'current_property' in context:
        property_id = context['current_property']['id']
        try:
            Favorite.objects.filter(user=user, property_id=property_id).delete()
            return "I've removed that property from your favorites.", None
        except:
            return "I couldn't remove that property from your favorites.", None

    # View favorites
    if action == "view":
        favorites = Favorite.objects.filter(user=user).select_related('property')[:5]
        if not favorites:
            return "You don't have any favorite properties yet.", None

        response = "Here are your favorite properties:\n\n"
        for i, fav in enumerate(favorites, 1):
            prop = fav.property
            response += f"{i}. {prop.title} - ${int(prop.price):,} in {prop.city}\n"

        return response, None


def handle_reviews(user_input, context=None, entities=None, user=None):
    """Handle property reviews with entity recognition and context"""
    property_id = None

    # Extract property ID from entities
    if entities and 'NUMBER' in entities:
        try:
            property_id = int(entities['NUMBER'][0])
        except ValueError:
            pass

    # Try regex pattern if entity extraction failed
    if not property_id:
        property_id_match = re.search(r'property\s*(\d+)', user_input.lower())
        if property_id_match:
            property_id = int(property_id_match.group(1))

    # Use current property from context if available
    if not property_id and context and 'current_property' in context:
        property_id = context['current_property']['id']

    # Determine if user wants to submit a review
    is_submission = any(word in user_input.lower() for word in ["submit", "leave", "write", "post"])

    if is_submission:
        if not user or not user.is_authenticated:
            return (
                "To submit a review, please log in first. Then visit the property page and click the 'Leave a Review' button."), None

        if not property_id:
            return (
                "Which property would you like to review? Please provide a property ID or continue from a property listing."), None

        try:
            property = Property.objects.get(id=property_id)
            # Check if user already reviewed this property
            existing = Review.objects.filter(user=user, property=property).exists()
            if existing:
                return f"You've already reviewed {property.title}. You can edit your review on the property page.", None

            # Extract rating if present
            rating_match = re.search(r'(\d+)(?:\s*\/\s*\d+)?\s*stars?', user_input.lower())
            rating = None
            if rating_match:
                try:
                    rating = int(rating_match.group(1))
                    if rating > 5:
                        rating = 5
                except ValueError:
                    pass

            if rating:
                # Try to extract review text from user input
                review_text = user_input
                # Remove the rating part
                review_text = re.sub(r'\d+\s*\/?\s*\d*\s*stars?', '', review_text)
                # Remove common phrases like "I want to leave a review"
                review_text = re.sub(r'(i want to|please|could you|leave|write|submit|post|a review|for property \d+)', '', review_text, flags=re.IGNORECASE)
                # Clean up
                review_text = review_text.strip()
                if len(review_text) < 3:
                    review_text = "Submitted via chatbot."
                
                Review.objects.create(
                    user=user,
                    property=property,
                    rating=rating,
                    content=review_text
                )
                return f"Thank you! Your {rating}-star review for {property.title} has been submitted.", None
            else:
                return f"To review {property.title}, please include a rating from 1 to 5 stars.", None
        except Property.DoesNotExist:
            return f"I couldn't find a property with ID {property_id}.", None

    # View reviews for a property
    if property_id:
        try:
            property = Property.objects.get(id=property_id)
            reviews = Review.objects.filter(property=property)

            if not reviews.exists():
                return f"There are no reviews yet for {property.title}.", None

            avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
            response = f"Reviews for {property.title} (Average: {avg_rating:.1f}/5):\n\n"

            for i, review in enumerate(reviews[:3], 1):
                response += f"{i}. {review.user.username}: {review.rating}/5\n"
                if review.content:
                    response += f"   \"{review.content[:50]}...\"\n"

            if reviews.count() > 3:
                response += f"\nThere are {reviews.count() - 3} more reviews available on the property page."

            return response, {"current_property": {"id": property.id, "title": property.title}}
        except Property.DoesNotExist:
            return f"I couldn't find a property with ID {property_id}.", None

    return "You can view and submit reviews on individual property listings. Would you like to see reviews for a specific property?", None


def user_account_info(user_input, context=None, user=None):
    """Handle user account-related questions with personalization"""
    # Personalize response if user is logged in
    if user and user.is_authenticated:
        if "profile" in user_input.lower() or "my account" in user_input.lower():
            return f"Hi {user.username}! You can view and edit your profile by clicking on your username in the top right corner.", None

        if "agent" in user_input.lower() or "seller" in user_input.lower():
            if user.role == 'agent':
                return "You're already registered as an agent. You can manage your listings from your agent dashboard.", None
            elif user.role == 'seller':
                return "You're already registered as a seller. You can manage your listings from your seller dashboard.", None
            else:
                return ("To upgrade to a seller or agent account, go to your profile settings and select your preferred role. "
                        "You'll need to complete a verification process."), None

    # Standard responses for non-logged in users
    if "create" in user_input.lower() or "register" in user_input.lower() or "sign up" in user_input.lower():
        return ("To create a new account, click on the 'Sign Up' button in the top right corner. "
                "You can register as a buyer, seller, or real estate agent."), None

    if "login" in user_input.lower() or "sign in" in user_input.lower():
        return "To log in to your account, click on the 'Log In' button in the top right corner.", None

    if "agent" in user_input.lower() or "seller" in user_input.lower():
        return ("To register as a real estate agent or seller, you'll need to create a regular account first, "
                "then submit a verification request. This helps us maintain quality listings and services."), None

    return ("Your user account gives you access to save favorite properties, submit reviews, "
            "and communicate with sellers or agents. What specific information about accounts do you need?"), None


def handle_reservation(user_input, context=None, entities=None, user=None):
    """Handle reservation-related queries"""
    if "how" in user_input.lower() or "process" in user_input.lower() or "work" in user_input.lower():
        return ("To reserve a property, follow these steps:\n\n"
                "1. Browse and find a property you're interested in\n"
                "2. Click the 'Reserve' button on the property detail page\n"
                "3. Review the reservation details and fee (typically 10% of the property price)\n"
                "4. Complete payment using M-Pesa or other supported methods\n"
                "5. Once your reservation is confirmed, you'll receive contact details for the property owner\n\n"
                "The reservation fee will be deducted from the final property price when you complete the purchase."), None
                
    if "fee" in user_input.lower() or "cost" in user_input.lower() or "price" in user_input.lower() or "deposit" in user_input.lower():
        return ("The reservation fee is typically 10% of the property price. This reserves the property exclusively for you "
                "and prevents others from booking it. The fee will be applied to the final property price, effectively "
                "serving as a deposit. HomeFinder charges a small booking fee (10% of the reservation amount) for this service."), None
                
    if "cancel" in user_input.lower() or "refund" in user_input.lower():
        return ("Reservation cancellation policies depend on the individual property. Generally, cancellations made within "
                "24 hours may be eligible for a partial refund. Please contact customer support for specific cases."), None
    
    # If user wants to make a reservation for a specific property
    if any(word in user_input.lower() for word in ["book", "reserve", "make"]) and context and 'current_property' in context:
        if not user or not user.is_authenticated:
            return ("To reserve a property, please sign in first. Then you can use the 'Reserve' button on the property details page."), None
            
        property_id = context['current_property']['id']
        try:
            property = Property.objects.get(id=property_id)
            
            # Check if property is already reserved
            existing_reservation = Reservation.objects.filter(
                property=property,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if existing_reservation:
                return f"I'm sorry, but {property.title} is already reserved by another user. Would you like to see similar properties?", None
                
            reservation_price = property.reservation_price or property.price * 0.1
            booking_fee = reservation_price * 0.1
            
            return (f"Great choice! To reserve {property.title}, you'll need to pay a reservation fee of "
                   f"Ksh {int(reservation_price):,} (plus a booking fee of Ksh {int(booking_fee):,}). "
                   f"Please click the 'Reserve' button on the property details page to proceed with payment."), None
        except Property.DoesNotExist:
            return "I couldn't find that property in our system.", None
        
    return ("Our reservation system allows you to secure a property with a partial payment. This gives you exclusive access "
            "to the property owner to complete the transaction. Would you like to know more about the reservation process?"), None


def generate_suggestion(context):
    """Generate a contextual suggestion based on conversation history"""
    if not context:
        return None

    if 'properties' in context and context['properties']:
        if len(context['properties']) == 1:
            return f"Would you like to see more details about {context['properties'][0]['title']}?"
        elif len(context['properties']) > 1:
            return "Would you like more details about any of these properties?"

    if 'current_property' in context:
        suggestions = [
            f"Would you like to see reviews for {context['current_property']['title']}?",
            f"Would you like to reserve this property?",
            f"Shall I save {context['current_property']['title']} to your favorites?",
            f"Do you want to see more properties like {context['current_property']['title']}?"
        ]
        import random
        return random.choice(suggestions)

    if 'property_filters' in context:
        filters = []
        if 'bedrooms' in context['property_filters']:
            filters.append(f"{context['property_filters']['bedrooms']} bedrooms")
        if 'max_price' in context['property_filters']:
            filters.append(f"under ${context['property_filters']['max_price']:,}")
        if 'location' in context['property_filters']:
            filters.append(f"in {context['property_filters']['location']}")

        if filters:
            filter_str = ", ".join(filters)
            return f"Would you like to see more properties with {filter_str}?"

    return None


def fallback_response(sentiment=None):
    """Provide a helpful response when the query is outside our domain, with sentiment context"""
    base_response = ("I can help you find properties, get property details, manage favorites, "
                     "read reviews, make reservations, or answer questions about user accounts.")

    # Adjust tone based on sentiment if available
    if sentiment and sentiment.get("label") == "NEGATIVE" and sentiment.get("score", 0) > 0.7:
        return ("I'm sorry I couldn't help with your last request. " + base_response +
                " How can I better assist with your real estate needs today?")

    return base_response + " What can I help you with today?"


@api_view(["POST"])
def chatbot_view(request):
    """Enhanced Django REST API endpoint for the real estate chatbot"""
    try:
        user_input = request.data.get("query", "")
        if not user_input:
            return Response(
                {"error": "Please provide a query parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get conversation context from session
        conversation_context = {}
        if 'conversation' in request.session:
            request.session['conversation'].append({"user": user_input})

            # Extract context from previous bot responses
            for message in request.session['conversation'][-5:]:  # Look at last 5 messages
                if 'bot' in message and 'context' in message:
                    # Merge contexts, with newer contexts taking precedence
                    conversation_context.update(message['context'])
        else:
            request.session['conversation'] = [{"user": user_input}]

        request.session.modified = True

        # Get authenticated user if available
        user = request.user if request.user.is_authenticated else None

        # Perform sentiment analysis
        sentiment = analyze_sentiment(user_input)

        # Extract entities
        entities = extract_entities(user_input)

        # Detect intent with model or keywords
        intent = detect_intent_hf(user_input)

        # If no real estate intent is detected, provide a domain-specific fallback
        if not intent:
            response_text = fallback_response(sentiment)
            response_context = None
        else:
            # Get the action function based on the detected intent
            action_name = INTENTS[intent]["action"]
            action_function = globals()[action_name]

            try:
                # Check if we're doing property search which needs special handling
                if action_name == "search_properties":
                    properties, property_filters = search_properties(user_input, conversation_context, entities)
                    response_text, properties_context = format_property_response(properties)

                    # Combine property context with filters
                    response_context = properties_context
                    if property_filters:
                        response_context['property_filters'] = property_filters
                else:
                    # Execute the appropriate function based on intent
                    response_text, response_context = action_function(
                        user_input,
                        context=conversation_context,
                        entities=entities,
                        user=user
                    )
            except Exception as e:
                logger.error(f"Error processing intent {intent}: {str(e)}", exc_info=True)
                return Response(
                    {"error": f"Error processing your request: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Generate contextual suggestion if no clear response context
        if not response_context and conversation_context:
            suggestion = generate_suggestion(conversation_context)
            if suggestion:
                response_text += f"\n\n{suggestion}"

        # Save bot response and context to conversation
        bot_response = {
            "bot": response_text,
            "context": response_context if response_context else conversation_context
        }
        request.session['conversation'].append(bot_response)
        request.session.modified = True

        # Return response along with useful metadata
        return Response({
            "response": response_text,
            "intent_detected": intent,
            "sentiment": sentiment.get("label") if sentiment else "NEUTRAL"
        })

    except Exception as e:
        logger.error(f"Unexpected error in chatbot_view: {str(e)}", exc_info=True)
        return Response(
            {"error": "I'm having trouble processing your request right now. Please try again shortly."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )