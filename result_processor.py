import re
import json
from datetime import datetime

def extract_matches(snippet: str, pattern: str) -> list:
    """Extract all matches of the pattern in the snippet."""
    try:
        regex = re.compile(pattern)
        matches = regex.findall(snippet)
        return matches
    except re.error:
        return []

def process_results(results: list, pattern: str) -> list:
    """Process search results and extract matches."""
    processed = []
    total_matches = 0
    total_unique_matches = 0
    all_unique_tokens = set()
    
    for item in results:
        text_matches = item.get("text_matches", [])
        collected = []
        fragments = []  # Store the original fragments
        for tm in text_matches:
            fragment = tm.get("fragment", "")
            fragments.append(fragment)  # Store the fragment
            matches = extract_matches(fragment, pattern)
            if matches:
                total_matches += len(matches)
                collected.extend(matches)
        
        if collected:
            # Deduplicate tokens for this file
            unique_tokens = list(set(collected))
            total_unique_matches += len(unique_tokens)
            all_unique_tokens.update(unique_tokens)
            
            # Try to get the most relevant date from multiple possible fields
            last_modified = None
            try:
                # Try different date fields in order of preference
                if item.get("repository", {}).get("pushed_at"):
                    last_modified = item["repository"]["pushed_at"]
                elif item.get("repository", {}).get("updated_at"):
                    last_modified = item["repository"]["updated_at"]
                elif item.get("repository", {}).get("created_at"):
                    last_modified = item["repository"]["created_at"]
                
                if last_modified:
                    last_modified = datetime.strptime(
                        last_modified,
                        "%Y-%m-%dT%H:%M:%SZ"
                    ).strftime("%Y-%m-%d %H:%M:%S UTC")
            except (ValueError, KeyError):
                pass
            
            result_info = {
                "repository": item.get("repository", {}).get("full_name"),
                "file_path": item.get("path"),
                "html_url": item.get("html_url"),
                "last_modified": last_modified or "N/A",
                "found_tokens": unique_tokens,
                "total_matches_in_file": len(collected),  # Total matches before deduplication
                "unique_matches_in_file": len(unique_tokens),  # Unique matches in this file
                "found_date": datetime.now().strftime("%d:%m:%Y"),
                "fragments": fragments
            }
            processed.append(result_info)
    
    # Add match statistics to the first result if we have any results
    if processed:
        processed[0]["match_statistics"] = {
            "total_files_with_matches": len(processed),
            "total_matches_found": total_matches,
            "total_unique_matches_in_files": total_unique_matches,
            "total_unique_tokens_overall": len(all_unique_tokens)
        }
    
    return processed

def sanitize_filename(filename):
    # Replace problematic characters
    invalid_chars = [':', '/', '\\', '?', '*', '"', '<', '>', '|']
    for char in invalid_chars:
        filename = filename.replace(char, '-')
    return filename

def save_results(results: list, pattern: str) -> tuple:
    """Save results to JSON files and return file paths and error status."""
    timestamp = datetime.now().strftime("%d:%m:%Y_%H:%M:%S")
    formatted_date = datetime.now().strftime("%d:%m:%Y")
    match_stats = results[0].get("match_statistics", {}) if results else {}
    
    all_tokens = []
    for result in results:
        all_tokens.extend(result["found_tokens"])
    all_tokens = list(set(all_tokens))
    
    base_filename_tokens = f"tokens_only_results_{timestamp}.json" # Differentiated filename
    tokens_file = sanitize_filename(base_filename_tokens)
    
    base_filename_detailed = f"detailed_results_{timestamp}.json"
    detailed_file = sanitize_filename(base_filename_detailed)
    
    error_occurred = False
    error_message = ""

    try:
        with open(tokens_file, "w", encoding='utf-8') as f: # Added encoding
            json.dump({
                "tokens": all_tokens,
                "total_unique_tokens": len(all_tokens),
                "pattern": pattern,
                "scan_date": formatted_date,
                "scan_time": datetime.now().strftime("%H:%M:%S"),
                "match_statistics": match_stats
            }, f, indent=4)
    except (IOError, OSError, json.JSONDecodeError) as e:
        error_occurred = True
        error_message += f"Error saving tokens file ({tokens_file}): {str(e)}\n"
        # Do not log here, will be logged/shown by app.py

    try:
        with open(detailed_file, "w", encoding='utf-8') as f: # Added encoding
            json.dump({
                "pattern": pattern,
                "scan_date": formatted_date,
                "scan_time": datetime.now().strftime("%H:%M:%S"),
                "match_statistics": match_stats,
                "results": results
            }, f, indent=4)
    except (IOError, OSError, json.JSONDecodeError) as e:
        error_occurred = True
        error_message += f"Error saving detailed results file ({detailed_file}): {str(e)}"
        # Do not log here
    
    if error_occurred:
        return None, None, error_message # Return error message
    else:
        return tokens_file, detailed_file, None # Return None for error message 