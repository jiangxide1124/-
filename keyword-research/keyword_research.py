"""네이버 블로그(쇼핑커넥트)용 키워드 조사 스크립트.

씨앗 키워드를 넣으면 네이버 검색광고 API로 연관 키워드와 월간 검색수를 모으고,
네이버 블로그 검색 API로 블로그 문서 수를, 검색광고 입찰가 추정 API로
구매 의도(광고주가 얼마를 걸고 있는지)를 붙여 CSV로 저장한다.

필요한 환경 변수
  NAVER_SEARCHAD_CUSTOMER_ID, NAVER_SEARCHAD_ACCESS_LICENSE, NAVER_SEARCHAD_SECRET_KEY  (필수)
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET  (선택: 없으면 블로그 문서 수를 건너뜀)

사용 예
  python keyword_research.py 캠핑의자 무선청소기 제습기 -o out.csv
  python keyword_research.py -f seeds.txt --docs-top 150 --bid-top 80
"""

import argparse
import base64
import csv
import hashlib
import hmac
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SEARCHAD_BASE = "https://api.searchad.naver.com"
BLOG_SEARCH_URL = "https://openapi.naver.com/v1/search/blog.json"

# 사러 온 사람이 쓰는 표현. 포함되면 구매 의도 키워드로 본다.
INTENT_WORDS = ("추천", "비교", "가격", "순위", "가성비", "후기", "리뷰", "최저가",
                "구매", "고르는법", "고르는", "브랜드", "종류", "할인", "세일", "top")


def env(name, required=True):
    value = os.environ.get(name, "").strip()
    if required and not value:
        sys.exit(f"환경 변수 {name} 가 없습니다. 클라우드 환경 설정에 등록한 뒤 새 세션에서 실행하세요.")
    return value


def request_json(url, headers, data=None, method="GET", retries=4):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            # 429(호출 과다)와 5xx만 잠깐 쉬었다가 다시 시도한다.
            if (e.code == 429 or e.code >= 500) and attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {e.code} {url.split('?')[0]}: {detail}") from None
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"접속 실패 {url.split('?')[0]}: {e.reason}") from None


class SearchAd:
    """네이버 검색광고 API. 서명 방식은 naver/searchad-apidoc 공식 샘플과 같다."""

    def __init__(self, customer_id, access_license, secret_key):
        self.customer_id = customer_id
        self.access_license = access_license
        self.secret_key = secret_key

    def signature(self, timestamp, method, uri):
        message = f"{timestamp}.{method}.{uri}"
        digest = hmac.new(self.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def headers(self, method, uri):
        timestamp = str(round(time.time() * 1000))
        return {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Timestamp": timestamp,
            "X-API-KEY": self.access_license,
            "X-Customer": str(self.customer_id),
            "X-Signature": self.signature(timestamp, method, uri),
        }

    def related_keywords(self, hints):
        """힌트 키워드(최대 5개)의 연관 키워드와 통계를 돌려준다."""
        uri = "/keywordstool"
        query = urllib.parse.urlencode({"hintKeywords": ",".join(hints), "showDetail": 1})
        result = request_json(f"{SEARCHAD_BASE}{uri}?{query}", self.headers("GET", uri))
        # 문서상 응답은 배열이지만 실제로는 {"keywordList": [...]}로 오는 경우가 있어 둘 다 받는다.
        return result.get("keywordList", []) if isinstance(result, dict) else result

    def top_bids(self, keywords, device="MOBILE", position=1):
        """해당 순위에 광고를 걸려면 필요한 평균 입찰가(원)를 키워드별로 돌려준다."""
        uri = "/estimate/average-position-bid/keyword"
        items = [{"key": k, "position": position} for k in keywords]
        result = request_json(f"{SEARCHAD_BASE}{uri}", self.headers("POST", uri),
                              data={"device": device, "items": items}, method="POST")
        return {row.get("keyword"): row.get("bid") for row in result.get("estimate", [])}


def blog_doc_count(keyword, client_id, client_secret):
    query = urllib.parse.urlencode({"query": keyword, "display": 1})
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    return request_json(f"{BLOG_SEARCH_URL}?{query}", headers).get("total")


def to_number(value):
    """'< 10' 같은 값은 5로 본다(10 미만의 중간값). 숫자가 아니면 0."""
    if isinstance(value, (int, float)):
        return value
    text = str(value).replace(",", "").strip()
    if text.startswith("<"):
        return 5
    try:
        number = float(text)
    except ValueError:
        return 0
    return int(number) if number.is_integer() else number


def has_intent(keyword):
    lowered = keyword.lower()
    return any(word in lowered for word in INTENT_WORDS)


def opportunity_score(row):
    """1차 선별용 점수. 검색량(로그) × 경쟁 틈(검색수/문서수, 최대 5) × 구매 의도 가중치.

    절대 기준이 아니라 후보를 추리는 용도다. 문서 수가 없으면 경쟁 틈은 1로 둔다.
    """
    searches = row["월간검색수"]
    if searches <= 0:
        return 0.0
    docs = row.get("블로그문서수")
    gap = min(searches / max(docs, 1), 5.0) if isinstance(docs, (int, float)) else 1.0
    weight = 1.5 if row["구매의도"] == "Y" else 1.0
    return round(math.log10(searches + 1) * gap * weight, 3)


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def load_seeds(args):
    seeds = list(args.keywords)
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            seeds += [line.strip() for line in f if line.strip() and not line.startswith("#")]
    # 검색광고 API는 힌트 키워드에 띄어쓰기를 받지 않는다.
    seeds = [s.replace(" ", "") for s in seeds]
    return list(dict.fromkeys(seeds))


def main():
    parser = argparse.ArgumentParser(description="네이버 키워드 검색량·경쟁도·구매의도 조사")
    parser.add_argument("keywords", nargs="*", help="씨앗 키워드")
    parser.add_argument("-f", "--file", help="씨앗 키워드 파일(한 줄에 하나, #은 주석)")
    parser.add_argument("-o", "--output", default="keyword_report.csv", help="결과 CSV 경로")
    parser.add_argument("--min-searches", type=int, default=100, help="이보다 월간 검색수가 적으면 제외")
    parser.add_argument("--docs-top", type=int, default=100, help="블로그 문서 수를 조회할 상위 키워드 수")
    parser.add_argument("--bid-top", type=int, default=50, help="입찰가를 조회할 상위 키워드 수(0이면 건너뜀)")
    parser.add_argument("--sleep", type=float, default=0.3, help="API 호출 사이 대기(초)")
    args = parser.parse_args()

    seeds = load_seeds(args)
    if not seeds:
        parser.error("씨앗 키워드를 인자나 -f 파일로 넣어 주세요.")

    api = SearchAd(env("NAVER_SEARCHAD_CUSTOMER_ID"), env("NAVER_SEARCHAD_ACCESS_LICENSE"),
                   env("NAVER_SEARCHAD_SECRET_KEY"))
    client_id = env("NAVER_CLIENT_ID", required=False)
    client_secret = env("NAVER_CLIENT_SECRET", required=False)

    # 1) 연관 키워드와 검색수
    rows = {}
    for group in chunks(seeds, 5):
        seed_label = ",".join(group)
        print(f"[연관 키워드] {seed_label}", file=sys.stderr)
        for item in api.related_keywords(group):
            keyword = item.get("relKeyword")
            if not keyword or keyword in rows:
                continue
            pc, mobile = to_number(item.get("monthlyPcQcCnt")), to_number(item.get("monthlyMobileQcCnt"))
            rows[keyword] = {
                "키워드": keyword,
                "씨앗": seed_label,
                "PC검색수": pc,
                "모바일검색수": mobile,
                "월간검색수": pc + mobile,
                "광고경쟁도": item.get("compIdx", ""),
                "광고클릭수(모바일)": to_number(item.get("monthlyAveMobileClkCnt")),
                "구매의도": "Y" if has_intent(keyword) else "N",
            }
        time.sleep(args.sleep)

    ranked = sorted((r for r in rows.values() if r["월간검색수"] >= args.min_searches),
                    key=lambda r: r["월간검색수"], reverse=True)
    print(f"연관 키워드 {len(rows)}개 중 검색수 {args.min_searches} 이상 {len(ranked)}개", file=sys.stderr)

    # 2) 블로그 문서 수
    if client_id and client_secret:
        for row in ranked[:args.docs_top]:
            try:
                row["블로그문서수"] = blog_doc_count(row["키워드"], client_id, client_secret)
            except RuntimeError as e:
                print(f"  문서 수 실패: {row['키워드']} ({e})", file=sys.stderr)
            time.sleep(args.sleep)
    else:
        print("NAVER_CLIENT_ID/SECRET 이 없어 블로그 문서 수는 건너뜁니다.", file=sys.stderr)

    # 3) 모바일 1위 평균 입찰가 = 광고주가 이 키워드에 거는 돈 = 구매 의도의 간접 지표
    if args.bid_top > 0:
        targets = [r["키워드"] for r in ranked[:args.bid_top]]
        for group in chunks(targets, 10):
            try:
                bids = api.top_bids(group)
            except RuntimeError as e:
                print(f"  입찰가 실패: {group[0]} 외 ({e})", file=sys.stderr)
                continue
            for keyword, bid in bids.items():
                if keyword in rows:
                    rows[keyword]["모바일1위입찰가"] = bid
            time.sleep(args.sleep)

    for row in ranked:
        docs = row.get("블로그문서수")
        row["검색수/문서수"] = round(row["월간검색수"] / max(docs, 1), 3) if isinstance(docs, (int, float)) else ""
        row["기회점수"] = opportunity_score(row)
    ranked.sort(key=lambda r: r["기회점수"], reverse=True)

    fields = ["키워드", "기회점수", "월간검색수", "PC검색수", "모바일검색수", "블로그문서수", "검색수/문서수",
              "구매의도", "모바일1위입찰가", "광고경쟁도", "광고클릭수(모바일)", "씨앗"]
    # utf-8-sig: 엑셀에서 열어도 한글이 깨지지 않게 한다.
    with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ranked)
    print(f"저장: {args.output} ({len(ranked)}행)", file=sys.stderr)


if __name__ == "__main__":
    main()
