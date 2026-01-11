"""
Market Scraper Service

Scrapes and filters Polymarket markets based on configurable criteria.
"""

from services.scraper.filters import MarketFilter, FilterResult
from services.scraper.service import ScraperService

__all__ = ["MarketFilter", "FilterResult", "ScraperService"]
