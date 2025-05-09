#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import datetime
from test4 import NaverMapSearchRankFinder
from blog_num_test import get_review_counts # 리뷰 수 가져오기
from blog_num_test2 import get_saved_count_from_list # << 저장하기 수 가져오기 함수 import

DB_NAME = 'rank_chart.db'

def _get_rank_and_insert(cursor, finder, store_name, keyword):
    """내부 헬퍼: 순위, 리뷰, 저장하기 수를 가져와 DB에 삽입. 순위 또는 None 반환."""
    rank = None
    place_id = None
    visitor_reviews = None
    blog_reviews = None
    saved_count_val = None # 저장하기 수 변수

    try:
        print(f" - '{store_name}' (키워드: '{keyword}') 정보 조회 중...")
        places = finder.fetch_top_100_places(keyword)

        rank_id_tuple = finder.find_rank_by_name(places, store_name)
        if rank_id_tuple:
            rank, place_id = rank_id_tuple

        if place_id:
            print(f"   -> 가게 ID: {place_id}. 리뷰 수 조회...")
            review_info = get_review_counts(place_id)
            if review_info:
                visitor_reviews = review_info.get("visitor_reviews")
                blog_reviews = review_info.get("blog_reviews")
                print(f"   -> 방문자 리뷰: {visitor_reviews}, 블로그 리뷰: {blog_reviews}")
        else:
            print(f"   -> 가게 ID를 찾지 못해 리뷰 수를 조회할 수 없습니다.")

        # 저장하기 수 가져오기 (가게 이름과 검색 키워드 사용)
        # search_keyword_for_url 인자는 get_saved_count_from_list 함수가 URL 생성 시 사용할 키워드
        # 일반적으로 tracked_items의 keyword와 동일하게 사용하거나, 가게 이름 자체를 사용할 수 있음.
        # 여기서는 tracked_items의 keyword를 사용합니다.
        print(f"   -> '{store_name}' 저장하기 수 조회 (URL 검색어: '{store_name}')...")
        saved_count_val = get_saved_count_from_list(
            target_store_name=store_name,         # 목록 내에서 찾을 실제 가게 이름
            search_keyword_for_url=store_name     # URL의 query 파라미터로 사용할 검색어 (가게 이름 자체)
        )
        if saved_count_val is not None:
            print(f"   -> 저장하기 수: {saved_count_val}")
        else:
            print(f"   -> 저장하기 수를 가져오지 못했습니다.")

        current_time = datetime.datetime.now()
        date_only = current_time.date()

        cursor.execute(
            "INSERT INTO requests (store_name, keyword, date, rank, visitor_reviews, blog_reviews, saved_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (store_name, keyword, date_only, rank, visitor_reviews, blog_reviews, saved_count_val) # saved_count_val 추가
        )

        if rank:
            print(f"   -> 최종 순위: {rank}. DB 저장 완료.")
        else:
            print(f"   -> 최종 순위: 100위 안에 없음 (또는 오류). DB 저장 완료.")
        return rank

    except Exception as e:
        print(f"   -> _get_rank_and_insert 오류 ({store_name}, {keyword}): {e}")
        return None

# update_single_rank 및 update_all_ranks 함수는 이전과 동일하게 _get_rank_and_insert를 호출합니다.
# (이하 update_single_rank, update_all_ranks 함수는 이전 답변과 동일하게 유지)
def update_single_rank(store_name: str, keyword: str):
    """단일 가게/키워드의 순위, 리뷰, 저장하기 수를 업데이트합니다."""
    conn = None
    rank_found = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        finder = NaverMapSearchRankFinder() # NaverMapSearchRankFinder 인스턴스 생성
        rank_found = _get_rank_and_insert(cursor, finder, store_name, keyword)
        conn.commit()
        print(f"단일 항목 업데이트 완료: '{store_name}' - '{keyword}'")
    except sqlite3.Error as e:
        print(f"단일 항목 업데이트 중 데이터베이스 오류 발생: {e}")
    except Exception as e:
        print(f"단일 항목 업데이트 중 예상치 못한 오류 발생: {e}")
    finally:
        if conn:
            conn.close()
    return rank_found


def update_all_ranks():
    """
    추적 중인 모든 항목의 순위, 리뷰, 저장하기 수를 업데이트합니다.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, store_name, keyword FROM tracked_items")
        tracked_items = cursor.fetchall()

        if not tracked_items:
            print("추적할 항목이 없습니다. 웹 인터페이스에서 추가해주세요.")
            return

        print(f"총 {len(tracked_items)}개의 항목 정보 업데이트 시작...")
        finder = NaverMapSearchRankFinder() # NaverMapSearchRankFinder 인스턴스 생성

        for item_id, store_name, keyword in tracked_items:
             _get_rank_and_insert(cursor, finder, store_name, keyword)
             conn.commit() # 각 항목 처리 후 커밋

        print("모든 항목 정보 업데이트 완료.")

    except sqlite3.Error as e:
        print(f"데이터베이스 작업 중 오류 발생: {e}")
    except Exception as e:
        print(f"스크립트 실행 중 예상치 못한 오류 발생: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    update_all_ranks()