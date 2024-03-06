from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from geopy.distance import geodesic
app = Flask(__name__)
CORS(app)
CORS(app, resources={r"/check_availability": {"origins": "*"}})
base_url = "https://entities.nft.helium.io/v2"
base_url = "https://entities.nft.helium.io/v2"

# Replace 'YOUR_HELIUM_API_KEY' with your actual Helium API key
HELIUM_API_URL = f"{base_url}/hotspots"
GEOCODE_API_KEY = '65e5a0961c4bc213255343tre52df20'
GEOCODE_URL = 'https://geocode.maps.co/reverse?'

# Caching mechanism using a simple dictionary
hotspot_cache = {}

def get_hotspots_by_subnetwork(subnetwork):
    endpoint = f"{base_url}/hotspots?subnetwork={subnetwork}"
    response = requests.get(endpoint)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching data. Status code: {response.status_code}")
        return None

def get_hotspot_info_by_key(key_to_asset_key):
    endpoint = f"{base_url}/hotspot/{key_to_asset_key}"
    response = requests.get(endpoint)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching data. Status code: {response.status_code}")
        return None

def get_hotspot_pagination_metadata(subnetwork):
    endpoint = f"{base_url}/hotspots/pagination-metadata?subnetwork={subnetwork}"
    response = requests.get(endpoint)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching data. Status code: {response.status_code}")
        return None

def get_total_hotspots_in_country(latitude, longitude, subnetwork="iot"):
    # Fetch country information from Geocode API
    geocode_url = get_geocode_url(latitude, longitude)
    geocode_response = requests.get(geocode_url)

    if geocode_response.status_code == 200:
        geocode_data = geocode_response.json()
        address = geocode_data.get("address", {})
        country = address.get("country")

        # Check if the country is available
        if country:
            # Print debugging information
            print("Fetched country:", country)

            # Fetch all hotspots within the identified country
            all_country_hotspots = get_hotspots_in_location(country)

            # Print debugging information
            print("All hotspots in country:", all_country_hotspots)

            total_hotspots_in_country = len(all_country_hotspots)

            # Print debugging information
            print("Total hotspots in country:", total_hotspots_in_country)

            return total_hotspots_in_country
        else:
            print("Country information not available.")
            return 0
    else:
        print(f"Error fetching geocode data. Status code: {geocode_response.status_code}")
        return 0


def normalize_coordinates(latitude, longitude):
    latitude = float(latitude)
    longitude = float(longitude)
    latitude = max(min(latitude, 90), -90)
    longitude = max(min(longitude, 180), -180)
    return latitude, longitude

def get_geocode_url(latitude, longitude):
    return f'{GEOCODE_URL}lat={latitude}&lon={longitude}&api_key={GEOCODE_API_KEY}'

def get_all_hotspots():
    if 'all_hotspots' not in hotspot_cache:
        hotspots_data = get_hotspots_by_subnetwork("iot")
        if hotspots_data and "items" in hotspots_data:
            hotspot_cache['all_hotspots'] = hotspots_data["items"]
        else:
            hotspot_cache['all_hotspots'] = []

    return hotspot_cache['all_hotspots']

def get_hotspots_in_location(location):
    if location not in hotspot_cache:
        params = {"subnetwork": "iot", "location": location}
        hotspots_data = get_hotspots_by_subnetwork(params)
        if hotspots_data and "items" in hotspots_data:
            hotspot_cache[location] = hotspots_data["items"]
        else:
            hotspot_cache[location] = []

    return hotspot_cache[location]

def get_hotspots_data_in_range(latitude, longitude, radius=1000):
    endpoint = f"{base_url}/hotspots?subnetwork=iot"
    response = requests.get(endpoint)

    if response.status_code == 200:
        hotspots_data = response.json().get("items", [])

        user_location = (float(latitude), float(longitude))

        hotspots_within_range = [
            hotspot for hotspot in hotspots_data
            if "lat" in hotspot and "long" in hotspot
            and geodesic(user_location, (hotspot["lat"], hotspot["long"])).kilometers <= radius
        ]

        return hotspots_within_range
    else:
        print(f"Error fetching data. Status code: {response.status_code}")
        return []

def get_closest_hotspot(latitude, longitude):
    latitude, longitude = normalize_coordinates(latitude, longitude)
    all_hotspots = get_all_hotspots()

    if all_hotspots:
        user_location = (float(latitude), float(longitude))

        # Fetch all hotspots within a specified radius (default: 1000 km)
        hotspots_within_range = get_hotspots_data_in_range(latitude, longitude)

        if not hotspots_within_range:
            return {"error": "No hotspots available within the specified range."}

        closest_hotspot = min(
            hotspots_within_range,
            key=lambda hotspot: geodesic(user_location, (hotspot.get("lat", 0), hotspot.get("long", 0))).kilometers,
        )

        distance_km = round(geodesic(user_location, (closest_hotspot["lat"], closest_hotspot["long"])).kilometers, 2)

        num_hotspots_within_range = len(hotspots_within_range)
        num_active_hotspots_within_range = sum(1 for hotspot in hotspots_within_range if hotspot.get("is_active"))

        geocode_url = get_geocode_url(latitude, longitude)
        geocode_response = requests.get(geocode_url)
        geocode_data = geocode_response.json()

        if geocode_data:
            state = geocode_data.get("address", {}).get("state")
            country = geocode_data.get("address", {}).get("country")

            return {
                "distance_km": distance_km,
                "num_hotspots": len(all_hotspots),
                "num_hotspots_within_range": num_hotspots_within_range,
                "num_active_hotspots_within_range": num_active_hotspots_within_range,
                "hotspots_within_range": hotspots_within_range,
                "hotspot": closest_hotspot,
                "total_hotspots_in_country": get_total_hotspots_in_country(latitude, longitude),
                "country_name": country,
                "country_address": geocode_data.get("display_name", ""),
                "state_location": state,
            }

    return {"error": "No hotspots available."}


@app.route('/check_availability', methods=['POST'])
def check_availability():
    data = request.get_json()
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    print(f"Received request with latitude: {latitude}, longitude: {longitude}")
    geocode_url = get_geocode_url(latitude, longitude)
    geocode_response = requests.get(geocode_url)

    if geocode_response.status_code == 200:
        geocode_data = geocode_response.json()

        result = get_closest_hotspot(latitude, longitude)
        if "error" in result:
            return jsonify(result)
        else:
            distance_km = result["distance_km"]
            num_hotspots_within_range = result["num_hotspots_within_range"]
            num_active_hotspots_within_range = result["num_active_hotspots_within_range"]
            hotspots_within_range = result["hotspots_within_range"]

            availability_msg = (
                f"The network is available. The closest hotspot is approximately {distance_km} km away. "
                f"There are {num_hotspots_within_range} hotspots within the specified range, "
                f"and {num_active_hotspots_within_range} of them are active."
            )

            return jsonify({
                "availability": availability_msg,
                "hotspot": result["hotspot"],
                "hotspots_within_range": hotspots_within_range,
                "reverse_geocode": geocode_data,
                "total_hotspots_in_country": result["total_hotspots_in_country"],
                "country_name": result["country_name"],
                "country_address": result["country_address"],
                "state_location": result["state_location"],
            })
    else:
        return jsonify({"error": "Failed to fetch geocode data"}), 500

if __name__ == '__main__':
    # Use the PORT environment variable if available, otherwise default to 8080
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

