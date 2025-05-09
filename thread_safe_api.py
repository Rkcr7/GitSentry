"""
Thread-safe API for GitHub search operations.

This module provides a bridge between worker threads and the Streamlit app,
allowing threads to update progress and status without directly accessing
Streamlit elements or session state.
"""

import threading
from queue import Queue
import logging
from typing import Dict, Any, Optional, List
import json
import time

# Configure logging
logger = logging.getLogger(__name__)

# Global state accessible from any thread
class ThreadSafeState:
    def __init__(self):
        self.lock = threading.RLock()
        self.progress_value = 0.0
        self.status_message = ""
        self.is_running = False
        self.error = None
        self.results = None
        # Store completion stats to display after search completes
        self.completed_stats = None
        # Queue for updates to be processed by the main thread
        self.update_queue = Queue()
        # Additional fields for more detailed stats
        self.search_stats = {
            "total_fetched": 0,
            "current_page": 0,
            "items_per_page": 0,
            "start_time": None,
            "elapsed_time": 0,
            "current_batch": 0,
            "total_batches": 0,
            "current_pattern": "",
            "token_info": "",
            "completed_patterns": 0,
            "total_patterns": 0,
            "rate_limit_hits": 0,
            "requests_made": 0,
            "is_extended_search": False,
            "search_query": "",
            "result_limit": 0,
            "cooldown_time": 40,
            "search_phase": "initializing",
            "active_tokens": 0,
            "last_update_time": None
        }
        
    def start_search(self, query: str, limit: int, extended: bool) -> None:
        """Record search start time and parameters"""
        with self.lock:
            self.reset()  # Make sure we start with a clean state
            self.search_stats["start_time"] = time.time()
            self.search_stats["search_query"] = query
            self.search_stats["result_limit"] = limit
            self.search_stats["is_extended_search"] = extended
            self.search_stats["search_phase"] = "initializing"
            self.is_running = True
            self.update_queue.put(("search_started", self.search_stats))
        
    def update_elapsed_time(self) -> None:
        """Update elapsed time since search started"""
        with self.lock:
            if self.search_stats["start_time"]:
                self.search_stats["elapsed_time"] = time.time() - self.search_stats["start_time"]
                
    def set_progress(self, value: float) -> None:
        """Set progress value (0.0-1.0)"""
        with self.lock:
            self.progress_value = min(max(0.0, value), 1.0)
            # Update elapsed time whenever progress is updated
            self.update_elapsed_time()
            self.update_queue.put(("progress", self.progress_value))
            
    def set_status(self, message: str) -> None:
        """Set status message and try to parse structured information from it"""
        with self.lock:
            self.status_message = message
            self.search_stats["last_update_time"] = time.time()
            
            # Update elapsed time
            self.update_elapsed_time()
            
            # Log the message for debugging
            logger.debug(f"Status message: {message}")
            
            # Track the search phase based on message content
            if "Starting extended parallel search" in message:
                self.search_stats["search_phase"] = "starting_extended"
                self.search_stats["is_extended_search"] = True
            elif "Starting the scraping process" in message:
                self.search_stats["search_phase"] = "starting"
            elif "Progress:" in message:
                self.search_stats["search_phase"] = "fetching_results"
            elif "Batch" in message and "Processing batch" in message:
                self.search_stats["search_phase"] = "batch_processing"
            elif "Cooling down" in message:
                self.search_stats["search_phase"] = "cooling_down"
            elif "Search completed" in message or "search completed" in message.lower():
                self.search_stats["search_phase"] = "completed"
            
            # Try to extract structured information from the status message
            if "Progress:" in message:
                try:
                    progress_part = message.split("Progress:")[1].strip()
                    total_results_text = progress_part.split("results")[0].strip()
                    self.search_stats["total_fetched"] = int(total_results_text)
                    
                    if "(page" in progress_part:
                        page_info = progress_part.split("(page")[1].split(",")[0].strip()
                        self.search_stats["current_page"] = int(page_info)
                    
                    if "+" in progress_part and "items" in progress_part:
                        items_info = progress_part.split("+")[1].split("items")[0].strip()
                        self.search_stats["items_per_page"] = int(items_info)
                    
                    self.search_stats["requests_made"] += 1
                    logger.info(f"Parsed progress: {self.search_stats['total_fetched']} results, page {self.search_stats['current_page']}")
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing Progress information: {str(e)}")

            # Extract batch information for extended search
            if "Batch" in message:
                try:
                    batch_lines = [line for line in message.split("\n") if "Batch" in line and "/" in line]
                    if batch_lines:
                        batch_line = batch_lines[0]
                        if "Processing batch" in batch_line:
                            batch_parts = batch_line.split("batch")[1].split("/")
                        else:
                            batch_parts = batch_line.split("Batch")[1].split("/")
                        
                        if len(batch_parts) >= 2:
                            current_batch = batch_parts[0].strip()
                            if current_batch.isdigit():
                                self.search_stats["current_batch"] = int(current_batch)
                            
                            total_part = batch_parts[1].split()[0].strip()
                            if total_part.isdigit():
                                self.search_stats["total_batches"] = int(total_part)
                                
                            logger.info(f"Parsed batch info: {self.search_stats['current_batch']}/{self.search_stats['total_batches']}")
                except (ValueError, IndexError, KeyError) as e:
                    logger.error(f"Error parsing Batch information: {str(e)}")
            
            # Extract pattern information
            if "Pattern" in message:
                try:
                    pattern_parts = message.split("Pattern")
                    if len(pattern_parts) > 1:
                        pattern_info = pattern_parts[1].split("in batch")[0].strip() if "in batch" in pattern_parts[1] else pattern_parts[1].strip()
                        self.search_stats["current_pattern"] = pattern_info
                        logger.info(f"Parsed pattern: {pattern_info}")
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing Pattern information: {str(e)}")
            
            # Extract number of tokens being used
            if "allocate" in message and "tokens" in message:
                try:
                    if "Allocated" in message:
                        tokens_part = message.split("Allocated")[1].strip()
                        token_count_text = tokens_part.split("tokens")[0].strip()
                        if token_count_text.isdigit():
                            self.search_stats["active_tokens"] = int(token_count_text)
                            logger.info(f"Parsed token count: {self.search_stats['active_tokens']}")
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing token allocation information: {str(e)}")
            
            # Extract completed patterns information
            if "Completed patterns:" in message:
                try:
                    completed_part = message.split("Completed patterns:")[1].strip()
                    completed_info = completed_part.split("\n")[0].strip()
                    if "/" in completed_info:
                        completed_parts = completed_info.split("/")
                        if len(completed_parts) >= 2:
                            completed_count = completed_parts[0].strip()
                            if completed_count.isdigit():
                                self.search_stats["completed_patterns"] = int(completed_count)
                            
                            total_count = completed_parts[1].strip()
                            if total_count.isdigit():
                                self.search_stats["total_patterns"] = int(total_count)
                            
                            logger.info(f"Parsed completed patterns: {self.search_stats['completed_patterns']}/{self.search_stats['total_patterns']}")
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing completed patterns information: {str(e)}")
            
            # Extract token information
            if "Using GitHub token:" in message:
                try:
                    token_info = message.split("Using GitHub token:")[1].strip()
                    self.search_stats["token_info"] = token_info
                    logger.info(f"Parsed token info: {token_info}")
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing token information: {str(e)}")
            
            # Count rate limit hits
            if "Rate limit hit" in message:
                self.search_stats["rate_limit_hits"] += 1
                logger.info(f"Rate limit hit count: {self.search_stats['rate_limit_hits']}")
            
            # Put both the raw message and structured stats into the queue
            self.update_queue.put(("status", {
                "message": self.status_message,
                "stats": self.search_stats.copy()  # Send a copy to avoid mutation
            }))
    
    def set_error(self, error_message: str) -> None:
        """Set error message"""
        with self.lock:
            self.error = error_message
            self.update_queue.put(("error", self.error))
    
    def set_results(self, results: List[Dict[str, Any]]) -> None:
        """Set search results"""
        with self.lock:
            self.results = results
            self.search_stats["total_results"] = len(results) if results else 0
            self.update_queue.put(("results", {
                "count": len(results) if results else 0,
                "stats": self.search_stats.copy()  # Send a copy to avoid mutation
            }))
    
    def set_running(self, is_running: bool) -> None:
        """Set running state"""
        with self.lock:
            previous_state = self.is_running
            self.is_running = is_running
            
            if not is_running and self.search_stats["start_time"]:
                # Calculate final elapsed time when search completes
                self.update_elapsed_time()
                
                # Store the final stats when search completes
                if previous_state:  # Only store if transitioning from running to not running
                    self.completed_stats = self.search_stats.copy()
                    logger.info("Search completed, stored final stats")
                    
            self.update_queue.put(("running", {
                "is_running": self.is_running,
                "stats": self.search_stats.copy()  # Send a copy to avoid mutation
            }))
    
    def get_progress(self) -> float:
        """Get current progress value"""
        with self.lock:
            return self.progress_value
    
    def get_status(self) -> str:
        """Get current status message"""
        with self.lock:
            return self.status_message
    
    def get_error(self) -> Optional[str]:
        """Get error message if any"""
        with self.lock:
            return self.error
    
    def get_results(self) -> Optional[List[Dict[str, Any]]]:
        """Get search results if available"""
        with self.lock:
            return self.results
    
    def is_search_running(self) -> bool:
        """Check if search is running"""
        with self.lock:
            return self.is_running
    
    def get_completed_stats(self) -> Dict[str, Any]:
        """Get stats from the completed search or current stats if search is running"""
        with self.lock:
            if self.is_running:
                return self.search_stats.copy()
            elif self.completed_stats:
                return self.completed_stats.copy()
            else:
                return self.search_stats.copy()
    
    def has_updates(self) -> bool:
        """Check if there are any pending updates"""
        return not self.update_queue.empty()
    
    def get_next_update(self) -> Optional[tuple]:
        """Get next update from the queue"""
        try:
            return self.update_queue.get_nowait()
        except:
            return None
    
    def reset(self) -> None:
        """Reset all state"""
        with self.lock:
            self.progress_value = 0.0
            self.status_message = ""
            self.is_running = False
            self.error = None
            # Don't clear results or completed_stats until explicitly requested
            # self.results = None
            # self.completed_stats = None
            
            # Reset search stats
            self.search_stats = {
                "total_fetched": 0,
                "current_page": 0,
                "items_per_page": 0,
                "start_time": None,
                "elapsed_time": 0,
                "current_batch": 0,
                "total_batches": 0,
                "current_pattern": "",
                "token_info": "",
                "completed_patterns": 0,
                "total_patterns": 0,
                "rate_limit_hits": 0,
                "requests_made": 0,
                "is_extended_search": False,
                "search_query": "",
                "result_limit": 0,
                "cooldown_time": 40,
                "search_phase": "initializing",
                "active_tokens": 0,
                "last_update_time": None
            }
            
            # Clear queue
            while not self.update_queue.empty():
                try:
                    self.update_queue.get_nowait()
                except:
                    break

# Singleton instance
thread_safe_state = ThreadSafeState()

# Function to wrap GitHub search_github to work with thread-safe state
def thread_safe_search_github(
    query: str,
    limit: int,
    extended: bool = False,
    cooldown: int = 40,
    state: ThreadSafeState = thread_safe_state
) -> List[Dict[str, Any]]:
    """
    Thread-safe wrapper for GitHub search_github function.
    
    Instead of taking Streamlit elements for progress and status, it updates
    the thread-safe state which can then be safely checked from the main thread.
    
    Args:
        query: The search query to submit to GitHub
        limit: Maximum number of results to fetch
        extended: Whether to use extended search (multiple queries)
        cooldown: Time in seconds to wait between batches in extended search
        state: The thread-safe state to update
    """
    # Import here to avoid circular imports
    from github_api import search_github as _search_github
    
    # Initialize search in the thread-safe state
    state.start_search(query, limit, extended)
    state.search_stats["cooldown_time"] = cooldown
    state.search_stats["search_phase"] = "starting"
    
    # Create proxy objects for progress_bar and status_text
    class ProgressProxy:
        def progress(self, value):
            state.set_progress(value)
    
    class StatusProxy:
        def markdown(self, text):
            state.set_status(text)
        def empty(self):
            state.set_status("")
        def error(self, text):
            state.set_error(text)
    
    progress_proxy = ProgressProxy()
    status_proxy = StatusProxy()
    
    try:
        # Call the original search_github with our proxies
        results = _search_github(
            query=query,
            limit=limit,
            progress_bar=progress_proxy,
            status_text=status_proxy,
            extended=extended,
            cooldown_time=cooldown
        )
        state.set_results(results)
        return results
    except Exception as e:
        logger.error(f"Error in thread_safe_search_github: {str(e)}", exc_info=True)
        state.set_error(f"Search error: {str(e)}")
        return [] 