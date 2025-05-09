import time
import requests
from config import get_token_rotator
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import threading
import streamlit as st
from queue import Queue
import threading
import sys
from contextlib import contextmanager

# Configure logging with UTF-8 encoding
class UTF8StreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Write with UTF-8 encoding
            if sys.version_info >= (3, 7):
                stream.buffer.write(msg.encode('utf-8'))
                stream.buffer.write(self.terminator.encode('utf-8'))
            else:
                stream.buffer.write(bytes(msg + self.terminator, 'utf-8'))
            self.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        UTF8StreamHandler(sys.stdout),
        logging.FileHandler("github_search.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Initialize thread local storage
thread_local = threading.local()

# Initialize session state for UI updates
if 'update_queue' not in st.session_state:
    st.session_state.update_queue = Queue()
    st.session_state.main_thread_id = threading.current_thread().ident

def is_main_thread():
    """Check if current thread is the main Streamlit thread"""
    return threading.current_thread().ident == st.session_state.main_thread_id

def queue_ui_update(update_type: str, content: Dict):
    """Queue a UI update to be processed in the main thread"""
    if 'update_queue' in st.session_state:
        st.session_state.update_queue.put((update_type, content))
        # If we're in the main thread, process updates immediately
        if is_main_thread():
            process_ui_updates()

def process_ui_updates():
    """Process queued UI updates in the main thread"""
    if 'update_queue' not in st.session_state or not is_main_thread():
        return
    
    while not st.session_state.update_queue.empty():
        try:
            update_type, content = st.session_state.update_queue.get_nowait()
            if update_type == 'status':
                if content['status_text']:
                    content['status_text'].markdown(f"""
📁 **Pattern Status:**
{content['current_pattern']}

🔑 **Token Status:**
{content['token_msg']}

{content.get('msg', '')}
""")
            elif update_type == 'progress':
                if content['progress_bar']:
                    content['progress_bar'].progress(content['value'])
            elif update_type == 'markdown':
                if content['status_text']:
                    content['status_text'].markdown(content['content'])
            elif update_type == 'error':
                if content['status_text']:
                    content['status_text'].error(content['error_msg'])
        except Exception as e:
            logger.error(f"Error processing UI update: {str(e)}")

def update_status(status_text, current_pattern: str, token_msg: str, msg: str = ""):
    """Queue a status update"""
    queue_ui_update('status', {
        'status_text': status_text,
        'current_pattern': current_pattern,
        'token_msg': token_msg,
        'msg': msg
    })

def update_progress_bar(progress_bar, value):
    """Queue a progress bar update"""
    queue_ui_update('progress', {
        'progress_bar': progress_bar,
        'value': value
    })

def update_markdown(status_text, content):
    """Queue a markdown update"""
    queue_ui_update('markdown', {
        'status_text': status_text,
        'content': content
    })

def update_error(status_text, error_msg):
    """Queue an error update"""
    queue_ui_update('error', {
        'status_text': status_text,
        'error_msg': error_msg
    })

def search_github(query: str, limit: int, progress_bar=None, status_text=None, extended=False, cooldown_time=40):
    """
    Search GitHub code using the Search API.
    
    If extended is True, split the query by appending filename qualifiers (a-z, 0-9)
    to bypass the 1,000 result limit and process in parallel.
    
    Otherwise, run a single query.
    
    Args:
        query: The search query
        limit: Maximum number of results to return
        progress_bar: Streamlit progress bar element to update
        status_text: Streamlit container for status updates
        extended: Whether to use extended search (multiple queries)
        cooldown_time: Time in seconds to wait between batches (default: 40)
    """
    if extended:
        # Include all alphanumeric characters for complete coverage
        partition_chars = [".", "_"] + list("abcdefghijklmnopqrstuvwxyz019")
        all_results = []
        total_chars = len(partition_chars)
        
        logger.info(f"Starting extended parallel search with {total_chars} filename patterns")
        update_markdown(status_text, f"""
📁 **Search Status:**
Starting extended parallel search with {total_chars} filename patterns...
(Using all alphanumeric characters to ensure complete coverage)
Cooldown between batches: {cooldown_time} seconds
""")
        process_ui_updates()

        # Get token rotator and calculate parallel workers
        token_rotator = get_token_rotator()
        total_tokens = token_rotator.get_total_token_count()
        parallel_workers = min(13, total_tokens - 7)  # Keep 3 tokens in reserve
        batch_size = min(parallel_workers, 13)  # Limit concurrent requests to avoid connection issues
        
        if total_tokens < (batch_size + 7):
            logger.warning(f"Not enough tokens available for optimal parallel processing. Have {total_tokens} tokens, need {batch_size + 3}.")
            batch_size = max(1, total_tokens - 7)
            logger.info(f"Adjusted to {batch_size} parallel workers")
        
        if batch_size < 1:
            logger.warning("Not enough tokens available for parallel processing. Falling back to sequential processing.")
            return search_github(query, limit, progress_bar, status_text, extended=False)
        
        # Split patterns into batches
        pattern_batches = [partition_chars[i:i + batch_size] for i in range(0, len(partition_chars), batch_size)]
        
        for batch_idx, batch in enumerate(pattern_batches, 1):
            logger.info(f"Processing batch {batch_idx}/{len(pattern_batches)} with {len(batch)} patterns")
            update_markdown(status_text, f"""
📁 **Batch Status:**
Processing batch {batch_idx}/{len(pattern_batches)}
Patterns in this batch: {len(batch)}
""")
            # Update overall progress bar based on batch completion
            if progress_bar:
                update_progress_bar(progress_bar, batch_idx / len(pattern_batches))

            # Allocate tokens for this batch with retries
            max_token_retries = 3
            token_retry_count = 0
            while token_retry_count < max_token_retries:
                tokens = token_rotator.allocate_tokens(len(batch))
                if len(tokens) == len(batch):
                    break
                logger.warning(f"Could only allocate {len(tokens)} tokens, needed {len(batch)}. Retrying in 5 seconds...")
                time.sleep(5)
                token_retry_count += 1
            
            if not tokens:
                logger.error("Failed to allocate any tokens for batch")
                continue
            
            if len(tokens) < len(batch):
                logger.warning(f"Could only allocate {len(tokens)} tokens. Reducing batch size.")
                batch = batch[:len(tokens)]
            
            # Process patterns in parallel with connection retries
            batch_results = []
            with ThreadPoolExecutor(max_workers=len(batch)) as executor:
                future_to_pattern = {
                    executor.submit(
                        search_github_single,
                        f"{query} filename:{char}",
                        limit,
                        progress_bar,
                        status_text,
                        f"Pattern {char} in batch {batch_idx}",
                        token
                    ): char for char, token in zip(batch, tokens)
                }
                
                completed = 0
                for future in as_completed(future_to_pattern):
                    pattern = future_to_pattern[future]
                    try:
                        results = future.result()
                        batch_results.extend(results)
                        completed += 1
                        
                        update_markdown(status_text, f"""
📁 **Progress Status:**
Batch {batch_idx}/{len(pattern_batches)}
Completed patterns: {completed}/{len(batch)}
Total results so far: {len(batch_results)}
""")
                            
                    except Exception as e:
                        logger.error(f"Error processing pattern '{pattern}': {str(e)}")
            
            # Release tokens back to the pool
            token_rotator.release_tokens(id(threading.current_thread()))
            
            # Add batch results to all results
            all_results.extend(batch_results)
            
            # Add a cooldown period between batches
            if batch_idx < len(pattern_batches):
                cooldown_msg = f"Batch complete. Cooling down for {cooldown_time} seconds before next batch..."
                logger.info(cooldown_msg)
                update_markdown(status_text, f"""
⏳ **Cooldown:**
{cooldown_msg}
""")
                time.sleep(cooldown_time)  # Using the configurable cooldown time
        
        # Deduplicate results by unique (repository, file path) combination
        deduped = {}
        for item in all_results:
            repo = item.get("repository", {}).get("full_name", "")
            path = item.get("path", "")
            key = (repo, path)
            if key not in deduped:
                deduped[key] = item
                
        final_results = list(deduped.values())
        summary_msg = f"""
Extended parallel search completed:
• Total results found (including duplicates): {len(all_results)}
• Total unique results (after deduplication): {len(final_results)}
• Total patterns processed: {total_chars}
• Total batches: {len(pattern_batches)}
• Parallel workers per batch: {batch_size}
• Average results per pattern: {len(all_results) / total_chars:.2f}
(Duplicates happen when the same file matches in multiple pattern searches)
"""
        logger.info(summary_msg)
        update_markdown(status_text, summary_msg)
        if progress_bar: # Ensure progress bar is at 100% at the end of extended search
            update_progress_bar(progress_bar, 1.0)
        process_ui_updates()  # Process any queued updates
        return final_results
    else:
        return search_github_single(query, limit, progress_bar, status_text)

def search_github_single(query: str, limit: int, progress_bar=None, status_text=None, current_pattern="", token=None):
    base_url = "https://api.github.com/search/code"
    session = requests.Session()  # Use session for connection pooling
    
    token_allocated_internally = False
    pool_id_internal = None
    token_rotator = get_token_rotator() # Get rotator instance

    # Use provided token or get from rotator
    if token is None:
        allocated_tokens = token_rotator.allocate_tokens(1)
        if not allocated_tokens:  # No tokens available
            error_msg = "No tokens available for allocation"
            logger.error(error_msg)
            update_error(status_text, error_msg)
            return []
        token = allocated_tokens[0]
        token_allocated_internally = True
        pool_id_internal = id(threading.current_thread()) # associate with current thread
    
    try:
        # Mask token for logging (without emoji)
        masked_token = f"...{token[-8:]}"
        token_msg = f"Using GitHub token: {masked_token}"
        logger.info(token_msg)
        update_status(status_text, current_pattern, token_msg)
        process_ui_updates()
        
        # Configure session with retry strategy
        session.mount('https://', requests.adapters.HTTPAdapter(
            max_retries=requests.adapters.Retry(
                total=5,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504]
            )
        ))

        # Extract sort parameters from query if present
        sort_param = None
        order_param = "desc"
        if " sort:" in query:
            sort_parts = query.split(" sort:")[1].split(" ")[0].split("-")
            if len(sort_parts) == 2:
                sort_param = sort_parts[0]
                order_param = sort_parts[1]
            query = query.split(" sort:")[0]

        # Determine per_page based on limit
        if isinstance(limit, int) and limit > 0:
            per_page_val = min(100, limit) 
        else: # Handles "all" or other non-positive int cases, defaults to max per_page
            per_page_val = 100

        params = {
            "q": query,
            "per_page": per_page_val
        }
        if sort_param:
            params["sort"] = sort_param
            params["order"] = order_param

        headers = {
            "Accept": "application/vnd.github.v3.text-match+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {token}"
        }

        results = []
        page = 1
        total_fetched = 0
        max_retries = 10
        initial_retry_delay = 2
        current_token = token  # Initialize current_token with the provided or allocated token

        while True:
            params["page"] = page
            retry_count = 0
            retry_delay = initial_retry_delay

            while retry_count < max_retries:
                try:
                    # Only get a new token if we've retried more than once with the current token
                    if retry_count > 0:
                        token_rotator = get_token_rotator()
                        tokens = token_rotator.allocate_tokens(1)
                        if not tokens:  # No tokens available
                            error_msg = "No tokens available for retry"
                            logger.error(error_msg)
                            update_error(status_text, error_msg)
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            retry_count += 1
                            continue
                        current_token = tokens[0]
                        # Mask token for logging (without emoji)
                        masked_token = f"...{current_token[-8:]}"
                        token_msg = f"Switching to new token: {masked_token}"
                        logger.info(token_msg)
                        update_status(status_text, current_pattern, token_msg)
                    
                    headers["Authorization"] = f"Bearer {current_token}"
                    
                    time.sleep(1)  # Basic rate limit protection
                    response = session.get(base_url, headers=headers, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("items", [])
                        results.extend(items)
                        total_fetched += len(items)
                        
                        progress_msg = f"Progress: {total_fetched} results (page {page}, +{len(items)} items)"
                        logger.info(progress_msg)
                        # Keep emoji only in UI updates, not in logs
                        update_status(status_text, current_pattern, token_msg, f"📊 {progress_msg}")
                        if progress_bar and isinstance(limit, int) and limit > 0: # Check if limit is a positive int
                            update_progress_bar(progress_bar, min(total_fetched / limit, 1.0))
                        
                        break
                    elif response.status_code == 403:
                        error_msg = f"Rate limit hit with token {masked_token}, attempt ({retry_count + 1}/{max_retries})"
                        if retry_count > 1:
                            error_msg += " - Will try with next token"
                        logger.warning(error_msg)
                        # Keep emoji only in UI updates
                        update_status(status_text, current_pattern, token_msg, f"⚠️ {error_msg}")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        retry_count += 1
                        continue
                    else:
                        error_msg = f"Error: HTTP {response.status_code} - {response.text}"
                        logger.error(error_msg)
                        # Keep emoji only in UI updates
                        update_error(status_text, f"❌ {error_msg}")
                        break
                except requests.exceptions.JSONDecodeError as jde:
                    logger.error(f"JSON Decode Error: {str(jde)} for query: {query} - Response text: {response.text if 'response' in locals() else 'Response object not available'}", exc_info=True)
                    update_error(status_text, f"❌ Error decoding API response: {str(jde)}")
                    # Decide if this is a retryable offense or break. Usually indicates malformed response.
                    break # Assuming malformed JSON means we can't proceed with this request.
                except requests.exceptions.RequestException as re: # More specific for network/request related issues
                    if retry_count < max_retries:
                        error_msg = f"⚠️ Request Exception, retrying... ({retry_count + 1}/{max_retries}): {str(re)}"
                        logger.error(error_msg, exc_info=True)
                        update_status(status_text, current_pattern, token_msg, error_msg)
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        retry_count += 1
                        continue
                    else:
                        error_msg = f"❌ Request Exception: {str(re)}"
                        logger.error(error_msg, exc_info=True)
                        update_error(status_text, error_msg)
                        break
                except Exception as e: # General catch-all for other unexpected errors
                    if retry_count < max_retries:
                        error_msg = f"⚠️ Unexpected error, retrying... ({retry_count + 1}/{max_retries}): {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        update_status(status_text, current_pattern, token_msg, error_msg)
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        retry_count += 1
                        continue
                    else:
                        error_msg = f"❌ Unexpected error: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        update_error(status_text, error_msg)
                        break

            if retry_count >= max_retries:
                warning_msg = "⚠️ Max retries reached, moving to next page..."
                logger.warning(warning_msg)
                update_status(status_text, current_pattern, token_msg, warning_msg)
                break

            if limit != "all" and total_fetched >= limit:
                results = results[:limit]
                break
            
            if not response.links.get("next"):
                break
            
            page += 1

        final_msg = f"Search completed. Total results: {len(results)}"
        logger.info(final_msg)
        update_status(status_text, current_pattern, token_msg, f"✅ {final_msg}")
        process_ui_updates()
        return results
    finally:
        if token_allocated_internally and pool_id_internal is not None:
            token_rotator.release_tokens(pool_id_internal)
            logger.info(f"Internally allocated token released for pool {pool_id_internal} in search_github_single")
