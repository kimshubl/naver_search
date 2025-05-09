# blog_num_test2.py (이전 답변의 내용과 동일하다고 가정)
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import quote
import time

def parse_number_from_text(text: str) -> int | None:
    # ... (이전과 동일)
    if not text:
        return None
    match = re.search(r'(?:저장|저장수)\s*([\d,]+)\+?', text)
    if match:
        num_str = match.group(1).replace(',', '')
        if num_str.isdigit():
            return int(num_str)
    return None


def get_saved_count_from_list(target_store_name: str, search_keyword_for_url: str) -> int | None:
    """
    특정 가게의 '저장하기' 수를 네이버 플레이스 목록에서 가져옵니다.

    Args:
        target_store_name (str): 찾고자 하는 가게의 정확한 이름.
        search_keyword_for_url (str): 플레이스 목록 URL 생성 시 query 및 mapUrl에 사용될 검색 키워드.

    Returns:
        int | None: 저장하기 수 또는 실패 시 None.
    """
    encoded_query_param = quote(search_keyword_for_url)
    # mapUrl의 키워드도 일반적으로 query와 동일하게 사용하거나, 별도로 지정할 수 있습니다.
    # 여기서는 query와 동일하게 사용합니다.
    encoded_mapUrl_keyword_param = encoded_query_param
    current_timestamp_param = str(int(time.time() * 1000))

    coord_x = "129.338944" # 예시 좌표, 실제로는 위치 기반으로 동적 설정 필요
    coord_y = "35.546513"

    keywordFilter_param = quote("voting^false")
    rank_param = quote("저장많은")
    mapUrl_value = quote(f"https://map.naver.com/p/search/{search_keyword_for_url}")


    list_url = (
        f"https://pcmap.place.naver.com/restaurant/list?"
        f"query={encoded_query_param}&"
        f"x={coord_x}&y={coord_y}&"
        f"clientX={coord_x}&clientY={coord_y}&"
        f"from=nx&fromNxList=true&deviceType=pc&"
        f"keywordFilter={keywordFilter_param}&"
        f"order=false&rank={rank_param}&"
        f"region=&"
        f"x={coord_x}&y={coord_y}&" # 두 번째 x, y 세트
        f"entry=pll&display=30&" # display 항목 수를 줄여서 응답 크기 최적화 가능
        f"ts={current_timestamp_param}&"
        f"additionalHeight=76&locale=ko&"
        f"mapUrl={mapUrl_value}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://map.naver.com/"
    }
    print(f"저장하기 수 조회 시도 URL: {list_url}")
    try:
        response = requests.get(list_url, headers=headers, timeout=20) # 타임아웃 증가
        print(f"저장하기 수 조회 HTTP 응답 상태 코드: {response.status_code}")
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')

        store_list_items = soup.find_all('li', class_='UEzoS')
        if not store_list_items:
            print("저장하기 수 조회: 가게 목록(li.UEzoS)을 찾을 수 없습니다.")
            return None

        for item in store_list_items:
            store_name_span = item.find('span', class_='TYaxT')
            current_store_name = ""
            if store_name_span:
                current_store_name = store_name_span.get_text(strip=True)

            if target_store_name == current_store_name:
                print(f"저장하기 수 조회: '{target_store_name}' 가게를 찾았습니다.")
                mvx6e_div = item.find('div', class_='MVx6e')
                if not mvx6e_div:
                    continue
                h69bs_spans = mvx6e_div.find_all('span', class_='h69bs')
                if not h69bs_spans:
                    continue
                # "저장" 텍스트를 포함하는 span 찾기 (더 안정적일 수 있음)
                saved_span_text = None
                for span in h69bs_spans:
                    text_content = span.get_text(strip=True)
                    if "저장" in text_content:
                        saved_span_text = text_content
                        break
                
                if saved_span_text:
                    print(f"'{target_store_name}' 가게의 저장 관련 텍스트: '{saved_span_text}'")
                    saved_count = parse_number_from_text(saved_span_text)
                    if saved_count is not None:
                        return saved_count
                return None # 저장 텍스트를 못 찾거나 파싱 실패
        print(f"저장하기 수 조회: 목록에서 '{target_store_name}' 가게를 찾지 못했습니다.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"저장하기 수 조회 중 URL 요청 오류: {e}")
        return None
    except Exception as e:
        print(f"저장하기 수 조회 중 예기치 않은 오류: {e}")
        return None

# if __name__ == '__main__':
#     # 테스트용 코드 (선택적으로 사용)
#     target = "삼산돈"
#     keyword = "삼산돈" # 또는 "울산 삼산 맛집" 등
#     count = get_saved_count_from_list(target, keyword)
#     if count is not None:
#         print(f"'{target}'의 최종 저장하기 수: {count}")
#     else:
#         print(f"'{target}'의 저장하기 수를 가져오지 못했습니다.")