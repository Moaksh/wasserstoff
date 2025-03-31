# AI Email Assistant

A web-based email assistant that uses AI to help manage and interact with emails efficiently.

## Project Structure

```
├── src/                    # Main source code
│   ├── auth/              # Authentication handling
│   ├── email_client/      # Email client implementation
│   ├── database/          # Database operations
│   ├── llm/               # Language Model integration
│   ├── tools/             # Utility tools
│   └── utils/             # Helper functions
├── templates/             # HTML templates
├── static/                # Static assets
├── credentials/           # API credentials (gitignored)
├── data/                  # Persistent data storage
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
└── .env                   # Environment variables
```

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   - Copy `.env.example` to `.env`
   - Update with your configuration

4. Set up Google OAuth credentials:
   - Place your credentials in `credentials/credentials.json`

5. Run the application:
   ```bash
   python app.py
   ```

## Features

- OAuth-based email authentication
- Web interface for email management
- AI-powered email processing (coming soon)
- Email organization and categorization

## Development

- Follow PEP 8 style guide
- Write tests for new features
- Keep sensitive information in .env file