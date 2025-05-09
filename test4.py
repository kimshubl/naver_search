#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from typing import List, Dict, Tuple, Optional # Added Tuple, Optional

# Note: Removed argparse and main function for web integration

class NaverMapSearchRankFinder:
    """
    네이버 지도 allSearch 내부 API를 호출해
    키워드 검색 결과 상위 100개 중 특정 가게 이름의 순위를 찾습니다.
    (비공식 API, 언제든 바뀔 수 있음)
    """
    API_URL = "https://map.naver.com/p/api/search/allSearch"
    MAX_RESULTS = 100 # 고정적으로 100위까지 조회

    def __init__(self, user_agent: str = None, coord: str = None):
        # Provide default User-Agent if none is given
        default_ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/114.0.0.0 Safari/537.36")
        # Default coordinates (Seoul City Hall)
        default_coord = "126.97805611;37.56666694"

        self.headers = {
            "User-Agent": user_agent or default_ua,
            "Referer": "https://map.naver.com"
        }
        self.coord = coord or default_coord

    def fetch_top_100_places(self, keyword: str, per_page: int = 20) -> Optional[List[Dict]]: # Return type hint
        """키워드로 검색하여 상위 100개 장소 정보를 가져옵니다. 오류 시 None 반환."""
        places = []
        page = 1
        while len(places) < self.MAX_RESULTS:
            params = {
                "query":        keyword,
                "type":         "all",
                "searchCoord":  self.coord,
                "boundary":     "",
                "page":         page,
                "displayCount": per_page
            }
            try:
                resp = requests.get(self.API_URL, headers=self.headers, params=params, timeout=10)
                resp.raise_for_status() # HTTP 오류 발생 시 예외 발생
                data = resp.json()
                items = data.get("result", {})\
                            .get("place", {})\
                            .get("list", [])

                if not items: # 더 이상 결과가 없으면 중단
                    break

                for item in items:
                    places.append({
                        "rank": len(places) + 1, # 순위 정보 추가
                        "name": item.get("name", ""),
                        "id": item.get("id") # <<<--- ADDED PLACE ID
                    })
                    if len(places) >= self.MAX_RESULTS: # 100개 채우면 중단
                        break
                page += 1

            except requests.exceptions.RequestException as e:
                print(f"API 요청 중 오류 발생: {e}") # Log error server-side
                return None # Indicate error by returning None
            except Exception as e:
                print(f"데이터 처리 중 오류 발생: {e}") # Log error server-side
                return None # Indicate error by returning None

        return places[:self.MAX_RESULTS] # 정확히 100개 또는 그 이하 반환

    def find_rank_by_name(self, places: Optional[List[Dict]], store_name: str) -> Optional[Tuple[Optional[int], Optional[str]]]: # Return type hint
        """장소 목록에서 가게 이름으로 순위와 ID를 찾습니다. 못 찾으면 None 반환."""
        if not places:
             return None
        for place in places:
            if place.get("name") == store_name:
                return place.get("rank"), place.get("id") # <<<--- RETURN RANK AND ID
        return None # Not found (was return None, None which is a tuple, better to return just None)

# Example usage (can be removed or kept for testing)
# if __name__ == "__main__":
#     finder = NaverMapSearchRankFinder()
#     keyword_to_search = "강남역 맛집"
#     store_to_find = "땀땀" # Example store
#     print(f"Searching for '{keyword_to_search}'...")
#     results = finder.fetch_top_100_places(keyword_to_search)
#     if results:
#         print(f"Fetched {len(results)} results.")
#         rank_id_tuple = finder.find_rank_by_name(results, store_to_find)
#         if rank_id_tuple:
#             rank, place_id = rank_id_tuple
#             print(f"'{store_to_find}' found at rank {rank} with ID {place_id}.")
#         else:
#             print(f"'{store_to_find}' not found in top 100.")
#     else:
#         print("Failed to fetch results.")