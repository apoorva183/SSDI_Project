# NinerMatch - Student Profile Matching System

A web application for matching students based on their academic profiles, skills, and interests.

## Project Structure

```
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── data/                  # Data files
│   └── courses.csv       # Course catalog
├── src/                  # Source code
│   ├── core/             # Core application modules
│   │   ├── config.py     # Configuration settings
│   │   ├── database.py   # Database management
│   │   └── models.py     # Data models
│   ├── resume_search/    # Resume search functionality
│   └── utils/            # Utility modules
│       ├── extract_text_from_pdf.py
│       ├── multi_agent_parse_llm.py
│       ├── similarity_matcher.py
│       ├── sync_mongodb_search.py
│       ├── init_resume_search.py
│       └── migrate_academic_data.py
├── static/               # CSS and JavaScript files
├── templates/            # HTML templates
└── uploads/              # Temporary file uploads
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables in `.env` file

3. Run the application:
   ```bash
   python app.py
   ```

## Features

- Resume parsing using LLM
- Student profile creation and management
- ML-based similarity matching
- MongoDB integration for data storage
- Search functionality for profile
- Swipe-based matching interface