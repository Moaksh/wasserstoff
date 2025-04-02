# LinkedIn Profile Scraper

This project implements an automated LinkedIn profile scraper using the browser-use library and LLM-driven agent technology. It can collect structured data from LinkedIn profiles based on search criteria provided by the user.

## Features

- **User Input**: Takes search queries from the command line to specify which types of profiles to scrape
- **Structured Data Collection**: Extracts profile information including name, URL, headline, location, and company
- **Caching Mechanism**: Implements a robust caching system to store previously fetched data and avoid re-scraping
- **Context Window Management**: Manages the LLM's context window by summarizing browser content and periodically clearing memory
- **Infinite Loop Prevention**: Tracks repeated actions to detect and break out of potential infinite loops
- **Error Handling**: Implements robust error handling with logging and retry mechanisms
- **Checkpointing**: Periodically saves progress to ensure data isn't lost in case of crashes
- **JSON Output**: Saves collected profiles in structured JSON format

## Requirements

- Python 3.8+
- browser-use library
- langchain-google-genai
- Gemini API key
- LinkedIn account credentials

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install browser-use langchain-google-genai tqdm
   ```
3. Create a `.env` file with the following variables:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   LINKEDIN_EMAIL=your_linkedin_email
   LINKEDIN_PASSWORD=your_linkedin_password
   ```

## Usage

Run the scraper with default settings (searches for "Software Engineer" profiles):

```
python linkedin_scraper.py
```

Specify a custom search query:

```
python linkedin_scraper.py --search "Data Scientist"
```

Customize the number of profiles to collect:

```
python linkedin_scraper.py --search "Product Manager" --max-profiles 300
```

Limit the maximum number of agent steps:

```
python linkedin_scraper.py --max-steps 50
```

## How It Works

1. **Initialization**: The scraper initializes the browser, LLM, and memory systems
2. **Authentication**: The agent logs into LinkedIn using provided credentials
3. **Search**: The agent searches for profiles matching the specified criteria
4. **Data Extraction**: For each profile in search results, the agent extracts structured data
5. **Pagination**: The agent navigates through multiple pages of search results
6. **Data Storage**: Extracted profiles are stored in both cache and output JSON files

## Optimization Strategies

- **Caching**: Implements a file-based caching system to avoid re-scraping profiles
- **Context Management**: Summarizes and truncates browser content to manage LLM token limits
- **Checkpointing**: Periodically saves progress to prevent data loss
- **Loop Detection**: Tracks repeated actions to prevent infinite loops
- **Error Handling**: Implements retry mechanisms and graceful error recovery

## Limitations

- LinkedIn may detect and block automated scraping attempts
- The scraper is dependent on LinkedIn's current UI structure
- Performance is limited by the speed of the LLM and browser interactions

## Future Improvements

- Implement parallel scraping with multiple browser instances
- Add more sophisticated data extraction for additional profile fields
- Implement proxy rotation to avoid IP-based blocking
- Add support for scraping connections and company pages