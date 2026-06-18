"""
🐾 포포트립 - 반려동물 동반 여행 (전국 / 모바일 최적화 v4)
추가 기능: 견종 크기 필터, 지역 필터, 즐겨찾기, 날씨 연동

실행:
  pip install streamlit requests folium streamlit-folium
  streamlit run dogtour.py
"""

import streamlit as st
import requests
import folium
import math
import time
from streamlit_folium import st_folium

# ─────────────────────────────────────────────
# 인증키
# ─────────────────────────────────────────────
API_KEY     = "8d6656d9a842ee9bf952e1bc7cde6b0b758692f16419ced765b77784741c64a3"
WEATHER_KEY = "938b68fafe8695ff73e56663e4934dc2"
BASE_URL    = "http://apis.data.go.kr/B551011/KorPetTourService2"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

CATEGORY_MAP = {
    "전체":      None,
    "🏞 관광지":  "12",
    "🎭 문화":   "14",
    "🎪 축제":   "15",
    "🏄 레포츠": "28",
    "🏨 숙박":   "32",
    "🛍 쇼핑":   "38",
    "🍽 음식점":  "39",
}
CATEGORY_LABEL = {v: k for k, v in CATEGORY_MAP.items()}

REGION_MAP = {
    "전국": None, "서울": "11", "부산": "21", "대구": "22",
    "인천": "23", "광주": "24", "대전": "25", "울산": "26",
    "세종": "29", "경기": "31", "강원": "32", "충북": "33",
    "충남": "34", "경북": "35", "경남": "36", "전북": "37",
    "전남": "38", "제주": "39",
}

REGION_CENTER = {
    "11": (37.5665,126.9780), "21": (35.1796,129.0756),
    "22": (35.8714,128.6014), "23": (37.4563,126.7052),
    "24": (35.1595,126.8526), "25": (36.3504,127.3845),
    "26": (35.5384,129.3114), "29": (36.4800,127.2890),
    "31": (37.4138,127.5183), "32": (37.8228,128.1555),
    "33": (36.6357,127.4917), "34": (36.6588,126.6728),
    "35": (36.4919,128.8889), "36": (35.4606,128.2132),
    "37": (35.7175,127.1530), "38": (34.8679,126.9910),
    "39": (33.4890,126.4983),
}

BADGE_COLOR = {
    "12":"#4CAF50","14":"#9C27B0","15":"#FF9800",
    "28":"#2196F3","32":"#F44336","38":"#E91E63","39":"#795548",
}
MARKER_COLOR = {
    "12":"green","14":"purple","15":"orange",
    "28":"blue","32":"red","38":"pink","39":"darkred",
}

KR_LAT, KR_LON = 36.5, 127.8


# ─────────────────────────────────────────────
# API 함수
# ─────────────────────────────────────────────
def fetch_places(content_type_id=None, region_code=None):
    params = {
        "serviceKey": API_KEY, "numOfRows": 100, "pageNo": 1,
        "MobileOS": "ETC", "MobileApp": "PawPawTrip",
        "_type": "json", "arrange": "C",
    }
    if content_type_id: params["contentTypeId"] = content_type_id
    if region_code:     params["lDongRegnCd"]   = region_code
    try:
        res = requests.get(f"{BASE_URL}/areaBasedList2", params=params, timeout=10)
        if res.text.strip().startswith("<"):
            return None, f"API 키 오류\n{res.text[:200]}"
        data = res.json()
        hdr  = data["response"]["header"]
        if hdr["resultCode"] != "0000":
            return None, f"API 오류: {hdr['resultMsg']}"
        body = data["response"]["body"]
        if body["totalCount"] == 0: return [], None
        items = body["items"]["item"]
        return (items if isinstance(items, list) else [items]), None
    except requests.exceptions.Timeout:
        return None, "요청 시간 초과."
    except Exception as e:
        return None, str(e)


def fetch_nearby(lat, lon, radius=5000, content_type_id=None):
    params = {
        "serviceKey": API_KEY, "numOfRows": 10, "pageNo": 1,
        "MobileOS": "ETC", "MobileApp": "PawPawTrip",
        "_type": "json", "arrange": "E",
        "mapX": lon, "mapY": lat, "radius": radius,
    }
    if content_type_id: params["contentTypeId"] = content_type_id
    try:
        res  = requests.get(f"{BASE_URL}/locationBasedList2", params=params, timeout=10)
        if res.text.strip().startswith("<"): return []
        data = res.json()
        body = data["response"]["body"]
        if body["totalCount"] == 0: return []
        items = body["items"]["item"]
        return items if isinstance(items, list) else [items]
    except Exception:
        return []


def fetch_pet_detail(content_id):
    params = {
        "serviceKey": API_KEY, "contentId": content_id,
        "MobileOS": "ETC", "MobileApp": "PawPawTrip", "_type": "json",
    }
    try:
        res  = requests.get(f"{BASE_URL}/detailPetTour2", params=params, timeout=10)
        if res.text.strip().startswith("<"): return None
        data = res.json()
        item = data["response"]["body"]["items"]["item"]
        return item[0] if isinstance(item, list) else item
    except Exception:
        return None


def fetch_weather(lat, lon):
    try:
        res  = requests.get(WEATHER_URL, params={
            "lat": lat, "lon": lon, "appid": WEATHER_KEY,
            "lang": "kr", "units": "metric",
        }, timeout=5)
        data = res.json()
        if data.get("cod") != 200: return None
        temp  = data["main"]["temp"]
        feel  = data["main"]["feels_like"]
        hum   = data["main"]["humidity"]
        wind  = data["wind"]["speed"]
        desc  = data["weather"][0]["description"]
        icon  = data["weather"][0]["icon"]
        wm    = data["weather"][0]["main"]
        if wm in ["Thunderstorm","Drizzle","Rain"]:
            em,msg,col = "🌧️","비가 와요. 실내 장소 위주로 방문하세요.","#2196F3"
        elif wm == "Snow":
            em,msg,col = "❄️","눈이 와요. 발바닥 보온에 주의하세요.","#90CAF9"
        elif wm in ["Mist","Fog","Haze","Dust","Sand"]:
            em,msg,col = "🌫️","미세먼지·안개 주의. 외출을 자제하세요.","#9E9E9E"
        elif temp >= 30:
            em,msg,col = "🌡️","매우 더워요. 그늘·실내 위주로 이동하세요.","#F44336"
        elif temp >= 25:
            em,msg,col = "☀️","따뜻해요. 물과 그늘 준비를 잊지 마세요.","#FF9800"
        elif temp <= 0:
            em,msg,col = "🥶","매우 추워요. 강아지 옷을 챙겨주세요.","#3F51B5"
        elif temp <= 10:
            em,msg,col = "🧥","쌀쌀해요. 외투를 챙겨주세요.","#607D8B"
        else:
            em,msg,col = "🐾","산책하기 좋은 날씨예요!","#4CAF50"
        return {
            "temp": round(temp,1), "feel": round(feel,1),
            "hum": hum, "wind": wind, "desc": desc,
            "icon_url": f"https://openweathermap.org/img/wn/{icon}@2x.png",
            "em": em, "msg": msg, "col": col,
        }
    except Exception:
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dl = math.radians(lat2-lat1); dL = math.radians(lon2-lon1)
    a  = math.sin(dl/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dL/2)**2
    return R*2*math.asin(math.sqrt(a))


# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="🐾 포포트립",
    page_icon="🐾",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700;800&display=swap');
* { font-family:'Noto Sans KR',sans-serif; box-sizing:border-box; }
.stApp { background:#F7F3EF; }

/* 인트로 */
.intro-wrap {
    position:fixed;inset:0;
    background:linear-gradient(160deg,#FF8C69,#FF5F5F);
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    z-index:9999;animation:fadeOut .6s ease 2.4s forwards;
}
@keyframes fadeOut{to{opacity:0;pointer-events:none;}}
.intro-paw{font-size:72px;animation:bounce .8s infinite alternate;}
@keyframes bounce{to{transform:translateY(-12px);}}
.intro-title{font-size:26px;font-weight:800;color:white;margin-top:18px;}
.intro-sub{font-size:14px;color:rgba(255,255,255,.85);margin-top:8px;}
.intro-dots{display:flex;gap:8px;margin-top:28px;}
.intro-dots span{
    width:8px;height:8px;border-radius:50%;
    background:rgba(255,255,255,.5);animation:dot 1.2s infinite;
}
.intro-dots span:nth-child(2){animation-delay:.2s;}
.intro-dots span:nth-child(3){animation-delay:.4s;}
@keyframes dot{0%,80%,100%{opacity:.3}40%{opacity:1}}

/* 히어로 */
.hero{
    background:linear-gradient(135deg,#FF8C69,#FF5F5F);
    border-radius:22px;padding:26px 20px 22px;
    text-align:center;margin-bottom:18px;color:white;
}
.hero h1{font-size:24px;font-weight:800;margin:0 0 5px;}
.hero p{font-size:13px;margin:0;opacity:.88;}

/* 필터 박스 */
.filter-section{
    background:white;border-radius:18px;padding:16px;
    margin-bottom:14px;box-shadow:0 2px 10px rgba(0,0,0,.06);
}
.filter-title{font-size:11px;font-weight:700;color:#aaa;margin-bottom:8px;letter-spacing:.5px;}

/* 검색창 */
.stTextInput input{
    border-radius:50px!important;border:2px solid #eee!important;
    padding:11px 18px!important;font-size:14px!important;
    background:white!important;box-shadow:0 2px 8px rgba(0,0,0,.06)!important;
}
.stTextInput input:focus{
    border-color:#FF6B6B!important;
    box-shadow:0 0 0 3px rgba(255,107,107,.15)!important;
}

/* selectbox */
.stSelectbox>div>div{border-radius:12px!important;border:2px solid #eee!important;font-size:13px!important;}

/* 카테고리·견종 버튼 — 1. 고정 높이, 작은 글씨 */
div[data-testid="column"] .stButton button{
    border-radius:50px!important;
    border:2px solid #eee!important;
    background:white!important;
    color:#555!important;
    font-size:10px!important;        /* 글씨 작게 */
    font-weight:700!important;
    padding:0 4px!important;
    width:100%!important;
    height:44px!important;           /* 고정 높이 */
    line-height:1.2!important;
    white-space:nowrap!important;    /* 줄바꿈 금지 */
    overflow:hidden!important;
    text-overflow:ellipsis!important;
    box-shadow:0 1px 4px rgba(0,0,0,.06)!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
}
div[data-testid="column"] .stButton button:hover{
    border-color:#FF6B6B!important;color:#FF6B6B!important;
}

/* 요약 카드 */
.stat-row{display:flex;gap:10px;margin:14px 0;}
.stat-card{
    flex:1;background:white;border-radius:16px;
    padding:14px 8px;text-align:center;
    box-shadow:0 2px 8px rgba(0,0,0,.06);
}
.stat-card .num{font-size:22px;font-weight:800;color:#FF6B6B;}
.stat-card .lbl{font-size:11px;color:#aaa;margin-top:3px;}

/* 장소 카드 */
.place-card{
    background:white;border-radius:20px;overflow:hidden;
    box-shadow:0 3px 14px rgba(0,0,0,.08);margin-bottom:16px;
}
.place-card .thumb{width:100%;height:175px;object-fit:cover;display:block;}
.place-card .no-thumb{
    width:100%;height:110px;
    background:linear-gradient(135deg,#FFE0D6,#FFB3A7);
    display:flex;align-items:center;justify-content:center;font-size:42px;
}
.place-body{padding:14px 16px 4px;}
.badge{
    display:inline-block;border-radius:50px;
    padding:3px 11px;font-size:11px;font-weight:700;color:white;margin-bottom:6px;
}
.place-name{font-size:17px;font-weight:800;color:#222;margin-bottom:3px;}
.place-addr{font-size:12px;color:#999;line-height:1.5;margin-bottom:6px;}
.place-tel{font-size:12px;color:#FF6B6B;margin-bottom:10px;}

/* 반려동물 정보 박스 */
.pet-box{
    background:#FFF6F4;border:1.5px solid #FFD0C7;
    border-radius:14px;padding:14px 16px;margin:4px 0 12px;
}
.pet-row{display:flex;gap:10px;margin-bottom:7px;align-items:flex-start;}
.pet-lbl{font-size:11px;font-weight:700;color:#FF6B6B;min-width:68px;padding-top:1px;}
.pet-val{font-size:13px;color:#444;line-height:1.6;}

/* 날씨 카드 */
.weather-wrap{margin:6px 0 14px;width:100%;}
.weather-card{
    background:#EEF6FF;border-radius:16px;
    padding:14px 16px;margin-bottom:8px;width:100%;
}
.weather-row{
    display:table;width:100%;
}
.weather-icon-cell{
    display:table-cell;width:70px;vertical-align:middle;
}
.weather-icon-cell img{width:64px;height:64px;}
.weather-text-cell{
    display:table-cell;vertical-align:middle;padding-left:8px;
}
.w-temp{font-size:26px;font-weight:800;color:#1A1A2E;line-height:1;}
.w-desc{font-size:13px;color:#666;margin-top:4px;}
.w-sub{font-size:11px;color:#aaa;margin-top:3px;line-height:1.8;}
.weather-rec{
    border-radius:12px;padding:10px 14px;margin-top:8px;
    font-size:13px;font-weight:600;
    display:table;width:100%;
}

/* 루트 추천 */
.route-header{
    background:linear-gradient(135deg,#667eea,#764ba2);
    border-radius:16px;padding:16px;margin:8px 0 14px;color:white;
}
.route-header h3{font-size:16px;font-weight:700;margin:0 0 4px;}
.route-header p{font-size:12px;margin:0;opacity:.85;}
.route-card{
    background:white;border-radius:14px;padding:12px 14px;
    margin-bottom:10px;box-shadow:0 2px 8px rgba(0,0,0,.07);
    display:flex;gap:12px;align-items:center;
}
.route-num{
    width:32px;height:32px;border-radius:50%;
    background:linear-gradient(135deg,#FF8C69,#FF5F5F);
    color:white;font-size:14px;font-weight:800;
    display:flex;align-items:center;justify-content:center;flex-shrink:0;
}
.route-info .r-name{font-size:14px;font-weight:700;color:#222;}
.route-info .r-dist{font-size:11px;color:#aaa;margin-top:2px;}
.route-info .r-cat{font-size:11px;color:#FF6B6B;font-weight:600;}

/* 즐겨찾기 빈 화면 */
.fav-empty{text-align:center;padding:48px 20px;color:#bbb;}
.fav-empty .icon{font-size:52px;margin-bottom:14px;}
.fav-empty .msg{font-size:15px;font-weight:600;}
.fav-empty .sub{font-size:13px;margin-top:6px;}

/* 전체 버튼 공통 (카드 아래 액션 버튼) */
.stButton>button{
    border-radius:50px!important;border:none!important;
    background:#FF6B6B!important;color:white!important;
    font-weight:700!important;font-size:13px!important;
    padding:10px!important;width:100%!important;
    box-shadow:0 3px 10px rgba(255,107,107,.3)!important;
}
.stButton>button:hover{background:#FF5252!important;}

/* 탭 */
.stTabs [data-baseweb="tab-list"]{background:#F7F3EF;gap:6px;}
.stTabs [data-baseweb="tab"]{border-radius:50px;font-size:14px;font-weight:700;padding:8px 20px;}
.stTabs [aria-selected="true"]{background:#FF6B6B!important;color:white!important;}

/* 레이아웃 */
.block-container{padding:1rem 1rem 4rem!important;max-width:480px!important;}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 세션 초기화
# ─────────────────────────────────────────────
for k, v in {
    "intro_done": False, "selected_cat": "전체",
    "selected_region": "전국", "dog_size": "전체",
    "favorites": [], "fav_data": {}, "route_place": None,
    "active_panel": {},   # {cid: "pet"|"weather"|"route"|None}
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────
# 인트로 (세션당 1회)
# ─────────────────────────────────────────────
if not st.session_state.intro_done:
    st.markdown("""
    <div class="intro-wrap">
      <div class="intro-paw">🐾</div>
      <div class="intro-title">포포트립</div>
      <div class="intro-sub">강아지와 함께하는 특별한 여행</div>
      <div class="intro-dots"><span></span><span></span><span></span></div>
    </div>
    """, unsafe_allow_html=True)
    time.sleep(3)
    st.session_state.intro_done = True
    st.rerun()


# ─────────────────────────────────────────────
# 히어로
# ─────────────────────────────────────────────
fav_count = len(st.session_state.favorites)
st.markdown("""
<div class="hero">
  <h1>🐾 포포트립</h1>
  <p>전국 반려동물 동반 가능 장소를 찾아보세요</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 필터 섹션
# ─────────────────────────────────────────────
with st.container():
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)

    keyword = st.text_input("", placeholder="🔍  장소명 또는 지역 검색...", label_visibility="collapsed")

    st.markdown('<div class="filter-title">📍 지역 선택</div>', unsafe_allow_html=True)
    selected_region = st.selectbox(
        "", list(REGION_MAP.keys()),
        index=list(REGION_MAP.keys()).index(st.session_state.selected_region),
        label_visibility="collapsed", key="region_select",
    )
    if selected_region != st.session_state.selected_region:
        st.session_state.selected_region = selected_region
        st.rerun()

    # 2. 견종 크기 — 선택해도 장소 수 안 줄어들게
    st.markdown('<div class="filter-title" style="margin-top:12px">🐕 견종 크기 (동반 정보 표시용)</div>', unsafe_allow_html=True)
    size_cols = st.columns(3)
    for col, (size, icon) in zip(size_cols, [("전체","🐾 전체"),("소형견","🐩 소형견"),("대형견","🐕 대형견")]):
        with col:
            label = f"✅{icon}" if st.session_state.dog_size == size else icon
            if st.button(label, key=f"size_{size}"):
                st.session_state.dog_size = size
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# 카테고리 버튼 (4+4, 1. 고정 높이)
st.markdown('<div class="filter-title">📂 카테고리</div>', unsafe_allow_html=True)
cat_items = list(CATEGORY_MAP.items())
for row in [cat_items[:4], cat_items[4:]]:
    cols = st.columns(len(row))
    for col, (cat_name, _) in zip(cols, row):
        with col:
            label = f"✅{cat_name}" if st.session_state.selected_cat == cat_name else cat_name
            if st.button(label, key=f"cat_{cat_name}"):
                st.session_state.selected_cat = cat_name
                st.rerun()

selected_cat    = st.session_state.selected_cat
content_type_id = CATEGORY_MAP[selected_cat]
region_code     = REGION_MAP[st.session_state.selected_region]
dog_size        = st.session_state.dog_size


# ─────────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────────
with st.spinner("불러오는 중..."):
    items, err = fetch_places(content_type_id, region_code)

if err:
    st.error(f"❌ {err}")
    st.info("💡 API_KEY를 Decoding 인증키로 교체했는지 확인해주세요.")
    st.stop()

if not items:
    st.warning("검색 결과가 없습니다.")
    st.stop()

if keyword:
    items = [p for p in items if keyword in p.get("title","") or keyword in p.get("addr1","")]
    if not items:
        st.warning(f"'{keyword}' 검색 결과가 없습니다.")
        st.stop()

# 2. 견종 필터 — 장소 수 줄이지 않고 카드에 배지만 표시
# (필터링 제거, 상세 페이지에서 관련 정보 강조 표시)


# ─────────────────────────────────────────────
# 요약 통계
# ─────────────────────────────────────────────
has_img = sum(1 for p in items if p.get("firstimage"))
cat_counts = {}
for p in items:
    c = CATEGORY_LABEL.get(str(p.get("contenttypeid","")), "기타")
    cat_counts[c] = cat_counts.get(c, 0) + 1
top_short = max(cat_counts, key=cat_counts.get).split()[-1] if cat_counts else "-"

st.markdown(f"""
<div class="stat-row">
  <div class="stat-card"><div class="num">{len(items)}</div><div class="lbl">검색 결과</div></div>
  <div class="stat-card"><div class="num">{has_img}</div><div class="lbl">사진 있는 곳</div></div>
  <div class="stat-card"><div class="num" style="font-size:15px">{top_short}</div><div class="lbl">가장 많은 유형</div></div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 탭
# ─────────────────────────────────────────────
fav_label = f"❤️  찜 ({fav_count})" if fav_count > 0 else "❤️  찜"
tab_list, tab_map, tab_fav = st.tabs(["📋  목록", "🗺️  지도", fav_label])


# ── 장소 카드 렌더링 ─────────────────────────
def render_place_card(place, show_route_btn=True):
    name       = place.get("title", "이름 없음")
    addr       = place.get("addr1", "")
    cat_id     = str(place.get("contenttypeid", ""))
    cat        = CATEGORY_LABEL.get(cat_id, "기타")
    img        = place.get("firstimage", "")
    tel        = place.get("tel", "")
    cid        = place.get("contentid", "")
    badge_color= BADGE_COLOR.get(cat_id, "#888")
    is_fav     = cid in st.session_state.favorites

    # 현재 열린 패널 상태
    panel = st.session_state.active_panel.get(cid, None)

    img_html = (
        f"<img class='thumb' src='{img}' alt='{name}'>"
        if img else "<div class='no-thumb'>🐾</div>"
    )
    st.markdown(f"""
    <div class="place-card">
      {img_html}
      <div class="place-body">
        <span class="badge" style="background:{badge_color}">{cat}</span>
        <div class="place-name">{name}</div>
        <div class="place-addr">📍 {addr}</div>
        {"<div class='place-tel'>📞 " + tel + "</div>" if tel else ""}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 버튼 색상: 활성 패널에 따라 다르게 ──
    # 각 버튼을 개별 컬럼으로 나눠서 CSS 직접 제어
    def btn_style(panel_name, color):
        """활성 패널이면 해당 색, 아니면 기본 coral"""
        if panel == panel_name:
            return color   # 활성
        return "#FF6B6B"   # 기본

    PET_COLOR     = "#4CAF50"   # 초록
    FAV_COLOR     = "#E91E63"   # 핑크
    WEATHER_COLOR = "#2196F3"   # 파랑
    ROUTE_COLOR   = "#9C27B0"   # 보라

    if show_route_btn:
        b1, b2, b3, b4 = st.columns(4)
    else:
        b1, b2, b3 = st.columns(3)
        b4 = None

    # 🐾 펫 정보 토글
    with b1:
        pet_active = (panel == "pet")
        st.markdown(f"""<style>
        div[data-testid="column"]:nth-of-type(1) .stButton button{{
            background:{PET_COLOR if pet_active else "#FF6B6B"}!important;
        }}</style>""", unsafe_allow_html=True)
        label = "🐾 닫기" if pet_active else "🐾 펫 정보"
        if st.button(label, key=f"pet_{cid}_{show_route_btn}"):
            st.session_state.active_panel[cid] = None if pet_active else "pet"
            st.rerun()

    # ❤️ 찜 토글
    with b2:
        fav_lbl = "❤️ 해제" if is_fav else "🤍 찜"
        st.markdown(f"""<style>
        div[data-testid="column"]:nth-of-type(2) .stButton button{{
            background:{FAV_COLOR if is_fav else "#FF6B6B"}!important;
        }}</style>""", unsafe_allow_html=True)
        if st.button(fav_lbl, key=f"fav_{cid}_{show_route_btn}"):
            if is_fav:
                st.session_state.favorites.remove(cid)
                st.session_state.fav_data.pop(cid, None)
            else:
                st.session_state.favorites.append(cid)
                st.session_state.fav_data[cid] = place
            st.rerun()

    # 🌤️ 날씨 토글
    with b3:
        weather_active = (panel == "weather")
        st.markdown(f"""<style>
        div[data-testid="column"]:nth-of-type(3) .stButton button{{
            background:{WEATHER_COLOR if weather_active else "#FF6B6B"}!important;
        }}</style>""", unsafe_allow_html=True)
        label = "🌤️ 닫기" if weather_active else "🌤️ 날씨"
        if st.button(label, key=f"weather_{cid}_{show_route_btn}"):
            st.session_state.active_panel[cid] = None if weather_active else "weather"
            st.rerun()

    # 🗺️ 주변 추천 토글
    if b4:
        with b4:
            route_active = (panel == "route")
            st.markdown(f"""<style>
            div[data-testid="column"]:nth-of-type(4) .stButton button{{
                background:{ROUTE_COLOR if route_active else "#FF6B6B"}!important;
            }}</style>""", unsafe_allow_html=True)
            label = "🗺️ 닫기" if route_active else "🗺️ 주변"
            if st.button(label, key=f"route_{cid}_{show_route_btn}"):
                st.session_state.active_panel[cid] = None if route_active else "route"
                st.rerun()

    # ── 패널 내용 표시 ──

    # 🐾 펫 정보
    if panel == "pet":
        with st.spinner("불러오는 중..."):
            detail = fetch_pet_detail(cid)
        if detail:
            rows = [
                ("동반 구역",     detail.get("acmpyTypeCd","")),
                ("동반 가능 동물", detail.get("acmpyPsblCpam","")),
                ("필요 사항",     detail.get("acmpyNeedMtr","")),
                ("기타 정보",     detail.get("etcAcmpyInfo","")),
                ("구비 시설",     detail.get("relaPosesFclty","")),
            ]
            pet_text = " ".join(v for _, v in rows if v)
            if dog_size != "전체":
                size_kw = "소형" if dog_size == "소형견" else "대형"
                if size_kw in pet_text:
                    st.success(f"✅ {dog_size} 동반 가능 정보가 있어요!")
                else:
                    st.warning(f"⚠️ {dog_size} 관련 명시 정보가 없습니다. 방문 전 확인하세요.")
            rows_html = "".join(
                f'<div class="pet-row"><div class="pet-lbl">{l}</div><div class="pet-val">{v}</div></div>'
                for l, v in rows if v
            )
            if rows_html:
                st.markdown(f'<div class="pet-box">{rows_html}</div>', unsafe_allow_html=True)
            else:
                st.info("상세 정보가 아직 등록되지 않은 장소입니다.")
        else:
            st.info("상세 정보가 아직 등록되지 않은 장소입니다.")

    # 🌤️ 날씨
    elif panel == "weather":
        p_lat = place.get("mapy", 0)
        p_lon = place.get("mapx", 0)
        if p_lat and p_lon:
            with st.spinner("날씨 불러오는 중..."):
                w = fetch_weather(float(p_lat), float(p_lon))
            if w:
                st.markdown(f"""
                <div class="weather-wrap">
                  <div class="weather-card">
                    <div class="weather-row">
                      <div class="weather-icon-cell">
                        <img src="{w['icon_url']}" alt="날씨">
                      </div>
                      <div class="weather-text-cell">
                        <div class="w-temp">{w['temp']}°C</div>
                        <div class="w-desc">{w['desc']}</div>
                        <div class="w-sub">체감 {w['feel']}°C<br>습도 {w['hum']}% · 바람 {w['wind']}m/s</div>
                      </div>
                    </div>
                    <div class="weather-rec" style="background:{w['col']}22;color:{w['col']}">
                      {w['em']} {w['msg']}
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("날씨 정보를 불러올 수 없습니다.")
        else:
            st.info("이 장소의 좌표 정보가 없습니다.")

    # 🗺️ 주변 추천
    elif panel == "route":
        try:
            r_lat = float(place.get("mapy", 0))
            r_lon = float(place.get("mapx", 0))
        except (ValueError, TypeError):
            r_lat = r_lon = 0

        if r_lat and r_lon:
            st.markdown(f"""
            <div class="route-header">
              <h3>📍 {name} 주변 추천</h3>
              <p>반경 5km 내 반려동물 동반 가능 장소</p>
            </div>
            """, unsafe_allow_html=True)
            with st.spinner("주변 장소 탐색 중..."):
                nearby = (
                    fetch_nearby(r_lat, r_lon, radius=5000, content_type_id="39") +
                    fetch_nearby(r_lat, r_lon, radius=5000, content_type_id="12")
                )
                results = []
                for nb in nearby:
                    if nb.get("contentid") == cid: continue
                    try:
                        dist = haversine_km(r_lat, r_lon, float(nb.get("mapy",0)), float(nb.get("mapx",0)))
                        results.append((dist, nb))
                    except (ValueError, TypeError):
                        continue
                results.sort(key=lambda x: x[0])
                results = results[:6]

            if results:
                for idx, (dist, nb) in enumerate(results, 1):
                    nb_cat   = CATEGORY_LABEL.get(str(nb.get("contenttypeid","")), "기타")
                    dist_str = f"{dist*1000:.0f}m" if dist < 1 else f"{dist:.1f}km"
                    addr_s   = nb.get("addr1","")[:20]
                    st.markdown(f"""
                    <div class="route-card">
                      <div class="route-num">{idx}</div>
                      <div class="route-info">
                        <div class="r-name">{nb.get('title','')}</div>
                        <div class="r-cat">{nb_cat}</div>
                        <div class="r-dist">📍 {dist_str} · {addr_s}</div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("반경 5km 내 다른 반려동물 동반 장소가 없습니다.")
        else:
            st.warning("이 장소의 좌표 정보가 없어 주변 추천이 어렵습니다.")


# ── 목록 탭 ───────────────────────────────────
with tab_list:
    for place in items:
        render_place_card(place, show_route_btn=True)


# ── 지도 탭 ───────────────────────────────────
with tab_map:
    if region_code and region_code in REGION_CENTER:
        c_lat, c_lon = REGION_CENTER[region_code]
        zoom = 10
    else:
        c_lat, c_lon = KR_LAT, KR_LON
        zoom = 7

    m = folium.Map(location=[c_lat, c_lon], zoom_start=zoom, tiles="CartoDB positron")

    for place in items:
        try:
            lat = float(place.get("mapy", 0))
            lon = float(place.get("mapx", 0))
        except (ValueError, TypeError):
            continue
        if not lat or not lon: continue

        cat_id   = str(place.get("contenttypeid",""))
        cat_name = CATEGORY_LABEL.get(cat_id, "기타")
        name     = place.get("title","")
        addr     = place.get("addr1","")
        tel      = place.get("tel","")
        img      = place.get("firstimage2","")
        is_fav   = place.get("contentid","") in st.session_state.favorites

        popup_html = f"""
        <div style='width:175px;font-family:sans-serif;font-size:12px;line-height:1.6'>
          {"❤️ " if is_fav else ""}<b style='font-size:13px'>{name}</b><br>
          <span style='color:#FF6B6B'>{cat_name}</span><br>
          📍 {addr}<br>{"📞 " + tel if tel else ""}
          {"<br><img src='" + img + "' width='165' style='margin-top:6px;border-radius:8px'>" if img else ""}
        </div>
        """
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=195),
            tooltip=("❤️ " if is_fav else "") + name,
            icon=folium.Icon(
                color="orange" if is_fav else MARKER_COLOR.get(cat_id,"gray"),
                icon="star" if is_fav else "paw", prefix="fa"
            ),
        ).add_to(m)

    st_folium(m, width=None, height=500)


# ── 즐겨찾기 탭 ───────────────────────────────
with tab_fav:
    if not st.session_state.favorites:
        st.markdown("""
        <div class="fav-empty">
          <div class="icon">🤍</div>
          <div class="msg">아직 찜한 장소가 없어요</div>
          <div class="sub">목록에서 🤍 찜하기 버튼을 눌러보세요</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"**총 {fav_count}곳을 찜했어요** ❤️")
        for cid in st.session_state.favorites:
            place = st.session_state.fav_data.get(cid)
            if place:
                render_place_card(place, show_route_btn=False)