"""
Fixed Content Router - Import from Module
Imports the router from the fixed_content module for main app inclusion
"""

# Import the router from the fixed content module
from ..fixed_content.router import router

# Re-export for main app
__all__ = ["router"]
