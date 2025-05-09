import json
import streamlit as st

@st.cache_data
def load_token_patterns():
    """Load token patterns from JSON file."""
    try:
        with open('token_patterns.json', 'r') as f:
            patterns = json.load(f)
        # Add "Custom Pattern" option
        patterns["Custom Pattern"] = "custom"
        return patterns
    except FileNotFoundError:
        return {"Custom Pattern": "custom"}
    except json.JSONDecodeError:
        return {"Custom Pattern": "custom"} 