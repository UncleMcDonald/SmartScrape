# Data Processing Portal

A Flask application that:
1. Takes URL and prompt as input
2. Scrapes web content
3. Processes it with OpenAI GPT
4. Exports structured data as CSV

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set your OpenAI API key:
   ```
   export OPENAI_API_KEY="your-key-here"
   ```

3. Run the application:
   ```
   python run.py
   ```

## API Endpoints

- POST `/process`: Submit URL and prompt for processing
- GET `/download/<filename>`: Download the generated CSV file 