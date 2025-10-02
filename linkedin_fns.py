import hashlib
import requests
import json


def get_linkedin_data(profile_url: str) -> dict:
    """
    Gets basic LinkedIn profile data for a given LinkedIn URL.

    Note: This function requires a third-party API service like:
    - RapidAPI's LinkedIn Profile Data API
    - ProxyCurl API
    - ScraperAPI

    For demonstration, this shows the structure. You'll need to:
    1. Sign up for an API service
    2. Get an API key
    3. Update the implementation below

    Args:
        profile_url: The LinkedIn profile URL (e.g., https://www.linkedin.com/in/username/)

    Returns:
        Dictionary containing basic LinkedIn profile data
    """
    # Example using ProxyCurl API (requires API key)
    # You need to sign up at https://nubela.co/proxycurl/ and get an API key

    api_key = "YOUR_API_KEY_HERE"  # Replace with your actual API key
    api_url = "https://nubela.co/proxycurl/api/v2/linkedin"

    headers = {
        'Authorization': f'Bearer {api_key}'
    }

    params = {
        'url': profile_url,
        'fallback_to_cache': 'on-error',
        'use_cache': 'if-present',
        'skills': 'include',
        'inferred_salary': 'include',
        'personal_email': 'include',
        'personal_contact_number': 'include',
        'twitter_profile_id': 'include',
        'facebook_profile_id': 'include',
        'github_profile_id': 'include',
        'extra': 'include'
    }

    try:
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()

        # Extract basic information
        basic_data = {
            'full_name': data.get('full_name'),
            'headline': data.get('headline'),
            'summary': data.get('summary'),
            'location': data.get('city'),
            'country': data.get('country_full_name'),
            'profile_pic_url': data.get('profile_pic_url'),
            'experiences': data.get('experiences', []),
            'education': data.get('education', []),
            'skills': data.get('skills', []),
            'connections': data.get('connections'),
            'profile_url': profile_url
        }

        return basic_data

    except requests.exceptions.RequestException as e:
        return {
            'error': str(e),
            'message': 'Failed to fetch LinkedIn data. Make sure you have a valid API key.'
        }


def get_linkedin_data_mock(profile_url: str) -> dict:
    """
    Returns mock LinkedIn data for testing purposes.
    Use this while you set up your API access.

    Args:
        profile_url: The LinkedIn profile URL

    Returns:
        Dictionary containing mock profile data
    """
    return {
        'full_name': 'Sample User',
        'headline': 'Software Engineer at Tech Company',
        'summary': 'Experienced professional with expertise in software development.',
        'location': 'San Francisco',
        'country': 'United States',
        'profile_pic_url': None,
        'experiences': [
            {
                'title': 'Software Engineer',
                'company': 'Tech Company',
                'start_date': '2020-01',
                'end_date': None,
                'description': 'Working on innovative solutions'
            }
        ],
        'education': [
            {
                'school': 'University Name',
                'degree': 'Bachelor of Science',
                'field_of_study': 'Computer Science',
                'start_date': '2016',
                'end_date': '2020'
            }
        ],
        'skills': ['Python', 'JavaScript', 'SQL'],
        'connections': 500,
        'profile_url': profile_url
    }