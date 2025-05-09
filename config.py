import os
from dotenv import load_dotenv
from itertools import cycle
import time
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
import threading

# Load environment variables
load_dotenv()

class TokenRotator:
    _instance = None
    _tokens = None
    _token_pools = {}
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TokenRotator, cls).__new__(cls)
            tokens = cls._instance._get_github_tokens()
            if tokens:
                cls._tokens = tokens
            else:
                raise ValueError("No GitHub tokens found in environment variables")
        return cls._instance
    
    def _get_github_tokens(self):
        """Get GitHub tokens from environment variables."""
        tokens_env = os.getenv("GITHUB_TOKENS")
        if tokens_env:
            tokens = [token.strip() for token in tokens_env.split(",") if token.strip()]
            if tokens:
                return tokens
        token = os.getenv("GITHUB_TOKEN")
        if token:
            return [token.strip()]
        return None
    
    def allocate_tokens(self, pool_size: int, reserve_count: int = 7) -> List[str]:
        """
        Allocate a pool of tokens for parallel processing.
        
        Args:
            pool_size (int): Number of tokens needed for the pool
            reserve_count (int): Number of tokens to keep in reserve for error handling
            
        Returns:
            List[str]: List of allocated tokens
        """
        with self._lock:
            available_tokens = [t for t in self._tokens if t not in sum(self._token_pools.values(), [])]
            if len(available_tokens) < pool_size + reserve_count:
                logging.warning(f"Not enough tokens available. Requested: {pool_size}, Available: {len(available_tokens)}")
                pool_size = max(1, len(available_tokens) - reserve_count)
            
            allocated_tokens = available_tokens[:pool_size]
            pool_id = id(threading.current_thread())
            self._token_pools[pool_id] = allocated_tokens
            
            logging.info(f"Allocated {len(allocated_tokens)} tokens to pool {pool_id}")
            return allocated_tokens
    
    def release_tokens(self, pool_id: int):
        """Release tokens back to the available pool."""
        with self._lock:
            if pool_id in self._token_pools:
                released_count = len(self._token_pools[pool_id])
                del self._token_pools[pool_id]
                logging.info(f"Released {released_count} tokens from pool {pool_id}")
    
    def get_available_token_count(self) -> int:
        """Get the count of available tokens not currently allocated to any pool."""
        with self._lock:
            used_tokens = sum(self._token_pools.values(), [])
            return len(self._tokens) - len(used_tokens)
    
    def get_total_token_count(self) -> int:
        """Get the total number of tokens."""
        return len(self._tokens) if self._tokens else 0

def get_token_rotator():
    """Get the token rotator singleton instance."""
    return TokenRotator()

def get_github_tokens():
    """Get GitHub tokens from environment variables (legacy function for compatibility)."""
    rotator = get_token_rotator()
    if rotator._tokens:
        return rotator._tokens
    return None 