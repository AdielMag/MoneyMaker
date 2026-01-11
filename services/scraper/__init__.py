"""
Market Scraper Service

Scrapes and filters Polymarket markets based on configurable criteria.
"""

from services.scraper.filters import FilterResult, MarketFilter
from services.scraper.service import ScraperService

__all__ = ["MarketFilter", "FilterResult", "ScraperService"]
