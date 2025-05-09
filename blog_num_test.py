# blog_num_test.py

import requests
from lxml import etree # XPath 사용을 위해 lxml 사용
from bs4 import BeautifulSoup # 리뷰 페이지는 BS도 혼용 가능 (선택 사항)
import re
import time
import sys
from typing import Dict, Optional
from urllib.parse import quote

# --- 설정값 ---
API_URL = "https://map.naver.com/p/api/search/allSearch"
PLACE_REVIEW_PAGE_URL_FORMAT = "https://pcmap.place.naver.com/restaurant/{place_id}/review"
RESTAURANT_LIST_URL_WITH_STORE_NAME_FORMAT = (
    "https://pcmap.place.naver.com/restaurant/list"
    "?query={query}"
    "&x=129.338944&y=35.546513&clientX=129.338944&clientY=35.546513" # 이 좌표는 예시, 실제 검색 위치에 맞게 조절 필요
    "&from=nx&fromNxList=true&deviceType=pc&keywordFilter=voting%5Efalse"
    "&order=false&rank=저장많은" # "저장 많은 순" 정렬
    "®ion=&entry=pll&display=30" # display 개수 조절
    "&additionalHeight=76&locale=ko"
    "&mapUrl=https%3A%2F%2Fmap.naver.com%2Fp%2Fsearch%2F{keyword_for_mapurl}"
)
DEFAULT_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36")
DEFAULT_COORD = "126.97805611;37.56666694" # 서울 시청 좌표 (API 검색 시 사용)
REQUEST_DELAY_SEC = 0.5

# --- Helper Functions ---

def get_headers(referer: str = "https://map.naver.com/"):
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": referer,
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

def fetch_html_tree(url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[etree._ElementTree]:
    """주어진 URL의 HTML을 가져와 lxml 트리 객체로 반환"""
    try:
        time.sleep(REQUEST_DELAY_SEC)
        response = requests.get(url, params=params, headers=headers or get_headers(), timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding # 인코딩 추정
        tree = etree.HTML(response.text)
        # tree가 None이 아닌지 확인 (파싱 실패 시 None 반환 가능성)
        if tree is None:
            print(f"  [Error] HTML 파싱 실패 (tree is None) ({url})")
            return None
        return tree
    except requests.exceptions.RequestException as e:
        print(f"  [Error] HTML 가져오기 실패 ({url}): {e}")
    except etree.ParseError as e:
        # lxml HTML 파서는 약간의 오류는 무시하고 파싱하는 경향이 있음. 심각한 오류만 예외 발생.
        print(f"  [Error] HTML 파싱 중 심각한 오류 ({url}): {e}")
    except Exception as e:
        print(f"  [Error] HTML 처리 중 알 수 없는 오류 ({url}): {e}")
    return None

def extract_text_from_xpath(tree: etree._ElementTree, xpath: str) -> Optional[str]:
    """lxml 트리에서 XPath로 텍스트 추출 (string(.) 사용)"""
    if tree is None: return None
    try:
        elements = tree.xpath(xpath)
        if elements:
            # string(.) XPath 함수는 해당 노드와 모든 자손 노드의 텍스트를 합쳐서 반환
            text_content = elements[0].xpath("string(.)")
            if isinstance(text_content, str):
                return text_content.strip()
        return None
    except Exception as e:
        print(f"  [Error] XPath로 텍스트 추출 중 오류 ({xpath}): {e}")
    return None

def parse_number_from_text(text: Optional[str]) -> Optional[int]:
    """텍스트에서 숫자(콤마, '+' 포함)를 추출하여 정수로 변환"""
    if not text: return None
    # "저장수 1,000+" 와 같은 경우를 위해, 문자열 전체에서 숫자 패턴을 찾음
    match = re.search(r'([\d,]+)\+?', text)
    if match:
        # group(1)은 숫자와 콤마 부분만 가져옴
        num_str = match.group(1).replace(',', '')
        if num_str.isdigit():
            return int(num_str)
    return None

# --- Main Logic Functions ---

def get_store_id_and_rank_from_api(keyword: str, target_store_name: str) -> Optional[Dict]:
    """Naver allSearch API를 통해 가게 ID와 순위(API 기반)를 가져옴"""
    print(f"\n[단계 1] API에서 '{target_store_name}' 정보 검색 (키워드: '{keyword}')...")
    params = {
        "query": keyword, "type": "all", "searchCoord": DEFAULT_COORD,
        "page": 1, "displayCount": 100, "lang": "ko" # API 결과는 충분히 요청
    }
    try:
        # API 요청 시에는 User-Agent와 Referer 정도만 필요할 수 있음
        api_headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Referer": "https://map.naver.com/"
        }
        response = requests.get(API_URL, headers=api_headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        items = data.get("result", {}).get("place", {}).get("list", [])

        for idx, item in enumerate(items):
            store_name_from_api = item.get("name", "")
            if store_name_from_api == target_store_name:
                place_id = item.get("id")
                rank = idx + 1 # 0-based index to 1-based rank
                print(f"  API에서 '{target_store_name}' 찾음: ID={place_id}, API 순위={rank}")
                return {"place_id": place_id, "rank": rank}
        print(f"  API 검색 결과에서 '{target_store_name}'을(를) 찾지 못했습니다.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  [Error] API 요청 실패: {e}")
    except Exception as e:
        print(f"  [Error] API 데이터 처리 중 오류: {e}")
    return None

def get_review_counts(place_id: str) -> Dict[str, Optional[int]]:
    """개별 리뷰 페이지에서 방문자/블로그 리뷰 수 추출 (BeautifulSoup 사용)"""
    print(f"\n[단계 2] 리뷰 수 가져오기 (ID: {place_id})...")
    url = PLACE_REVIEW_PAGE_URL_FORMAT.format(place_id=place_id)
    reviews = {"visitor_reviews": None, "blog_reviews": None}
    try:
        time.sleep(REQUEST_DELAY_SEC)
        response = requests.get(url, headers=get_headers(url), timeout=10) # Referer를 해당 URL로 설정
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        # 리뷰 수 선택자는 비교적 안정적일 수 있음 (<a> 태그의 href 속성 기준)
        visitor_tag = soup.find('a', href=re.compile(r'/review/visitor'))
        if visitor_tag:
            reviews["visitor_reviews"] = parse_number_from_text(visitor_tag.get_text(strip=True))

        blog_tag = soup.find('a', href=re.compile(r'/review/ugc'))
        if blog_tag:
            reviews["blog_reviews"] = parse_number_from_text(blog_tag.get_text(strip=True))

        print(f"  방문자 리뷰: {reviews['visitor_reviews']}, 블로그 리뷰: {reviews['blog_reviews']}")
    except Exception as e:
        print(f"  [Error] 리뷰 수 추출 중 오류: {e}")
    return reviews

def get_saved_count(store_name_query: str, keyword_for_mapurl: str, target_place_id: str) -> Optional[int]:
    """검색 목록 페이지에서 특정 가게의 '저장하기' 수 추출 (XPath 사용)"""
    print(f"\n[단계 3] '저장하기' 수 가져오기 (가게명 검색: '{store_name_query}', 원래 키워드: '{keyword_for_mapurl}')...")

    encoded_query = quote(store_name_query)
    encoded_keyword = quote(keyword_for_mapurl)
    current_ts = str(int(time.time() * 1000))

    list_url = RESTAURANT_LIST_URL_WITH_STORE_NAME_FORMAT.format(
        query=encoded_query, keyword_for_mapurl=encoded_keyword
    ) + f"&ts={current_ts}"

    print(f"  접속 URL: {list_url}")
    # 검색 목록 페이지 접속 시에는 검색 페이지를 Referer로 설정하는 것이 더 자연스러울 수 있음
    tree = fetch_html_tree(list_url, headers=get_headers(referer=f"https://map.naver.com/p/search/{encoded_keyword}"))

    if tree is None:
        return None

    # 1. target_place_id를 포함하는 <li> 요소를 먼저 찾습니다. (더 안정적인 방법)
    xpath_to_target_li = f'//li[.//a[contains(@href, "/restaurant/{target_place_id}/")]]'
    target_li_elements = tree.xpath(xpath_to_target_li)

    if not target_li_elements:
        print(f"  [Info] XPath로 ID '{target_place_id}'를 가진 가게의 <li> 요소를 직접 찾지 못했습니다. 다른 방법을 시도합니다.")

        # 만약 ID로 li를 못찾으면, "삼산돈"이 항상 두번째 li라고 가정한 절대 XPath로 시도
        # (이 방법은 매우 불안정하므로, 실제로는 li를 찾는 XPath를 개선해야 함)
        print(f"  [Warning] 'li[2]' 가정을 사용하여 절대 경로로 재시도합니다 (불안정할 수 있음).")
        xpath_to_target_li_fallback = '/html/body/div[3]/div/div[2]/div[1]/ul/li[2]'
        target_li_elements = tree.xpath(xpath_to_target_li_fallback)
        if not target_li_elements:
             print(f"  [Error] 절대 경로 XPath ({xpath_to_target_li_fallback})로도 <li> 요소를 찾지 못했습니다.")
             return None

    target_li = target_li_elements[0]
    print(f"  대상 가게의 <li> 요소 찾음 (또는 가정된 위치 사용).")

    # 2. 찾은 <li> 내부에서 <div class="MVx6e">를 찾습니다. (상대 경로 사용)
    xpath_to_mvx6e_div = './/div[contains(@class, "MVx6e")]'
    mvx6e_div_elements = target_li.xpath(xpath_to_mvx6e_div)

    if not mvx6e_div_elements:
        print(f"  [Error] <li> 내부에서 <div class='MVx6e'> 요소를 찾지 못했습니다.")
        return None

    mvx6e_div = mvx6e_div_elements[0]
    print(f"  <div class='MVx6e'> 요소 찾음.")

    # 3. <div class="MVx6e"> 내부의 세 번째 <span>을 직접 선택하고 텍스트를 가져옵니다.
    #    (이전 디버깅 결과를 바탕으로 세 번째 span으로 가정)
    xpath_to_target_span = './span[3]'
    target_span_elements = mvx6e_div.xpath(xpath_to_target_span)

    raw_text_to_parse = None
    if target_span_elements:
        target_span = target_span_elements[0]
        text_content = target_span.xpath("string(.)") # span 내부의 모든 텍스트 가져오기

        if isinstance(text_content, str):
            raw_text_to_parse = text_content.strip()
            print(f"     - MVx6e의 세 번째 span 텍스트 가져옴: '{raw_text_to_parse}'")
        else:
            print("     - MVx6e의 세 번째 span에서 텍스트를 가져올 수 없음.")
    else:
        print(f"  [Error] <div class='MVx6e'> 내부에서 세 번째 <span> (XPath: {xpath_to_target_span})을 찾지 못했습니다.")
        # 디버깅용: mvx6e_div 내용 출력
        # print("   MVx6e div HTML:")
        # print(etree.tostring(mvx6e_div, pretty_print=True, encoding='unicode'))


    # 4. 가져온 텍스트에서 숫자만 추출합니다.
    if raw_text_to_parse:
        parsed_num = parse_number_from_text(raw_text_to_parse)
        if parsed_num is not None:
            print(f"     - 저장하기 수 추출됨: {parsed_num}")
            return parsed_num
        else:
            print(f"     - '저장하기' 수 패턴 매칭 또는 숫자 변환 실패. 텍스트: '{raw_text_to_parse}'")
    # else: raw_text_to_parse가 None이면 이미 로그 출력됨

    return None

# --- Main Execution ---
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python blog_num_test.py \"검색 키워드\" \"가게 이름\"")
        sys.exit(1)

    search_keyword = sys.argv[1]
    target_store_name = sys.argv[2]

    final_result = {
        "가게 이름": target_store_name,
        "검색 키워드": search_keyword,
        "API 순위": None,
        "가게 ID": None,
        "방문자 리뷰": None,
        "블로그 리뷰": None,
        "저장하기 수": None,
        "오류 메시지": None
    }

    # 1. API에서 가게 ID 및 순위 가져오기
    api_info = get_store_id_and_rank_from_api(search_keyword, target_store_name)

    if api_info and api_info.get("place_id"):
        final_result["가게 ID"] = api_info["place_id"]
        final_result["API 순위"] = api_info["rank"]

        # 2. 리뷰 수 가져오기
        review_info = get_review_counts(api_info["place_id"])
        final_result["방문자 리뷰"] = review_info["visitor_reviews"]
        final_result["블로그 리뷰"] = review_info["blog_reviews"]

        # 3. 저장하기 수 가져오기
        saved_count_info = get_saved_count(target_store_name, search_keyword, api_info["place_id"])
        final_result["저장하기 수"] = saved_count_info
    else:
        # API에서 정보를 못 찾았으면 오류 메시지 설정
        if not final_result["오류 메시지"]: # 다른 단계에서 오류가 설정되지 않았을 경우
             final_result["오류 메시지"] = "API에서 가게 정보를 찾을 수 없었습니다."

    print("\n--- 최종 수집 결과 ---")
    for key, value in final_result.items():
        # 오류 메시지는 마지막에 별도로 출력하거나, 값이 있을 때만 출력
        if key == "오류 메시지" and value is None:
            continue
        display_key = key.replace('_', ' ').capitalize()
        print(f"{display_key}: {value if value is not None else '정보 없음'}")