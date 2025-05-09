# 여기에 앞서 작성한 make_signature(), get_monthly_search_volume() 함수 포함

from urllib.parse import urlparse, parse_qs
from blog_rank_test import get_monthly_search_volume

def extract_query_from_url(url):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    keyword = query_params.get('query', [None])[0]
    return keyword

def search_volume_from_url(url):
    keyword = extract_query_from_url(url)
    if keyword:
        print(f"추출된 키워드: {keyword}")
        return get_monthly_search_volume(keyword)
    else:
        print("URL에서 검색어를 추출할 수 없습니다.")
        return None

# ▶️ 실행 예시
def print_querry():
    search_url = " "
    result = search_volume_from_url(search_url)
    print(result)
