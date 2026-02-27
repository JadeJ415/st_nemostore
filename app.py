import streamlit as st
import pandas as pd
import json
import re
import plotly.express as px
import plotly.graph_objects as go
from bs4 import BeautifulSoup
from datetime import datetime

# ==========================================
# 1. 설정 및 스타일링
# ==========================================
st.set_page_config(page_title="Nemo Store Advanced Dashboard", page_icon="📈", layout="wide")

# 프리미엄 테마 적용 (CSS)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Outfit:wght@400;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Outfit', sans-serif; font-weight: 700; }
    
    .stApp { background-color: #0e1117; color: #ffffff; }
    
    /* 카드 디자인 */
    .detail-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }
    .detail-card:hover {
        border-color: #ff4b4b;
        transform: translateY(-2px);
    }
    
    /* 뱃지 */
    .badge {
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: bold;
        background: #262730;
        color: #ff4b4b;
        margin-right: 5px;
    }
    
    /* 금액 강조 */
    .price-val { font-size: 1.1rem; font-weight: 700; color: #ff4b4b; }
    .unit-label { font-size: 0.8rem; color: #888; margin-left: 2px; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 유틸리티 함수 (파싱 & 변환)
# ==========================================

import sqlite3

@st.cache_data
def load_db_data(db_path):
    """SQLite DB에서 전체 매물 데이터를 로드합니다."""
    try:
        conn = sqlite3.connect(db_path)
        # 컬럼명으로 접근 가능하도록 Row 객체 사용
        conn.row_factory = sqlite3.Row
        df = pd.read_sql_query("SELECT * FROM nemo_stores", conn)
        conn.close()
        
        # 문자열로 저장된 JSON 리스트 필드들을 파이썬 리스트로 변환
        # DB 컬럼명 확인 결과: snake_case
        json_cols = ['small_photo_urls', 'origin_photo_urls']
        for col in json_cols:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) and x.startswith('[') else (x if x else []))
        
        return df
    except Exception as e:
        st.error(f"DB 로딩 중 오류 발생: {e}")
        return pd.DataFrame()

@st.cache_data
def load_html_from_md(file_path):
    """MD 파일에서 분석용 HTML 블록만 추출합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        json_end_marker = "위 정보에 매핑되는 데이터는 다음 html에 들어 있습니다"
        if json_end_marker in content:
            html_part = content.split(json_end_marker)[-1].strip()
            html_start = html_part.find('<div')
            if html_start != -1:
                return html_part[html_start:]
    except:
        pass
    return ""

def convert_price(val, to_unit='만'):
    """만원 단위 = JSON값 / 10, KRW(원) = JSON값 * 1,000"""
    if pd.isna(val) or val is None:
        return 0
    
    if to_unit == '원':
        return int(val * 1000)
    else: # '만'
        return val / 10

def format_price_display(val, unit='만'):
    """금액을 읽기 좋은 형식으로 포맷팅"""
    if val == 0: return "-"
    if unit == '만':
        if val >= 10000:
            억 = int(val // 10000)
            만 = int(val % 10000)
            return f"{억}억 {만:,}만" if 만 > 0 else f"{억}억"
        return f"{val:,.0f}만"
    else:
        return f"₩{val:,.0f}"

def extract_agent_comment(html_content):
    """HTML에서 중개사 코멘트를 추출합니다."""
    if not html_content: return ""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        comment_div = soup.find('div', class_='comment')
        if comment_div:
            p_tag = comment_div.find('p')
            return p_tag.get_text(separator="\n").strip() if p_tag else ""
    except:
        pass
    return ""

# ==========================================
# 3. 데이터 로드 및 필터
# ==========================================

import os

# DB 및 MD 경로 (배포 환경을 위한 상대 경로 설정)
current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, 'nemo_store.db')
md_path = os.path.join(current_dir, 'data_json_html.md')

# 데이터 실행
raw_df = load_db_data(db_path)
html_data = load_html_from_md(md_path)
base_comment = extract_agent_comment(html_data)

if raw_df.empty:
    st.warning("DB에서 매물 데이터를 가져오지 못했습니다. 경로를 확인해 주세요.")
    st.stop()

st.sidebar.title("NEMO DASHBOARD")
st.sidebar.markdown("---")

# 단위 선택 토글
unit_choice = st.sidebar.radio("💰 금액 단위 선택", ["만원", "원"])
target_unit = '원' if unit_choice == "원" else '만'

# 데이터 전처리 (단위 반영)
df = raw_df.copy()
# DB 컬럼명: snake_case
price_cols = ['deposit', 'monthly_rent', 'premium', 'maintenance_fee', 'sale']
for col in price_cols:
    if col in df.columns:
        df[f'{col}_disp'] = df[col].apply(lambda x: convert_price(x, target_unit))

# 날짜 변환
if 'created_date_utc' in df.columns:
    df['regDate'] = pd.to_datetime(df['created_date_utc']).dt.date

# 필터 구성
with st.sidebar.expander("📂 업종 및 위치", expanded=True):
    col_ind = 'business_middle_code_name'
    if col_ind in df.columns:
        industries = ["전체"] + sorted(df[col_ind].unique().tolist())
        sel_ind = st.selectbox("업종(중)", industries)
    else:
        sel_ind = "전체"
    
    search_station = st.text_input("🚉 역 주변 검색", placeholder="예: 이촌역")

with st.sidebar.expander("💸 가격 범위", expanded=True):
    hide_premium_closed = False
    if 'is_premium_closed' in df.columns:
        hide_premium_closed = st.checkbox("권리금 비공개 매물 제외")
    
    # 대표 가격 필터 (월세 기준)
    if 'monthly_rent_disp' in df.columns:
        min_rent = float(df['monthly_rent_disp'].min())
        max_rent = float(df['monthly_rent_disp'].max())
        
        if min_rent < max_rent:
            rent_range = st.slider(f"월세 범위 ({unit_choice})", min_rent, max_rent, (min_rent, max_rent))
        else:
            st.info(f"선택 가능한 월세가 단일 값({format_price_display(min_rent, target_unit)})입니다.")
            rent_range = (min_rent, max_rent)
    else:
        rent_range = (0, 0)

# 필터링 로직
f_df = df.copy()
if sel_ind != "전체": f_df = f_df[f_df['business_middle_code_name'] == sel_ind]
if search_station and 'near_subway_station' in f_df.columns: 
    f_df = f_df[f_df['near_subway_station'].str.contains(search_station, na=False)]
if hide_premium_closed and 'is_premium_closed' in f_df.columns:
    f_df = f_df[f_df['is_premium_closed'] == False]
    
if 'monthly_rent_disp' in f_df.columns:
    f_df = f_df[(f_df['monthly_rent_disp'] >= rent_range[0]) & (f_df['monthly_rent_disp'] <= rent_range[1])]

# ==========================================
# 4. 메인 대시보드
# ==========================================

st.title("🏙️ Nemo Store Real Estate Dashboard")
st.markdown("시니어 엔지니어가 설계한 고도화된 매물 분석 시스템 (DB Ver.)")

# KPI 영역
st.subheader("📌 Key Metrics")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric("추천 매물", f"{len(f_df)} 건")
with kpi2:
    if not f_df.empty and 'monthly_rent_disp' in f_df.columns:
        val = f_df['monthly_rent_disp'].median()
        st.metric(f"월세 중앙값 ({unit_choice})", format_price_display(val, target_unit))
    else:
        st.metric(f"월세 중앙값 ({unit_choice})", "-")
with kpi3:
    if not f_df.empty and 'deposit_disp' in f_df.columns:
        val = f_df['deposit_disp'].median()
        st.metric(f"보증금 중앙값 ({target_unit}단위)", format_price_display(val, target_unit))
    else:
        st.metric(f"보증금 중앙값 ({target_unit}단위)", "-")
with kpi4:
    if not f_df.empty and 'size' in f_df.columns:
        val = f_df['size'].mean()
        st.metric("평균 면적 (㎡)", f"{val:.1f} ㎡")
    else:
        st.metric("평균 면적 (㎡)", "-")

# 시각화 영역
st.markdown("---")
st.subheader("📊 시장 데이터 시각화")
if not f_df.empty:
    v_col1, v_col2 = st.columns([2, 1])
    
    with v_col1:
        # 산점도: 보증금 vs 월세
        fig_scatter = px.scatter(
            f_df, x="deposit_disp", y="monthly_rent_disp",
            size="size", color="business_middle_code_name",
            hover_name="title",
            labels={"deposit_disp": f"보증금 ({unit_choice})", "monthly_rent_disp": f"월세 ({unit_choice})"},
            title="보증금 vs 월세 분포 (원 크기=면적)",
            template="plotly_dark",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    with v_col2:
        # 권리금 히스토그램
        fig_hist = px.histogram(
            f_df, x="premium_disp",
            nbins=15,
            title=f"권리금 분포 ({unit_choice})",
            template="plotly_dark",
            color_discrete_sequence=['#ff4b4b']
        )
        st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.info("시각화할 데이터가 없습니다.")

# 시계열 추이
st.subheader("🕒 매물 등록 현황")
if 'regDate' in f_df.columns and not f_df.empty:
    trend = f_df.groupby('regDate').size().reset_index(name='count')
    fig_trend = px.line(
        trend, x='regDate', y='count',
        title="날짜별 매물 등록 추이",
        template="plotly_dark",
        markers=True
    )
    fig_trend.update_traces(line_color='#00d1b2')
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("매물 등록 추이를 시각화할 데이터가 없습니다.")

# ==========================================
# 5. 데이터 테이블 및 상세 정보
# ==========================================
st.markdown("---")
st.subheader("📋 매물 검색 결과")

if not f_df.empty:
    # 테이블용 데이터 정제
    cols_to_use = ['title', 'business_middle_code_name', 'size', 'floor', 'deposit_disp', 'monthly_rent_disp', 'premium_disp', 'maintenance_fee_disp', 'near_subway_station', 'regDate']
    display_cols = [c for c in cols_to_use if c in f_df.columns]
    table_df = f_df[display_cols].copy()
    
    # 가독성을 위해 테이블 내 수치 포맷팅
    price_map = {'deposit_disp': '보증금', 'monthly_rent_disp': '월세', 'premium_disp': '권리금', 'maintenance_fee_disp': '관리비'}
    for raw, kor in price_map.items():
        if raw in table_df.columns:
            table_df[kor] = table_df[raw].apply(lambda x: format_price_display(x, target_unit))
            table_df.drop(columns=[raw], inplace=True)
    
    # 나머지 컬럼명 한글화
    column_rename_map = {
        'title': '제목',
        'business_middle_code_name': '업종',
        'size': '면적(㎡)',
        'floor': '층',
        'near_subway_station': '역정보',
        'regDate': '등록일'
    }
    table_df.rename(columns={k: v for k, v in column_rename_map.items() if k in table_df.columns}, inplace=True)

    st.dataframe(table_df, use_container_width=True)
    
    # 상세 정보 선택
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🔍 상세 매물 정보")
    selected_title = st.selectbox("상세 정보를 볼 매물을 선택하세요", f_df['title'].unique())
    item = f_df[f_df['title'] == selected_title].iloc[0]
    
    d_col1, d_col2 = st.columns([1, 1])
    
    with d_col1:
        st.markdown(f"### {item['title']}")
        st.markdown(f"<span class='badge'>{item.get('price_type_name', '임대')}</span> <span class='badge'>{item.get('business_middle_code_name', '기타')}</span>", unsafe_allow_html=True)
        
        # 갤러리
        cols = st.columns(3)
        photos = item.get('small_photo_urls', [])
        if not photos and 'preview_photo_url' in item: photos = [item['preview_photo_url']]
        if not photos: photos = []
        
        for idx, url in enumerate(photos[:6]): # 최대 6개
            with cols[idx % 3]:
                st.image(url, use_column_width=True)
                
    with d_col2:
        st.info("💡 **매물 수치를 확인하세요**")
        p_c1, p_c2 = st.columns(2)
        with p_c1:
            st.metric("보증금", format_price_display(item.get('deposit_disp', 0), target_unit))
            st.metric("월세", format_price_display(item.get('monthly_rent_disp', 0), target_unit))
        with p_c2:
            st.metric("권리금", format_price_display(item.get('premium_disp', 0), target_unit))
            st.metric("관리비", format_price_display(item.get('maintenance_fee_disp', 0), target_unit))
            
        st.write(f"**📍 위치:** {item.get('near_subway_station', '정보 없음')}")
        st.write(f"**📐 면적:** {item.get('size', '-')} ㎡ ({item.get('floor', '-')}층)")
        
        st.markdown("**✍️ 중개사 코멘트**")
        # 특정 ID(동부이촌동)만 MD 파일 코멘트와 매핑, 그 외에는 기본 또는 비움
        if "이촌" in item['title']:
            st.write(base_comment if base_comment else "상세 코멘트 준비 중입니다.")
        else:
            st.write("중개사 상세 설명이 등록되지 않은 매물입니다.")
else:
    st.info("필터링된 결과가 없습니다.")
