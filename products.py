"""
Shopify Integration Module
Fetches products from omega-house.net Shopify store and recommends matches
based on detected key, tempo, and mix profile.
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Shopify Store Configuration
SHOPIFY_STORE = "omega-house.myshopify.com"
SHOPIFY_API_VERSION = "2024-01"

# OAuth Credentials (from environment variables for security)
CLIENT_ID = os.getenv('SHOPIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SHOPIFY_CLIENT_SECRET')
ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')

# If no token yet, use client credentials to get one
# (function defined below - currently using fallback products instead)
# if not ACCESS_TOKEN:
#     ACCESS_TOKEN = get_access_token()

# Product Database (fallback if API call fails)
# Updated with actual Omega House products
PRODUCTS = {
    'drum_kits': [
        {
            'id': 1,
            'name': 'Premiere Drum Kit',
            'price': '$34.00',
            'bpm_range': [85, 160],
            'keys': ['all'],
            'genre': ['hiphop', 'trap', 'rnb', 'pop'],
            'url': 'https://www.omega-house.net/products/premiere-drum-kit',
            'description': 'Professional drum kit with 808s, kicks, snares, and hats'
        }
    ],
    'sample_packs': [
        {
            'id': 101,
            'name': 'Melancholy Beats Volume One',
            'price': '$28.00',
            'bpm_range': [80, 110],
            'keys': ['all'],
            'genre': ['hiphop', 'lofi', 'rnb', 'soul'],
            'url': 'https://www.omega-house.net/products/melancholy-beats-vol-1',
            'description': 'Moody, atmospheric beat samples for lo-fi and hip-hop production'
        },
        {
            'id': 102,
            'name': 'Ionospheric Beats Volume One',
            'price': '$20.00',
            'bpm_range': [90, 140],
            'keys': ['all'],
            'genre': ['electronic', 'experimental', 'ambient'],
            'url': 'https://www.omega-house.net/products/ionospheric-beats-vol-1',
            'description': 'Spacey, atmospheric beats for electronic and experimental music'
        }
    ],
    'services': [
        {
            'id': 201,
            'name': 'Mixing & Mastering - Stereo',
            'price': '$50.00',
            'bpm_range': ['all'],
            'keys': ['all'],
            'genre': ['all'],
            'url': 'https://www.omega-house.net/products/mixing-mastering-stereo',
            'description': 'Professional mixing and mastering for stereo files'
        },
        {
            'id': 202,
            'name': 'Mixing & Mastering - Stem',
            'price': '$100.00',
            'bpm_range': ['all'],
            'keys': ['all'],
            'genre': ['all'],
            'url': 'https://www.omega-house.net/products/mixing-mastering-stem',
            'description': 'Professional mixing and mastering for multi-track stem files'
        }
    ],
    'merchandise': [
        {
            'id': 301,
            'name': 'Mystical Hand T-Shirt Dress',
            'price': '$47.35',
            'bpm_range': ['all'],
            'keys': ['all'],
            'genre': ['all'],
            'url': 'https://www.omega-house.net/products/mystical-hand-tshirt-dress',
            'description': 'Unique boho-style t-shirt dress with mystical hand symbol'
        },
        {
            'id': 302,
            'name': 'Trap Sack Orange Fade Backpack',
            'price': '$45.00',
            'bpm_range': ['all'],
            'keys': ['all'],
            'genre': ['all'],
            'url': 'https://www.omega-house.net/products/trap-sack-backpack',
            'description': 'Durable fabric backpack with vibrant orange fade design'
        }
    ]
}

def get_access_token():
    """Get OAuth access token from Shopify using client credentials."""
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Warning: SHOPIFY_CLIENT_ID or SHOPIFY_CLIENT_SECRET not set")
        return None
    
    url = f"https://{SHOPIFY_STORE}/admin/oauth/access_token"
    
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            return response.json().get('access_token')
    except Exception as e:
        print(f"Error getting Shopify token: {e}")
    
    return None

def fetch_shopify_products():
    """Fetch all products from Shopify store."""
    if not ACCESS_TOKEN:
        print("No Shopify access token available, using fallback products")
        return PRODUCTS
    
    headers = {
        'X-Shopify-Access-Token': ACCESS_TOKEN
    }
    
    url = f"https://{SHOPIFY_STORE}/admin/api/{SHOPIFY_API_VERSION}/products.json"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            shopify_products = response.json().get('products', [])
            # Parse and organize products (implementation depends on Shopify schema)
            return parse_shopify_products(shopify_products)
    except Exception as e:
        print(f"Error fetching Shopify products: {e}")
    
    return PRODUCTS

def parse_shopify_products(shopify_products):
    """Parse Shopify product data into recommendation format."""
    # This would parse the actual Shopify response
    # For now, return the fallback database
    return PRODUCTS

def get_recommendations(key=None, tempo=None, mix_profile=None):
    """
    Get product recommendations based on detected audio properties.
    
    Args:
        key: Musical key (e.g., "G Minor")
        tempo: BPM (e.g., 120)
        mix_profile: Mix reference (e.g., "electronic")
    
    Returns:
        List of recommended products with relevance scores
    """
    
    products = fetch_shopify_products()
    recommendations = []
    
    # Genre mapping from mix_profile
    genre_map = {
        'pop': 'pop',
        'hiphop': 'hiphop',
        'trap': 'trap',
        'rock': 'rock',
        'electronic': 'electronic',
        'classical': 'cinematic',
        'lofi': 'lofi',
        'soul': 'soul',
        'rnb': 'rnb',
        'ambient': 'ambient'
    }
    
    detected_genre = genre_map.get(mix_profile, 'all')
    
    # Score all products (drums, samples, services, merchandise)
    for category in ['drum_kits', 'sample_packs', 'services', 'merchandise']:
        for product in products.get(category, []):
            score = 0
            
            # Tempo match (highest weight) - skip for services/merchandise
            if category in ['drum_kits', 'sample_packs']:
                bpm_range = product.get('bpm_range', [60, 150])
                if isinstance(bpm_range, list) and len(bpm_range) == 2:
                    if tempo:
                        if bpm_range[0] <= tempo <= bpm_range[1]:
                            score += 40  # Perfect match
                        elif bpm_range[0] - 15 <= tempo <= bpm_range[1] + 15:
                            score += 20  # Close match
            
            # Genre match
            product_genres = product.get('genre', ['all'])
            if 'all' not in product_genres:
                if detected_genre in product_genres:
                    score += 30
                # Minor bonus if any genre matches
                elif any(g == detected_genre for g in product_genres):
                    score += 15
            else:
                # Services/merchandise always get a base score
                if category == 'services':
                    score += 10
                elif category == 'merchandise':
                    score += 5
            
            # Key match (if applicable)
            if key and category in ['drum_kits', 'sample_packs']:
                product_keys = product.get('keys', ['all'])
                if 'all' not in product_keys:
                    key_letter = key.split()[0]  # Extract letter from "G Minor"
                    if any(key_letter in pk for pk in product_keys):
                        score += 20
            
            if score > 0:
                recommendations.append({
                    'id': product['id'],
                    'name': product['name'],
                    'price': product['price'],
                    'description': product['description'],
                    'url': product['url'],
                    'relevance_score': score,
                    'reason': generate_reason(key, tempo, detected_genre, product, category)
                })
    
    # Sort by relevance score (descending)
    recommendations.sort(key=lambda x: x['relevance_score'], reverse=True)
    
    # Return top 5, prioritizing production products over merchandise
    return recommendations[:5]

def generate_reason(key, tempo, genre, product, category='sample_packs'):
    """Generate human-readable recommendation reason."""
    reasons = []
    
    # Production products
    if category in ['drum_kits', 'sample_packs']:
        bpm_range = product.get('bpm_range', [])
        if isinstance(bpm_range, list) and len(bpm_range) == 2 and tempo:
            if bpm_range[0] <= tempo <= bpm_range[1]:
                reasons.append(f"Perfect for {tempo} BPM")
            else:
                reasons.append(f"Great for {tempo} BPM production")
        
        product_genres = product.get('genre', [])
        if genre and genre != 'all' and genre in product_genres:
            reasons.append(f"Ideal for {genre}")
        
        if key and 'all' not in product.get('keys', ['all']):
            reasons.append(f"Works in {key}")
    
    # Services
    elif category == 'services':
        reasons.append("Have your audio professionally processed")
    
    # Merchandise
    elif category == 'merchandise':
        reasons.append("Omega House branded merch")
    
    return ' • '.join(reasons) if reasons else "Recommended for your style"

if __name__ == '__main__':
    # Test recommendations
    test_analysis = {
        'key': 'G Minor',
        'tempo': 95,
        'mix_reference': 'hiphop'
    }
    
    recs = get_recommendations(
        key=test_analysis['key'],
        tempo=test_analysis['tempo'],
        mix_profile=test_analysis['mix_reference']
    )
    
    print(f"\n📊 Recommendations for {test_analysis}:\n")
    for i, rec in enumerate(recs, 1):
        print(f"{i}. {rec['name']} - {rec['price']}")
        print(f"   {rec['reason']}")
        print(f"   → {rec['url']}\n")
