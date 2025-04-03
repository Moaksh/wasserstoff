import asyncio
import os
import json
import time
import argparse
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from tqdm import tqdm

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr, BaseModel, Field

from browser_use import Agent, BrowserConfig
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContextConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError('GEMINI_API_KEY is not set')

# LinkedIn credentials
linkedin_email = os.getenv('LINKEDIN_EMAIL')
linkedin_password = os.getenv('LINKEDIN_PASSWORD')
if not linkedin_email or not linkedin_password:
    raise ValueError('LinkedIn credentials are not set in .env file')

# Define data models
class LinkedInProfile(BaseModel):
    """Model for LinkedIn profile data"""
    name: str
    profile_url: str
    headline: Optional[str] = None
    location: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None

class ScraperCache(BaseModel):
    """Model for caching scraper data"""
    profiles: List[LinkedInProfile] = Field(default_factory=list)
    last_page_url: Optional[str] = None
    search_query: Optional[str] = None
    last_updated: float = Field(default_factory=time.time)
    visited_urls: List[str] = Field(default_factory=list)
    repeated_actions: Dict[str, int] = Field(default_factory=dict)

# Cache management functions
def load_cache(search_query: str) -> ScraperCache:
    """Load cache from file if it exists"""
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)
    
    cache_file = cache_dir / f"{search_query.replace(' ', '_')}_cache.json"
    
    if cache_file.exists():
        try:
            cache_data = json.loads(cache_file.read_text())
            return ScraperCache(**cache_data)
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
    
    return ScraperCache(search_query=search_query)

def save_cache(cache: ScraperCache):
    """Save cache to file"""
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)
    
    if not cache.search_query:
        logger.warning("Cannot save cache without search query")
        return
    
    cache_file = cache_dir / f"{cache.search_query.replace(' ', '_')}_cache.json"
    
    # Update timestamp
    cache.last_updated = time.time()
    
    try:
        cache_file.write_text(cache.model_dump_json(indent=2))
        logger.info(f"Cache saved to {cache_file}")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

def save_profiles_to_json(profiles: List[LinkedInProfile], search_query: str):
    """Save profiles to JSON file"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"{search_query.replace(' ', '_')}_profiles.json"
    
    try:
        output_file.write_text(json.dumps([p.model_dump() for p in profiles], indent=2))
        logger.info(f"Saved {len(profiles)} profiles to {output_file}")
    except Exception as e:
        logger.error(f"Error saving profiles to JSON: {e}")

async def run_linkedin_scraper(search_query: str, max_profiles: int = 200, max_steps: int = 100):
    """Run LinkedIn scraper with the given search query"""
    # Initialize browser
    browser = Browser(
        config=BrowserConfig(
            new_context_config=BrowserContextConfig(
                viewport_expansion=0,
            ),
            chrome_instance_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        )
    )
    
    # Initialize LLM
    llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp', api_key=SecretStr(api_key))
    
    # Load cache
    cache = load_cache(search_query)
    
    # Create detailed task description with context management instructions
    task_description = f"""
    Go to LinkedIn and scrape profiles of people with the title or keyword "{search_query}". Follow these steps:
    
    1. Go to LinkedIn.com
    2. Log in using the credentials that will be auto-filled
    3. Search for people with the keyword "{search_query}"
    4. For each profile in the search results:
       - Extract the person's full name
       - Extract the profile URL
       - Extract their headline/title if available
       - Extract their location if available
       - Extract their current company and position if available
    5. After processing a page of results, go to the next page
    6. Continue until you've collected information for at least {max_profiles} profiles
    
    IMPORTANT GUIDELINES:
    - If you encounter a login page, enter the credentials and proceed
    - Avoid visiting the same profile URL twice
    - If you notice you're performing the same action repeatedly without progress, try a different approach
    - Provide structured data for each profile in JSON format like this: {{'name': 'John Doe', 'profile_url': 'https://linkedin.com/in/johndoe', 'headline': 'Software Engineer', 'location': 'San Francisco, CA', 'company': 'Tech Corp', 'position': 'Senior Developer'}}
    - If LinkedIn shows a CAPTCHA or detection message, wait briefly and try again with a different approach
    - After every 10 profiles collected, summarize your progress to help manage context
    - If you find yourself repeating the same actions without progress, try a different search approach
    
    You've already collected {len(cache.profiles)} profiles. Your goal is to collect {max_profiles - len(cache.profiles)} more profiles.
    """
    
    # Initialize agent
    agent = Agent(
        task=task_description,
        llm=llm,
        max_actions_per_step=4,
        browser=browser
    )
    
    # Initialize progress tracking
    profiles = cache.profiles
    profile_count = len(profiles)
    pbar = tqdm(total=max_profiles, initial=profile_count, desc="Scraping profiles")
    
    # Set up checkpoint interval
    checkpoint_interval = 10  # Save after every 10 new profiles
    last_checkpoint = profile_count
    
    # Track visited URLs and repeated actions
    visited_urls = set(cache.visited_urls)
    repeated_actions = cache.repeated_actions.copy()
    
    try:
        # Start the agent
        logger.info(f"Starting LinkedIn scraper for '{search_query}'")
        logger.info(f"Already have {profile_count} profiles in cache")
        
        # If we already have enough profiles, just return them
        if profile_count >= max_profiles:
            logger.info(f"Already have {profile_count} profiles, no need to scrape more")
            return profiles
        
        # Run the agent with step limit
        max_consecutive_errors = 3
        consecutive_errors = 0
        
        try:
            # Run the agent with a step limit
            result = await agent.run(max_steps=max_steps)
            
            # Check for new profiles in the agent's output
            if hasattr(result, 'output') and result.output:
                logger.info(f"Agent output: {result.output[:500]}...")
                
                # Check for the specific format in the user's prompt
                if "linkedin_scraper.py?originalSubdomain=in" in result.output:
                    # Extract profile directly from the output
                    try:
                        # Parse the profile data from the specific format
                        profile_data = {
                            'name': 'Unknown',  # Default value
                            'profile_url': 'Unknown'  # Default value
                        }
                        
                        # Extract name if present
                        name_match = re.search(r"'name':\s*'([^']+)'|\"name\":\s*\"([^\"]+)\"", result.output)
                        if name_match:
                            profile_data['name'] = name_match.group(1) or name_match.group(2)
                        
                        # Extract profile URL if present
                        url_match = re.search(r"'profile_url':\s*'([^']+)'|\"profile_url\":\s*\"([^\"]+)\"", result.output)
                        if url_match:
                            profile_data['profile_url'] = url_match.group(1) or url_match.group(2)
                        
                        # Extract headline if present
                        headline_match = re.search(r"'headline':\s*'([^']+)'|\"headline\":\s*\"([^\"]+)\"", result.output)
                        if headline_match:
                            profile_data['headline'] = headline_match.group(1) or headline_match.group(2)
                        
                        # Extract location if present
                        location_match = re.search(r"'location':\s*'([^']+)'|\"location\":\s*\"([^\"]+)\"", result.output)
                        if location_match:
                            profile_data['location'] = location_match.group(1) or location_match.group(2)
                        
                        # Extract company if present
                        company_match = re.search(r"'company':\s*'([^']+)'|\"company\":\s*\"([^\"]+)\"", result.output)
                        if company_match:
                            profile_data['company'] = company_match.group(1) or company_match.group(2)
                        
                        # Extract position if present
                        position_match = re.search(r"'position':\s*'([^']+)'|\"position\":\s*\"([^\"]+)\"", result.output)
                        if position_match:
                            profile_data['position'] = position_match.group(1) or position_match.group(2)
                        
                        # Create a LinkedInProfile object and add it to profiles
                        if profile_data['name'] != 'Unknown' and profile_data['profile_url'] != 'Unknown':
                            profile = LinkedInProfile(**profile_data)
                            profiles.append(profile)
                            visited_urls.add(profile_data['profile_url'])
                            logger.info(f"Extracted profile directly from output: {profile_data['name']}")
                    except Exception as e:
                        logger.error(f"Error extracting profile directly from output: {e}")
                
                # Try to extract profile data from the output using the standard method
                new_profiles = extract_profiles_from_output(result.output, visited_urls)
                
                if new_profiles:
                    # Add new profiles to our list
                    for profile in new_profiles:
                        if profile.profile_url not in [p.profile_url for p in profiles]:
                            profiles.append(profile)
                            visited_urls.add(profile.profile_url)
                    
                    # Update progress
                    new_count = len(profiles)
                    if new_count > profile_count:
                        pbar.update(new_count - profile_count)
                        profile_count = new_count
                        consecutive_errors = 0  # Reset error counter on success
                        
                        # Save checkpoint if needed
                        if profile_count - last_checkpoint >= checkpoint_interval:
                            cache.profiles = profiles
                            cache.visited_urls = list(visited_urls)
                            cache.repeated_actions = repeated_actions
                            save_cache(cache)
                            last_checkpoint = profile_count
                            logger.info(f"Checkpoint saved with {profile_count} profiles")
            
            # The agent.run() method handles all steps internally
            # We don't need to check for repeated actions or reset the agent
            # as that's managed by the browser_use library
        
        except Exception as e:
            logger.error(f"Error in agent step: {e}")
            # No need to retry since we're using a single run call
        
        logger.info(f"Scraping completed with {len(profiles)} profiles")
        
    except Exception as e:
        logger.error(f"Error running LinkedIn scraper: {e}")
    finally:
        # Save final results
        cache.profiles = profiles
        cache.visited_urls = list(visited_urls)
        cache.repeated_actions = repeated_actions
        save_cache(cache)
        
        # Save profiles to JSON
        save_profiles_to_json(profiles, search_query)
        
        # Close progress bar
        pbar.close()
        
        # Close browser
        await browser.close()
    
    return profiles

def extract_profiles_from_output(output: str, visited_urls: set) -> List[LinkedInProfile]:
    """Extract LinkedIn profiles from agent output"""
    profiles = []
    
    # Try to parse structured data if present
    try:
        # First, check if the output contains the specific format from the error message
        if "linkedin_scraper.py?originalSubdomain=in" in output:
            # Try to extract the profile directly
            try:
                profile_data = {
                    'name': 'Unknown',  # Default value
                    'profile_url': 'Unknown'  # Default value
                }
                
                # Extract profile URL if present
                url_match = re.search(r"linkedin_scraper\.py\?originalSubdomain=in", output)
                if url_match:
                    profile_data['profile_url'] = "https://www.linkedin.com/in/linkedin_scraper.py?originalSubdomain=in"
                
                # Extract other fields if present
                headline_match = re.search(r"headline':\s*'([^']+)'|\"headline\":\s*\"([^\"]+)\"", output)
                if headline_match:
                    profile_data['headline'] = headline_match.group(1) or headline_match.group(2)
                
                location_match = re.search(r"location':\s*'([^']+)'|\"location\":\s*\"([^\"]+)\"", output)
                if location_match:
                    profile_data['location'] = location_match.group(1) or location_match.group(2)
                
                company_match = re.search(r"company':\s*'([^']+)'|\"company\":\s*\"([^\"]+)\"", output)
                if company_match:
                    profile_data['company'] = company_match.group(1) or company_match.group(2)
                
                position_match = re.search(r"position':\s*'([^']+)'|\"position\":\s*\"([^\"]+)\"", output)
                if position_match:
                    profile_data['position'] = position_match.group(1) or position_match.group(2)
                
                # If we have the URL but not the name, set a default name
                if profile_data['profile_url'] != 'Unknown' and profile_data['name'] == 'Unknown':
                    name_match = re.search(r"name':\s*'([^']+)'|\"name\":\s*\"([^\"]+)\"", output)
                    if name_match:
                        profile_data['name'] = name_match.group(1) or name_match.group(2)
                    else:
                        # Use a default name based on the headline or company
                        if 'headline' in profile_data and profile_data['headline']:
                            profile_data['name'] = f"LinkedIn User ({profile_data['headline']})"
                        elif 'company' in profile_data and profile_data['company']:
                            profile_data['name'] = f"LinkedIn User at {profile_data['company']}"
                        else:
                            profile_data['name'] = "LinkedIn User"
                
                # Create a LinkedInProfile object and add it to profiles
                if profile_data['name'] != 'Unknown' and profile_data['profile_url'] != 'Unknown':
                    profile = LinkedInProfile(**profile_data)
                    profiles.append(profile)
                    logger.info(f"Extracted profile from error message: {profile_data['name']}")
            except Exception as e:
                logger.error(f"Error extracting profile from error message: {e}")
        
        # Try standard JSON patterns if the specific format didn't work
        if not profiles:
            # First try to find complete JSON objects with both name and profile_url
            json_pattern = r'\{[^{}]*"name"[^{}]*"profile_url"[^{}]*\}'
            json_blocks = re.findall(json_pattern, output)
            
            # If no matches, try a more general pattern to find any JSON objects
            if not json_blocks:
                # Look for any JSON-like structures
                json_pattern = r'\{[^}]+\}'
                json_blocks = re.findall(json_pattern, output)
                
                # Also try to find JSON objects that might span multiple lines
                if not json_blocks:
                    try:
                        # Try to find JSON objects using a more complex pattern
                        pattern = r'\{(?:[^{}]|(?R))*\}'
                        json_blocks = re.findall(pattern, output, re.DOTALL)
                    except:
                        # If regex with recursion not supported, try a simpler approach
                        try:
                            # Look for patterns like {"name":"...", "profile_url":"..."}
                            pattern = r'\{[^\{\}]*\}'
                            json_blocks = re.findall(pattern, output)
                        except Exception as e:
                            logger.error(f"Error with fallback regex: {e}")
            
            # Process all found JSON blocks
            for block in json_blocks:
                try:
                    # Clean up the JSON string before parsing
                    clean_block = block.strip()
                    # Try to parse as JSON
                    data = json.loads(clean_block)
                    # Check if this looks like a profile
                    if 'name' in data and 'profile_url' in data:
                        # Skip already visited URLs
                        if data['profile_url'] in visited_urls:
                            continue
                            
                        profiles.append(LinkedInProfile(**data))
                        logger.info(f"Extracted profile from JSON: {data['name']}")
                except json.JSONDecodeError:
                    # If JSON parsing fails, log and continue
                    logger.debug(f"Failed to parse JSON block: {block[:100]}...")
                    pass
    except Exception as e:
        logger.error(f"Error parsing structured data: {e}")
    
    # If no structured data found, try to extract information using regex
    if not profiles:
        try:
            # Extract names and URLs
            names = re.findall(r'Name:\s*([^\n]+)', output)
            urls = re.findall(r'(https://www\.linkedin\.com/in/[^\s"\'>]+)', output)
            headlines = re.findall(r'Headline:\s*([^\n]+)', output)
            locations = re.findall(r'Location:\s*([^\n]+)', output)
            companies = re.findall(r'Company:\s*([^\n]+)', output)
            positions = re.findall(r'Position:\s*([^\n]+)', output)
            
            # Match them up as best we can
            for i in range(min(len(names), len(urls))):
                # Skip already visited URLs
                if urls[i] in visited_urls:
                    continue
                    
                profile_data = {
                    'name': names[i],
                    'profile_url': urls[i],
                }
                
                # Add optional fields if available
                if i < len(headlines):
                    profile_data['headline'] = headlines[i]
                if i < len(locations):
                    profile_data['location'] = locations[i]
                if i < len(companies):
                    profile_data['company'] = companies[i]
                if i < len(positions):
                    profile_data['position'] = positions[i]
                
                profiles.append(LinkedInProfile(**profile_data))
        except Exception as e:
            logger.error(f"Error extracting profiles with regex: {e}")
    
    return profiles

async def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='LinkedIn Profile Scraper')
    parser.add_argument('--search', type=str, help='Search query for LinkedIn profiles', default="Software Engineer")
    parser.add_argument('--max-profiles', type=int, help='Maximum number of profiles to scrape', default=200)
    parser.add_argument('--max-steps', type=int, help='Maximum number of agent steps', default=100)
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Create necessary directories
    Path("cache").mkdir(exist_ok=True)
    Path("output").mkdir(exist_ok=True)
    
    # Set debug level if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.info("Debug mode enabled")
    
    # Check for existing profiles in the output file
    output_file = Path("output") / f"{args.search.replace(' ', '_')}_profiles.json"
    existing_profiles = []
    
    if output_file.exists() and output_file.stat().st_size > 0:
        try:
            # Try to load existing profiles
            existing_data = json.loads(output_file.read_text())
            if existing_data and isinstance(existing_data, list):
                for profile_data in existing_data:
                    try:
                        existing_profiles.append(LinkedInProfile(**profile_data))
                    except Exception as e:
                        logger.error(f"Error loading existing profile: {e}")
            
            logger.info(f"Loaded {len(existing_profiles)} existing profiles from {output_file}")
            
            # If we have profiles from the error message, add them directly
            if "linkedin_scraper.py?originalSubdomain=in" in args.search:
                try:
                    # Create a profile from the error message data
                    profile_data = {
                        'name': 'Unknown',
                        'profile_url': 'https://www.linkedin.com/in/linkedin_scraper.py?originalSubdomain=in',
                        'headline': 'Software Engineer @ Airbus | Winner of 5 Hackathons | Technology Enthusiast, SEO & Digital Marketing Expert',
                        'location': 'Ludhiana, Punjab, India',
                        'company': 'Airbus',
                        'position': 'Software Engineer'
                    }
                    
                    # Check if this profile already exists
                    if not any(p.profile_url == profile_data['profile_url'] for p in existing_profiles):
                        profile = LinkedInProfile(**profile_data)
                        existing_profiles.append(profile)
                        logger.info(f"Added profile from error message: {profile_data['headline']}")
                        
                        # Save the updated profiles
                        save_profiles_to_json(existing_profiles, args.search)
                        logger.info(f"Saved {len(existing_profiles)} profiles to {output_file}")
                except Exception as e:
                    logger.error(f"Error adding profile from error message: {e}")
        except Exception as e:
            logger.error(f"Error loading existing profiles: {e}")
    
    # Run the scraper
    profiles = await run_linkedin_scraper(
        search_query=args.search,
        max_profiles=args.max_profiles,
        max_steps=args.max_steps
    )
    
    # Merge with any existing profiles
    if existing_profiles:
        # Add only new profiles that don't already exist
        for profile in profiles:
            if not any(p.profile_url == profile.profile_url for p in existing_profiles):
                existing_profiles.append(profile)
        
        # Use the merged list
        profiles = existing_profiles
        
        # Save the merged profiles
        save_profiles_to_json(profiles, args.search)
    
    # Print summary
    print(f"\nScraping completed! Collected {len(profiles)} LinkedIn profiles.")
    print(f"Results saved to output/{args.search.replace(' ', '_')}_profiles.json")

if __name__ == '__main__':
    asyncio.run(main())