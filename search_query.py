import re

def generate_search_query(pattern: str, pattern_type: str = "", start_date: str = None, end_date: str = None) -> str:
    """Generate a search query based on the regex pattern, pattern type, and optional date range."""
    # First try to get keywords from pattern type
    if pattern_type and pattern_type != "Custom Pattern" and pattern_type != "Custom (Empty)":
        keywords = pattern_type.lower().split()
        keywords = [w for w in keywords if w not in {'token', 'key', 'pattern', 'api'}]
        if keywords:
            query = keywords[0]
        else:
            query = ""
    else:
        query = ""
    
    # If no pattern type or it's custom, try to extract from pattern
    if not query:
        # If pattern is empty, custom, or Custom (Empty), return empty string
        if not pattern or pattern.lower() == "custom" or pattern_type == "Custom (Empty)":
            query = ""
        else:
            # Try to extract service name from pattern, as before
            known_prefixes = {
                "github": ["github", "gho_", "ghu_", "ghp_", "ghr_", "github_pat_"],
                "aws": ["AKIA", "ASIA", "AROA", "AIPA", "ANPA", "ANVA", "amzn"],
                "groq": ["gsk_"],
                "google": ["AIza", "AIzaSy", "AIzaSyA", "AIzaSyB", "AIzaSyC", "AIzaSyD", "AIzaSyE", "AIzaSyF", "AIzaSyG", "AIzaSyH", "AIzaSyI", "AIzaSyJ", "AIzaSyK", "AIzaSyL", "AIzaSyM", "AIzaSyN", "AIzaSyO", "AIzaSyP", "AIzaSyQ", "AIzaSyR", "AIzaSyS", "AIzaSyT", "AIzaSyU", "AIzaSyV", "AIzaSyW", "AIzaSyX", "AIzaSyY", "AIzaSyZ"]
            }
            for service, prefixes in known_prefixes.items():
                for prefix in prefixes:
                    if prefix.lower() in pattern.lower():
                        query = service
                        break
            if not query:
                service_match = re.search(r'\(([a-zA-Z0-9_\-]+)[a-z0-9_ \.,\-]{0,25}\)', pattern)
                if service_match:
                    query = service_match.group(1)
                else:
                    quote_match = re.search(r'[\'"][^\'"\s]{3,}[\'"]', pattern)
                    if quote_match:
                        query = quote_match.group(0).strip('\'"')
                    else:
                        const_match = re.search(r'[a-zA-Z_][a-zA-Z0-9_-]{2,}', pattern)
                        if const_match:
                            query = const_match.group(0)
                        else:
                            query = ""
    # If a date range is provided, do not add it here (it will be added in the API function)
    return query
