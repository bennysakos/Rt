import asyncio
import aiohttp
import re
import time
from bs4 import BeautifulSoup
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class RTanksScraper:
    def __init__(self):
        self.base_url = "https://ratings.ranked-rtanks.online"
        self.session = None
        self.cache = {}
        self.cache_timeout = 300  # 5 minutes cache
        
        # Headers to mimic a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.headers
            )
        return self.session
    
    async def close_session(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self.cache:
            return False
        
        cached_time = self.cache[cache_key].get('timestamp', 0)
        return time.time() - cached_time < self.cache_timeout
    
    def get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if valid"""
        if self.is_cache_valid(cache_key):
            return self.cache[cache_key]['data']
        return None
    
    def set_cache(self, cache_key: str, data: Any):
        """Set data in cache"""
        self.cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a web page with error handling"""
        try:
            session = await self.get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    return content
                else:
                    logger.warning(f"HTTP {response.status} for URL: {url}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching URL: {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None
    
    def parse_player_profile(self, html: str, nickname: str) -> Optional[Dict]:
        """Parse player profile HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Check if player exists
            if "профиль игрока" not in html.lower() and nickname.lower() not in html.lower():
                return None
            
            player_data = {
                'nickname': nickname,
                'rank': None,
                'experience': None,
                'kills': None,
                'deaths': None,
                'kd_ratio': None,
                'gold_boxes': None,
                'premium': None,
                'group': None,
                'rankings': {},
                'equipment': {
                    'turrets': [],
                    'hulls': [],
                    'paints': [],
                    'modules': []
                }
            }
            
            # Extract rank and experience
            rank_section = soup.find('div', string=re.compile(r'.*-офицер.*|.*Генерал.*|.*Капитан.*'))
            if rank_section:
                rank_text = rank_section.get_text(strip=True)
                player_data['rank'] = rank_text
            
            # Extract experience from progress bar or text
            exp_elements = soup.find_all(text=re.compile(r'\d+\s*/\s*\d+|\d+\s+/\s+\d+'))
            for exp_text in exp_elements:
                if '/' in exp_text:
                    current_exp = exp_text.split('/')[0].strip().replace(' ', '')
                    if current_exp.isdigit():
                        player_data['experience'] = int(current_exp)
                        break
            
            # Extract statistics from tables
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        
                        if 'Уничтожил' in key or 'Убийств' in key:
                            if value.isdigit():
                                player_data['kills'] = int(value)
                        elif 'Подбит' in key or 'Смертей' in key:
                            if value.isdigit():
                                player_data['deaths'] = int(value)
                        elif 'У/П' in key or 'K/D' in key:
                            try:
                                player_data['kd_ratio'] = float(value)
                            except ValueError:
                                pass
                        elif 'золотых ящиков' in key:
                            if value.isdigit():
                                player_data['gold_boxes'] = int(value)
                        elif 'Премиум' in key:
                            player_data['premium'] = 'Да' in value
                        elif 'Группа' in key:
                            player_data['group'] = value
            
            # Extract rankings
            ranking_section = soup.find('table')
            if ranking_section:
                rows = ranking_section.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        category = cells[0].get_text(strip=True)
                        rank = cells[1].get_text(strip=True)
                        value = cells[2].get_text(strip=True)
                        
                        if category and rank and value:
                            player_data['rankings'][category] = {
                                'rank': rank,
                                'value': value
                            }
            
            # Extract equipment information
            equipment_sections = soup.find_all('div', class_=re.compile(r'.*equipment.*|.*gear.*'))
            for section in equipment_sections:
                imgs = section.find_all('img')
                for img in imgs:
                    alt_text = img.get('alt', '')
                    src = img.get('src', '')
                    
                    if 'turrets' in src:
                        player_data['equipment']['turrets'].append(alt_text)
                    elif 'hulls' in src:
                        player_data['equipment']['hulls'].append(alt_text)
                    elif 'colormaps' in src:
                        player_data['equipment']['paints'].append(alt_text)
                    elif 'resistances' in src:
                        player_data['equipment']['modules'].append(alt_text)
            
            return player_data
            
        except Exception as e:
            logger.error(f"Error parsing player profile: {e}")
            return None
    
    async def get_player_stats(self, nickname: str) -> Optional[Dict]:
        """Get player statistics from RTanks ratings"""
        cache_key = f"player_{nickname}"
        
        # Check cache first
        cached_data = self.get_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        # Fetch from website
        url = f"{self.base_url}/user/{nickname}"
        html = await self.fetch_page(url)
        
        if not html:
            return None
        
        player_data = self.parse_player_profile(html, nickname)
        
        if player_data:
            self.set_cache(cache_key, player_data)
        
        return player_data
    
    def parse_leaderboard(self, html: str) -> List[Dict]:
        """Parse leaderboard HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            players = []
            
            # Find the leaderboard table
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        # Extract rank, player name, and value
                        rank_text = cells[0].get_text(strip=True)
                        player_cell = cells[1]
                        value_text = cells[2].get_text(strip=True)
                        
                        # Extract player name from link or img alt
                        player_name = None
                        player_link = player_cell.find('a')
                        if player_link:
                            player_name = player_link.get_text(strip=True)
                        
                        # Also check for img alt attribute
                        if not player_name:
                            img = player_cell.find('img')
                            if img:
                                player_name = img.get('alt', '').strip()
                        
                        # Try to extract from any text in the cell
                        if not player_name:
                            player_name = player_cell.get_text(strip=True)
                        
                        # Clean up player name
                        if player_name:
                            # Remove rank icons and other prefixes
                            player_name = re.sub(r'^[\d\s]+', '', player_name).strip()
                            player_name = re.sub(r'^\W+', '', player_name).strip()
                        
                        # Validate rank
                        if rank_text.isdigit() and player_name and value_text:
                            # Clean up value (remove non-numeric characters except spaces)
                            value_clean = re.sub(r'[^\d\s]', '', value_text).strip()
                            value_clean = value_clean.replace(' ', '')
                            
                            try:
                                if value_clean:
                                    value = int(value_clean)
                                else:
                                    value = 0
                            except ValueError:
                                value = 0
                            
                            players.append({
                                'rank': int(rank_text),
                                'name': player_name,
                                'value': value,
                                'formatted_value': value_text
                            })
            
            # Sort by rank and limit to top 10
            players.sort(key=lambda x: x['rank'])
            return players[:10]
            
        except Exception as e:
            logger.error(f"Error parsing leaderboard: {e}")
            return []
    
    async def get_leaderboard(self, category: str) -> Optional[List[Dict]]:
        """Get leaderboard for specified category"""
        cache_key = f"leaderboard_{category}"
        
        # Check cache first
        cached_data = self.get_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        # Fetch main ratings page
        url = self.base_url
        html = await self.fetch_page(url)
        
        if not html:
            return None
        
        # Parse leaderboard data
        leaderboard_data = self.parse_leaderboard(html)
        
        if leaderboard_data:
            self.set_cache(cache_key, leaderboard_data)
        
        return leaderboard_data
    
    def __del__(self):
        """Cleanup when scraper is destroyed"""
        if self.session and not self.session.closed:
            asyncio.create_task(self.close_session())
