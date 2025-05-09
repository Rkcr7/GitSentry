# GitSentry

![GitSentry](https://img.shields.io/badge/Security-Token%20Scanning-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-red)

A powerful tool for scanning GitHub repositories to identify exposed API tokens and secrets using regular expressions. Built with Streamlit for an interactive user interface.

## 🔍 Overview

GitSentry helps security professionals and developers identify exposed API keys, tokens, and credentials in public GitHub repositories. It leverages GitHub's Code Search API to find potentially sensitive information using customizable regex patterns.

### Features

- 📋 **Extensive Token Pattern Library**: Pre-configured with 200+ regex patterns for common API tokens and secrets
- 🔍 **Custom Search Queries**: Use custom search queries or let the app generate optimized queries
- ⚡ **Extended Search**: Bypass GitHub's 1000 result limit with extended search functionality
- 🚀 **Multi-threading**: Efficient background processing with real-time UI updates
- 🔄 **Token Rotation**: Automatic rotation of GitHub tokens to handle rate limits
- 💾 **Result Export**: Download results in JSON format for further analysis

## ⚠️ Ethical Usage & Disclaimer

**This tool is intended for educational purposes and legitimate security auditing only.**

- Only scan repositories you own or have explicit permission to scan
- Report exposed tokens to appropriate owners
- Don't use discovered tokens for unauthorized access
- Follow GitHub's Terms of Service and rate limiting policies

**The authors accept no responsibility for misuse of this tool or its findings.**

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- A GitHub personal access token with `read:public_repo` scope

### Setting Up GitHub Personal Access Tokens

1. Go to your GitHub Settings > Developer settings > Personal access tokens
2. Create a new token with the `read:public_repo` scope
3. For extended searches, consider creating multiple tokens to handle rate limiting effectively

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Rkcr7/GitSentry.git
   cd GitSentry
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   
   The repository includes a `.env.example` file with sample configurations:
   
   ```bash
   # Copy the example file
   cp .env.example .env
   
   # Edit the .env file with your own tokens
   nano .env  # or use any text editor
   ```
   
   At minimum, you need to add your GitHub token(s):
   ```
   GITHUB_TOKEN=your_github_token_here
   # OR for multiple tokens (recommended for extended searches)
   GITHUB_TOKENS=token1,token2,token3
   ```

## 💻 Usage

### Starting the Application

1. Start the application:
   ```bash
   streamlit run app.py
   ```

2. Open the provided URL in your browser (typically http://localhost:8501)

### Step-by-Step Workflow

1. **Select a Token Pattern**:
   - Choose from the dropdown of pre-configured token patterns
   - Use the search box to filter available patterns
   - Select "Custom (Empty)" to create your own regex pattern from scratch
   - Edit any pattern if needed to refine your search

2. **Configure Search Parameters**:
   - Enable "Use Custom Search Query" to provide your own search query
   - If disabled, a search query will be automatically generated based on your selected token pattern
   - Set the "Result Limit" to control maximum number of results (1-999)
   - For thorough searches, enable "Extended Search"
   - For extended searches, consider adjusting the cooldown time to prevent rate limiting

3. **Start the Search**:
   - Click "Start Scraping" to begin
   - The app will display a progress indicator and status updates
   - For extended searches, you'll see cooling down periods between batches

4. **Review Results**:
   - After the search completes, results will be processed and displayed
   - A summary will show total repositories scanned and unique tokens found
   - Detailed results can be viewed and downloaded

5. **Export and Analysis**:
   - Download token lists in JSON format
   - Download detailed results including file paths and context
   - Analyze results offline or in other tools

### Understanding Search Types

#### Standard Search

Standard searches use GitHub's Code Search API directly with your query. They're limited to 1000 results by GitHub's API constraints but are faster and require fewer tokens.

#### Extended Search

Extended searches break down your query into multiple smaller searches by appending filename prefixes (a-z, 0-9). This bypasses GitHub's 1000 result limit but requires:

1. Multiple GitHub tokens (recommended)
2. Longer execution time
3. Cooldown periods between batches to prevent rate limiting

During extended searches, the system:
- Splits your search into batches based on filename prefixes
- Allocates tokens from your token pool for parallel processing
- Enforces cooldown periods between batches (configurable)
- Deduplicates results across all searches

## 🔍 Understanding GitHub API Rate Limits

GitHub enforces rate limits on API usage:
- 10 requests per minute for search operations with authenticated requests
- 1,000 results maximum per search query

### How GitSentry Handles Rate Limits

1. **Token Rotation**: 
   - When multiple tokens are provided, the app rotates through them
   - Each token can make 10 search requests per minute
   - More tokens = higher throughput

2. **Cooldown Periods**:
   - Extended searches automatically implement cooldown periods between batches
   - Default cooldown is 40 seconds but can be adjusted
   - Lower cooldown time = faster searches but higher chance of hitting rate limits
   - Higher cooldown time = slower searches but more reliable

3. **Batch Processing**:
   - The app processes results in batches to stay within GitHub limits
   - During cooling down periods, the app pauses to let rate limits reset

4. **Rate Limit Error Handling**:
   - If a rate limit is hit, the app will pause, rotate tokens, and retry
   - The app tracks rate limit hits for monitoring

## 📊 Search Results and Analysis

Results are saved in two formats:
- **Tokens JSON**: Just the extracted tokens for quick review
- **Detailed Results**: Complete information including repository details, file paths, and context

### Understanding the Results

1. **Repository Information**: The GitHub repo where tokens were found
2. **File Path**: The specific file containing the match
3. **URL**: Direct link to the file on GitHub
4. **Last Modified**: When the file was last updated
5. **Found Tokens**: The actual tokens/credentials discovered
6. **Context**: Code fragments showing the tokens in context

### Analyzing the Results

- Review each match for legitimacy - regex patterns may create false positives
- Check the context to understand how the token is being used
- Consider token expiration and creation dates (often visible in the commit history)

## 🔧 Advanced Configuration

### Custom Token Patterns

Add your own token patterns by editing `token_patterns.json`:

```json
{
  "Your Pattern Name": "your_regex_pattern"
}
```

Effective regex patterns should:
- Be specific enough to minimize false positives
- Capture the full token structure including prefixes
- Include validation characteristics (length, charset, etc.)

### Performance Tuning

For large-scale searches:
- Use multiple GitHub tokens (5+ recommended for extended searches)
- Increase cooldown time to 60-120 seconds for very large searches
- Consider splitting large searches into multiple smaller searches
- Run during off-peak hours to minimize impact of rate limits

### Troubleshooting

**Search Fails Immediately**:
- Check that your GitHub token(s) are valid
- Ensure your `.env` file is in the correct location

**Rate Limiting Issues**:
- Add more GitHub tokens
- Increase cooldown time
- Retry during off-peak hours

**No Results Found**:
- Check your regex pattern using regex testing tools
- Try a broader search query
- Ensure you're not hitting GitHub's query length limits

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 👏 Acknowledgements

- GitHub API for providing code search capabilities
- Streamlit for the interactive web interface
- All contributors to the token pattern database 