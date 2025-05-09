#!/usr/bin/env python3
"""
GitHub PAT Scraper - Streamlit Application

A web interface for the GitHub PAT Scraper that allows:
- Custom regex patterns for searching
- Configurable result limits
- Real-time progress tracking
- Download of results in JSON format
- Extended search by splitting query by filename prefix
"""

import streamlit as st
import threading
import time
import logging
import re # Added for regex compilation

from config import get_github_tokens
from token_patterns import load_token_patterns
from github_api import search_github
from result_processor import process_results, save_results
from search_query import generate_search_query
from thread_safe_api import thread_safe_state, thread_safe_search_github

logger = logging.getLogger(__name__) # Initialize logger for app.py

def main():
    st.set_page_config(
        page_title="GitSentry",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 GitSentry")
    st.markdown("Search for tokens and secrets in GitHub public code.")
    
    # Initialize search_running in session state if not present for disabling widgets
    if 'search_running' not in st.session_state:
        st.session_state.search_running = False
    if 'progress_bar' not in st.session_state:
        st.session_state.progress_bar = None
    if 'status_container' not in st.session_state:
        st.session_state.status_container = None
    if 'search_error' not in st.session_state: # Added for storing search errors
        st.session_state.search_error = None
    if 'pattern' not in st.session_state:
        st.session_state.pattern = ""
    if 'pattern_valid' not in st.session_state: # To track regex validity
        st.session_state.pattern_valid = True
    if 'start_search_requested' not in st.session_state: # New flag
        st.session_state.start_search_requested = False

    # Sidebar configuration
    st.sidebar.header("⚙️ Configuration") # Added icon
    search_active = st.session_state.search_running # Convenience variable

    # Load token patterns
    TOKEN_PATTERNS = load_token_patterns()
    
    # Add empty custom token type
    TOKEN_PATTERNS["Custom (Empty)"] = ""
    
    # Search box for token patterns
    pattern_search = st.sidebar.text_input(
        "Search Token Patterns",
        value="",
        help="Type to search and filter token patterns",
        disabled=search_active
    )
    
    # Filter patterns based on search
    filtered_patterns = {
        k: v for k, v in TOKEN_PATTERNS.items()
        if pattern_search.lower() in k.lower()
    }
    
    if not filtered_patterns:
        st.sidebar.warning("No patterns match your search.")
        filtered_patterns = {"Custom (Empty)": ""}
    
    # Token pattern selection
    if 'pattern_type' not in st.session_state:
        st.session_state.pattern_type = list(filtered_patterns.keys())[list(filtered_patterns.keys()).index("Custom (Empty)")] if "Custom (Empty)" in filtered_patterns else list(filtered_patterns.keys())[0]

    st.session_state.pattern_type = st.sidebar.selectbox(
        "Token Type",
        options=list(filtered_patterns.keys()),
        index=list(filtered_patterns.keys()).index(st.session_state.pattern_type) if st.session_state.pattern_type in filtered_patterns else (list(filtered_patterns.keys()).index("Custom (Empty)") if "Custom (Empty)" in filtered_patterns else 0),
        help="Select the type of token to search for",
        disabled=search_active
    )
    
    # Pattern input/editing
    if 'pattern' not in st.session_state:
        st.session_state.pattern = ""

    if st.session_state.pattern_type == "Custom (Empty)":
        new_custom_pattern = st.sidebar.text_input(
            "Custom Regex Pattern",
            value=st.session_state.get("pattern", ""),
            help="Enter your custom regular expression pattern",
            disabled=search_active
        )
        if new_custom_pattern != st.session_state.get("pattern", ""):
            st.session_state.pattern = new_custom_pattern
            try:
                re.compile(st.session_state.pattern)
                st.session_state.pattern_valid = True
            except re.error as e:
                st.session_state.pattern_valid = False
                st.sidebar.error(f"Invalid Regex: {e}")
            st.rerun() # Rerun to reflect validity or error
        elif not st.session_state.pattern_valid and st.session_state.pattern: # Show error if already invalid
             st.sidebar.error("Invalid Regex: Please correct the pattern.")

    else:
        # When a predefined pattern is selected, it's assumed valid
        if TOKEN_PATTERNS.get(st.session_state.pattern_type) != st.session_state.pattern or not st.session_state.pattern:
             st.session_state.pattern = TOKEN_PATTERNS[st.session_state.pattern_type]
             st.session_state.pattern_valid = True # Predefined patterns are valid
             # No rerun needed here as selectbox change causes it if value changes

        st.session_state.pattern = st.sidebar.text_area(
            "Edit Pattern",
            value=st.session_state.pattern,
            help="Edit the regex pattern that will be used for searching",
            disabled=search_active
        )
        # If user edits a predefined pattern, it becomes custom-like, check validity on change
        # This part is tricky as text_area doesn't have an on_change for immediate feedback like text_input
        # For now, validation primarily happens for the "Custom (Empty)" type upon input change.
        # And the Start Scraping button will be the final check point for other edited patterns.

    st.sidebar.divider() # Added divider

    # Optional search query
    use_custom_query = st.sidebar.checkbox(
        "Use Custom Search Query",
        value=True,
        help="By default, we'll automatically generate a search query from the pattern type and regex. Enable this to use a custom query.",
        disabled=search_active
    )
    
    if use_custom_query:
        search_query = st.sidebar.text_input(
            "Search Query",
            value="",
            help="Custom search query (optional)",
            disabled=search_active
        )
    else:
        search_query = generate_search_query(st.session_state.pattern, st.session_state.pattern_type)
        if search_query:
            st.sidebar.text_area(
                "Generated Search Query",
                value=search_query,
                disabled=True,
                help="Query automatically generated from the pattern type and regex"
            )
        else:
            search_query = ""
            st.sidebar.info(f"Using default search query: '{search_query}'")
    
    limit = st.sidebar.number_input(
        "Result Limit",
        min_value=1,
        max_value=999,
        value=400,
        help="Maximum number of results to fetch",
        disabled=search_active
    )
    
    # Extended search by splitting by filename prefix
    enable_extended = st.sidebar.checkbox(
        "Enable Extended Search (split by filename prefix)",
        value=False,
        help="Split the search query by appending filename qualifiers (a-z, 0-9) to bypass the 1,000 result limit. (This only applies to code search.)",
        disabled=search_active
    )
    
    # Add custom cooldown time configuration
    if enable_extended:
        st.sidebar.markdown("---")
        custom_cooldown = st.sidebar.checkbox(
            "Use Custom Cooldown Time",
            value=False,
            help="Customize the cooldown time between batches in extended search (default is 40 seconds)",
            disabled=search_active
        )
        
        cooldown_time = 40  # Default value
        if custom_cooldown:
            cooldown_time = st.sidebar.number_input(
                "Cooldown Time (seconds)",
                min_value=5,
                max_value=120, 
                value=40,
                step=5,
                help="Time to wait between batches to avoid rate limiting (seconds)",
                disabled=search_active
            )
            
            st.sidebar.info(
                "ℹ️ Lower values may cause more rate limit errors. Higher values make the search slower but more reliable."
            )
    else:
        cooldown_time = 40  # Default if extended search is not enabled
        custom_cooldown = False

    # Main content
    if 'search_thread' not in st.session_state:
        st.session_state.search_thread = None
    if 'should_update_ui' not in st.session_state:
        st.session_state.should_update_ui = False

    # When search completes or has an error, Streamlit will rerun the app and
    # this will be set to show the appropriate screen
    if thread_safe_state.get_results() is not None and not thread_safe_state.is_search_running():
        st.session_state.should_update_ui = True
    
    # Show welcome message if no search is in progress and no results to show
    if not thread_safe_state.is_search_running() and thread_safe_state.get_results() is None and thread_safe_state.get_error() is None:
        st.info("ℹ️ Configure your search parameters in the sidebar and click 'Start Scraping' to begin.")
    
    # Create container for progress and status updates
    status_container = st.empty()
    progress_bar = st.progress(0)
    
    # Button is only active if no search is running
    if st.button("Start Scraping", type="primary", disabled=thread_safe_state.is_search_running()):
        # Final validation check before starting
        try:
            re.compile(st.session_state.pattern)
            st.session_state.pattern_valid = True
        except re.error as e:
            st.session_state.pattern_valid = False
            st.error(f"Invalid Regex Pattern: {e}")
        
        if not st.session_state.pattern:
            st.error("Please enter a valid regex pattern")
        elif not st.session_state.pattern_valid:
            st.error("Please fix the invalid regex pattern in the sidebar.")
        elif not get_github_tokens():
            st.error("⚠️ No GitHub token found in environment variables. Please set GITHUB_TOKEN or GITHUB_TOKENS.")
        else:
            # Reset thread safe state
            thread_safe_state.reset()
            thread_safe_state.set_running(True)
            
            # Show search configuration
            st.info("🚀 Starting the scraping process...")
            st.markdown(f"""
            **Search Configuration:**
            - Pattern Type: `{st.session_state.pattern_type}`
            - Regex Pattern: `{st.session_state.pattern}`
            - Search Query: `{search_query}`
            - Result Limit: `{limit}`
            - Extended Search: {"Enabled" if enable_extended else "Disabled"}
            """)
            
            # Capture current values for the thread
            current_search_query = search_query
            current_limit = limit
            current_enable_extended = enable_extended
            
            # Function to be run in the thread - no Streamlit API access
            def thread_target():
                try:
                    # Use thread-safe search function that doesn't require Streamlit UI elements
                    thread_safe_search_github(
                        query=current_search_query,
                        limit=current_limit,
                        extended=current_enable_extended,
                        cooldown=cooldown_time
                    )
                except Exception as e:
                    logger.error(f"Error in search thread: {str(e)}", exc_info=True)
                    thread_safe_state.set_error(f"An unexpected error occurred: {str(e)}")
                finally:
                    thread_safe_state.set_running(False)

            # Start thread
            st.session_state.search_thread = threading.Thread(target=thread_target)
            st.session_state.search_thread.start()
            
            # Force a rerun to enter the search monitoring state
            st.rerun()

    # Search monitoring state - display progress and status updates
    if thread_safe_state.is_search_running():
        # Display a spinner while search is running
        with st.spinner("Search in progress"):
            # Update UI with current progress and status
            progress_bar.progress(thread_safe_state.get_progress())
            
            # Create simplified status display
            status_container.empty()
            with status_container.container():
                # Show basic search info
                st.markdown(f"### 🔍 GitHub Token Search in Progress")
                
                # Create a simple status card
                st.markdown("""
                <style>
                .status-card {
                    background-color: #f0f2f6;
                    border-radius: 10px;
                    padding: 15px;
                    margin-bottom: 15px;
                }
                .cooling-card {
                    background-color: #e6f3ff;
                    border-radius: 10px;
                    padding: 15px;
                    margin-bottom: 15px;
                    border-left: 4px solid #2196F3;
                }
                </style>
                """, unsafe_allow_html=True)
                
                # Get current status message for details
                status_msg = thread_safe_state.get_status()
                
                # Check for cooling down phase
                is_cooling_down = "Cooling down" in status_msg
                cooldown_time = 40  # Default value
                
                # Try to extract cooldown time from status message
                if is_cooling_down:
                    try:
                        # Look for patterns like "Cooling down for X seconds" or similar
                        cooldown_parts = status_msg.split("Cooling down")
                        if len(cooldown_parts) > 1:
                            for part in cooldown_parts[1:]:
                                if "seconds" in part:
                                    # Extract number before "seconds"
                                    numbers = [int(s) for s in part.split() if s.isdigit()]
                                    if numbers:
                                        cooldown_time = numbers[0]
                                        break
                    except:
                        # If extraction fails, use default value
                        pass
                
                # Display appropriate card based on state
                if is_cooling_down:
                    st.markdown(f"""
                    <div class="cooling-card">
                    <h4>⏱️ Cooling Down Between Batches</h4>
                    <p>The search is paused for a cooling down period of <strong>{cooldown_time} seconds</strong> to avoid GitHub API rate limits.</p>
                    <p>This is normal during extended searches. The search will automatically continue after the cooldown period.</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Display pattern being searched
                st.markdown(f"""
                <div class="status-card">
                <h4>📊 Search Information</h4>
                <p>Searching for tokens matching pattern: <code>{st.session_state.pattern_type}</code></p>
                <p>Please wait while GitHub is being searched. This may take several minutes.</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Show raw status message for debugging
                with st.expander("Status Details", expanded=False):
                    st.code(status_msg)
            
            # Keep checking the search state until it's done
            while thread_safe_state.is_search_running() and st.session_state.search_thread and st.session_state.search_thread.is_alive():
                # Get updated progress
                current_progress = thread_safe_state.get_progress()
                progress_bar.progress(current_progress)
                
                # Update status container with new info
                with status_container.container():
                    # Show basic search info
                    st.markdown(f"### 🔍 GitHub Token Search in Progress")
                    
                    # Create a simple status card
                    st.markdown("""
                    <style>
                    .status-card {
                        background-color: #f0f2f6;
                        border-radius: 10px;
                        padding: 15px;
                        margin-bottom: 15px;
                    }
                    .cooling-card {
                        background-color: #e6f3ff;
                        border-radius: 10px;
                        padding: 15px;
                        margin-bottom: 15px;
                        border-left: 4px solid #2196F3;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    # Get current status message for details
                    status_msg = thread_safe_state.get_status()
                    
                    # Check for cooling down phase
                    is_cooling_down = "Cooling down" in status_msg
                    cooldown_time = 40  # Default value
                    
                    # Try to extract cooldown time from status message
                    if is_cooling_down:
                        try:
                            # Look for patterns like "Cooling down for X seconds" or similar
                            cooldown_parts = status_msg.split("Cooling down")
                            if len(cooldown_parts) > 1:
                                for part in cooldown_parts[1:]:
                                    if "seconds" in part:
                                        # Extract number before "seconds"
                                        numbers = [int(s) for s in part.split() if s.isdigit()]
                                        if numbers:
                                            cooldown_time = numbers[0]
                                            break
                        except:
                            # If extraction fails, use default value
                            pass
                    
                    # Display appropriate card based on state
                    if is_cooling_down:
                        st.markdown(f"""
                        <div class="cooling-card">
                        <h4>⏱️ Cooling Down Between Batches</h4>
                        <p>The search is paused for a cooling down period of <strong>{cooldown_time} seconds</strong> to avoid GitHub API rate limits.</p>
                        <p>This is normal during extended searches. The search will automatically continue after the cooldown period.</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Display pattern being searched
                    st.markdown(f"""
                    <div class="status-card">
                    <h4>📊 Search Information</h4>
                    <p>Searching for tokens matching pattern: <code>{st.session_state.pattern_type}</code></p>
                    <p>Please wait while GitHub is being searched. This may take several minutes.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Show raw status message for debugging
                    with st.expander("Status Details", expanded=False):
                        st.code(status_msg)
                
                # Sleep for better performance
                time.sleep(0.5)
            
            # Final update after search completes
            progress_bar.progress(1.0)  # Force to 100% when complete
            
            with status_container.container():
                st.success("✅ Search completed successfully!")
                
                # Display simple completion message
                st.info("Results are being processed and will be displayed shortly...")
                
                time.sleep(1)  # Brief pause to show completion status
            
        # Rerun to show results or error
        st.rerun()
    
    # Error state - display error message
    if thread_safe_state.get_error():
        status_container.empty()
        progress_bar.empty()
        st.error(f"Search failed: {thread_safe_state.get_error()}")
        # Clear error after displaying
        thread_safe_state.set_error(None)

    # Results state - display search results
    if thread_safe_state.get_results() is not None and st.session_state.should_update_ui:
        # Clear the progress and status indicators
        status_container.empty()
        progress_bar.empty()
        
        # Get results from thread-safe state
        results = thread_safe_state.get_results()
        
        # Process results with the pattern from session state
        current_pattern = st.session_state.pattern
        processed_results = process_results(results, current_pattern)
        
        if processed_results:
            tokens_file, detailed_file, save_error = save_results(processed_results, current_pattern)
            
            if save_error:
                st.error(f"Failed to save results: {save_error}")
            else:
                st.success(f"✅ Found {len(processed_results)} results with matching patterns!")
                
                # Display summary
                st.header("Summary")
                total_tokens = sum(len(r["found_tokens"]) for r in processed_results)
                st.markdown(f"""
                - Total repositories scanned: {len(processed_results)}
                - Total unique tokens found: {total_tokens}
                - Results saved to:
                    - Tokens file: `{tokens_file}`
                    - Detailed results: `{detailed_file}`
                """)
                
                # Allow downloading results
                col1, col2 = st.columns(2)
                with col1:
                    with open(tokens_file, 'rb') as f:
                        st.download_button(
                            label="Download Tokens JSON",
                            data=f,
                            file_name=tokens_file,
                            mime="application/json"
                        )
                
                with col2:
                    with open(detailed_file, 'rb') as f:
                        st.download_button(
                            label="Download Detailed Results",
                            data=f,
                            file_name=detailed_file,
                            mime="application/json"
                        )
                
                # Display results preview
                st.header("Results Preview")
                for idx, result in enumerate(processed_results[:5], 1):
                    with st.expander(f"Result #{idx} - {result.get('repository', 'N/A')}", expanded=idx==1):
                        st.markdown(f"""
                        - Repository: {result.get('repository', 'N/A')}
                        - File: {result.get('path', 'N/A')}
                        - URL: {result.get('html_url', 'N/A')}
                        - Last Updated: {result.get('last_modified', 'N/A')}
                        - Found Tokens: {len(result.get('found_tokens', []))}
                        """)
                        st.markdown("**Tokens Found in Context:**")
                        for fragment in result.get('fragments', []):
                            st.code(fragment, language="text")
                
                if len(processed_results) > 5:
                    st.info(f"... and {len(processed_results) - 5} more results")
        else:
            st.warning("No matching tokens found in the search results.")
        
        # Reset session state for next run
        st.session_state.should_update_ui = False
        # Do not clear results from thread_safe_state here to allow viewing results again
        # thread_safe_state.results = None

    # Display error if any occurred during search (should display once then clear)
    if st.session_state.search_error and not thread_safe_state.is_search_running():
        st.error(st.session_state.search_error)
        st.session_state.search_error = None # Clear error after displaying

if __name__ == "__main__":
    main()
