import requests
from typing import Optional

# Attempt to import lxml, handle potential ImportError
try:
    from lxml import etree
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False
    print("Warning: lxml library not found. HTML parsing for store name extraction will not work.")
    # Define a dummy etree object to avoid NameError later if lxml is not available
    class DummyEtree:
        class DummyHtmlElement:
            text = None
        class DummyParserError(Exception):
            pass
        HTML = lambda x: None # Dummy function
        XMLSyntaxError = DummyParserError # Dummy exception

    etree = DummyEtree()


def extract_restaurant_name(url: str) -> Optional[str]:
    """
    주어진 Naver Place URL에서 HTML을 가져와 XPath를 사용하여 업체명을 추출합니다.
    추출 성공 시 업체명(str), 실패 시 None을 반환합니다.

    Args:
        url (str): Naver Place 레스토랑 상세 페이지 URL

    Returns:
        Optional[str]: 추출된 업체명 또는 None
    """
    if not LXML_AVAILABLE:
        print("Error: lxml library is required for store name extraction.")
        return None # Cannot proceed without lxml

    headers = {
        'User-Agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/601.3.9 (KHTML, like Gecko) Version/9.0.2 Safari/601.3.9",
        'Referer': 'https://m.place.naver.com/', # Use mobile referer as it might be more stable
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Connection': 'keep-alive'
    }

    try:
        print(f"Extracting name from URL: {url}") # Server log
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        print("HTML fetched successfully.")

        # Use apparent_encoding and parse as string
        response.encoding = response.apparent_encoding
        html_text = response.text

        # Parse HTML using lxml
        tree = etree.HTML(html_text)
        if tree is None: # Check if parsing failed
             print("HTML parsing failed (tree is None).")
             return None
        print("HTML parsed successfully.")

        # Define potential XPaths (add more robust ones if needed)
        xpath_expression_1 = '//*[@id="_title"]/div/span[1]/text()' # Get text directly
        

        restaurant_name = None

        for i, xpath in enumerate([xpath_expression_1], 1):
            print(f"Trying XPath {i}: {xpath}")
            results = tree.xpath(xpath)
            # Filter out empty strings and take the first non-empty result
            valid_results = [r.strip() for r in results if isinstance(r, str) and r.strip()]
            if valid_results:
                restaurant_name = valid_results[0]
                print(f"Success! Extracted name: {restaurant_name}")
                break # Stop after first successful extraction
        else:
            print("Could not find restaurant name using any XPath.")
            return None # Return None if not found

        return restaurant_name

    except requests.exceptions.RequestException as e:
        print(f"Error during request for {url}: {e}")
        return None
    except etree.XMLSyntaxError as e:
        print(f"HTML parsing error for {url}: {e}")
        return None
    except Exception as e:
        print(f"Unknown error extracting name from {url}: {e}")
        return None

# --- 메인 실행 부분 제거됨 ---

# Example usage (for testing)
# if __name__ == "__main__":
#     test_url = "https://m.place.naver.com/restaurant/11797899/home" # Example URL
#     name = extract_restaurant_name(test_url)
#     if name:
#         print(f"\n--- Final Extracted Name ---")
#         print(name)
#     else:
#         print("\n--- Failed to extract name ---")
