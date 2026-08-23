import io
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
import pandas as pd
from pypdf import PdfReader
import streamlit as st
import streamlit.components.v1 as components

# ==========================================
# 1. 페이지 기본 설정 및 모바일 UI 최적화 CSS (웨일 브라우저 아이콘 깨짐 방지 적용)
# ==========================================
st.set_page_config(
    page_title="CLC AI영업툴 (Pro)",
    page_icon="💼",
    layout="wide"
)

# Streamlit Cloud 배지, 헤더, 푸터 완전 은닉 스크립트
components.html("""
<script>
    function removeStreamlitBadgesOnly() {
        try {
            const parentDoc = window.parent.document;
            const selectors = [
                'footer',
                '#MainMenu',
                '[data-testid="stStatusWidget"]',
                '[data-testid="stDecoration"]',
                '[class*="viewerBadge"]',
                '[class*="stAppDeployButton"]',
                'div[class*="styles_viewerBadge"]',
                'div[class*="ViewerBadge"]',
                'button[title="View app in Streamlit Community Cloud"]'
            ];
            selectors.forEach(selector => {
                const elements = parentDoc.querySelectorAll(selector);
                elements.forEach(el => {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                });
            });
        } catch (e) { console.log(e); }
    }
    setInterval(removeStreamlitBadgesOnly, 300);
</script>
""", height=0, width=0)

st.markdown("""
<style>
    footer {display: none !important; visibility: hidden !important;}
    #MainMenu {display: none !important;}
    .stAppDeployButton {display: none !important;}
    div[data-testid="stDecoration"] {display: none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    
    div[data-testid="stHeader"] {
        background-color: transparent !important;
        z-index: 100 !important;
    }
    
    /* 네이버 웨일 등 모바일 웹뷰에서 Material Icon 텍스트 깨짐 현상 완전 차단 및 깔끔한 메뉴 텍스트 대체 */
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"] {
        color: transparent !important;
        background-color: #003b7a !important;
        border-radius: 8px !important;
        padding: 6px 12px !important;
        margin-top: 5px !important;
        margin-left: 5px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2) !important;
    }
    
    [data-testid="collapsedControl"] *, [data-testid="stSidebarCollapseButton"] * {
        color: transparent !important;
    }
    
    [data-testid="collapsedControl"]::before {
        content: "≡ 메뉴" !important;
        color: #ffffff !important;
        font-size: 13px !important;
        font-weight: bold !important;
        visibility: visible !important;
        position: absolute;
        left: 8px;
    }
    
    [data-testid="stSidebarCollapseButton"]::before {
        content: "✕ 닫기" !important;
        color: #ffffff !important;
        font-size: 13px !important;
        font-weight: bold !important;
        visibility: visible !important;
        position: absolute;
        left: 8px;
    }

    .main .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 2rem !important;
    }
    
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
        h1 { font-size: 1.4rem !important; }
        div[data-testid="stMarkdownContainer"] table { font-size: 12px !important; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. [LOCK] 카카오 지도 API 실시간 매장 검색 함수
# ==========================================
def search_kakao_local_stores(query_text):
    """카카오 지도 REST API를 활용하여 실시간 건물 내 점포 리스트 추출"""
    kakao_key = st.secrets.get("KAKAO_REST_API_KEY", "4b59cf7aff54ff6e7b451b761d5befaf").strip()
    if not kakao_key:
        return None
    
    clean_query = query_text
    for stop_word in ["입점 매장", "입점매장", "매장 리스트", "점포 리스트", "상권", "특징", "전략", "분석해줘", "알려줘", "3일 체험", "3일체험", "추천", "침투", "포진 업종", "골든타임", "네이버 지도 주소"]:
        clean_query = clean_query.replace(stop_word, "")
    clean_query = clean_query.strip()
    
    search_keyword = clean_query if clean_query else query_text.split()[0]

    try:
        encoded_query = urllib.parse.quote(search_keyword)
        url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={encoded_query}&size=15"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"KakaoAK {kakao_key}")
        
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            documents = res_data.get('documents', [])
            
            if not documents and len(query_text.split()) > 0:
                first_word = query_text.split()[0]
                encoded_fb = urllib.parse.quote(first_word)
                url_fb = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={encoded_fb}&size=15"
                req_fb = urllib.request.Request(url_fb)
                req_fb.add_header("Authorization", f"KakaoAK {kakao_key}")
                with urllib.request.urlopen(req_fb) as res_fb_obj:
                    res_fb_data = json.loads(res_fb_obj.read().decode('utf-8'))
                    documents = res_fb_data.get('documents', [])

            stores_summary = []
            for doc in documents:
                place_name = doc.get('place_name', '')
                category = doc.get('category_name', '')
                address = doc.get('road_address_name') or doc.get('address_name', '')
                phone = doc.get('phone', '')
                place_url = doc.get('place_url', '')
                
                stores_summary.append({
                    "상호명": place_name,
                    "업종": category.split(">")[-1].strip() if ">" in category else category,
                    "주소": address,
                    "전화번호": phone if phone else "정보없음",
                    "카카오지도URL": place_url
                })
            return stores_summary
    except Exception as e:
        return None

# ==========================================
# 3. [Dynamic Proposal Engine] 전 제품 맞춤형 고품격 제안서 이미지 생성 엔진
# ==========================================
def generate_general_proposal_card(store_name, product_name, industry, summary_text, price_text):
    """
    어떤 제품이나 업체명이 들어오든 RAG 학습 단가표 및 스펙을 반영하여 
    참고 이미지 스타일의 고품격 제안서 카드(.png)를 동적으로 렌더링합니다.
    """
    FONT_PATH = "NanumGothic-Bold.ttf"
    if not os.path.exists(FONT_PATH):
        try:
            urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf", FONT_PATH)
        except:
            pass

    width, height = 1200, 1600
    img = Image.new('RGB', (width, height), color='#f8fafc')
    draw = ImageDraw.Draw(img)

    try:
        f_title = ImageFont.truetype(FONT_PATH, 42)
        f_sub = ImageFont.truetype(FONT_PATH, 26)
        f_box_t = ImageFont.truetype(FONT_PATH, 28)
        f_box_b = ImageFont.truetype(FONT_PATH, 20)
        f_price = ImageFont.truetype(FONT_PATH, 32)
        f_foot = ImageFont.truetype(FONT_PATH, 18)
    except:
        f_title = f_sub = f_box_t = f_box_b = f_price = f_foot = ImageFont.load_default()

    # Header Section
    draw.rectangle([(0, 0), (width, 220)], fill='#003b7a')
    draw.rectangle([(0, 210), (width, 220)], fill='#00a3e0')
    draw.text((60, 40), "🦅 CESCO OFFICIAL PROPOSAL", fill='#38bdf8', font=ImageFont.truetype(FONT_PATH, 24))
    draw.text((60, 90), f"'{store_name}' ({industry}) 맞춤형 제안서", fill='#ffffff', font=f_title)
    draw.text((60, 155), f"추천 제품: {product_name}", fill='#cbd5e1', font=f_sub)

    # Section 1: Core Summary / Need
    draw.rounded_rectangle([(60, 260), (1140, 520)], radius=15, fill='#ffffff', outline='#cbd5e1', width=2)
    draw.text((100, 300), "📌 현장 진단 및 핵심 가치 요약", fill='#003b7a', font=f_box_t)
    sum_lines = [summary_text[i:i+45] for i in range(0, len(summary_text), 45)]
    sy = 360
    for line in sum_lines[:4]:
        draw.text((100, sy), line, fill='#334155', font=f_box_b)
        sy += 32

    # Section 2: Product & Pricing
    draw.rounded_rectangle([(60, 560), (1140, 920)], radius=15, fill='#eff6ff', outline='#bfdbfe', width=2)
    draw.text((100, 600), f"✨ 제안 제품: {product_name}", fill='#0284c7', font=f_box_t)
    draw.text((100, 660), "• 세스코 전문 케어 요원의 정기적인 관리 서비스", fill='#1e293b', font=f_box_b)
    draw.text((100, 705), "• 100% 본사 지원 3일 무상 체험 서비스 제공", fill='#1e293b', font=f_box_b)
    draw.text((100, 775), f"💰 제안 견적 / 단가: {price_text}", fill='#003b7a', font=f_price)

    # Section 3: Branding & CTA
    draw.rounded_rectangle([(60, 960), (1140, 1260)], radius=15, fill='#0f172a', outline='#38bdf8', width=2)
    draw.text((100, 1010), "🎁 특별 프로모션 혜택", fill='#38bdf8', font=f_box_t)
    draw.text((100, 1070), "• 설치비 전액 면제 및 3일 무료 체험 후 결정", fill='#ffffff', font=f_box_b)
    draw.text((100, 1115), "• “깨끗하고 안전한 공간은 고객의 발걸음을 머물게 합니다.”", fill='#94a3b8', font=f_box_b)

    # Footer
    draw.rectangle([(0, height - 90), (width, height)], fill='#020617')
    draw.text((60, height - 55), "CESCO 경기서북부 담당 플래너 | www.cesco.co.kr | Innovation for Tomorrow", fill='#94a3b8', font=f_foot)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# ==========================================
# 4. [LOCK - CLC AI영업툴] 고도화된 페르소나 및 시스템 지침 (제안서 자동 이미지 생성 파싱 규칙 포함)
# ==========================================
CLC_AI_SALES_TOOL_INSTRUCTION = """
당신은 현장 B2C 및 소상공인 영업 전문가인 'CLC AI영업툴'입니다. 
주로 소상공인 대표 혹은 가정의 가장 및 결정권자를 상대로 단기 성과 구축과 계약 및 매출 증대를 이끌어내는 것이 주된 목표입니다.

[소통 및 답변 원칙]
1. 친절하면서도 전문적이고, 어려운 기술 용어보다는 쉬운 일상적 비유를 사용하여 소통합니다.
2. 자료 요청(제안서, 스크립트 등) 시, **항상 핵심 가치를 먼저 두괄식으로 제시**합니다.
3. **예상되는 고객의 거절/질문과 그에 대한 명확한 답변**을 반드시 포함해 주세요.
4. 답변 길이는 일반적으로 핵심만 간결하게 요약하며, 복잡한 내용은 표나 불렛 포인트로 정리합니다.
5. 절대 고객을 가르치려 들거나 강압적인 어투를 사용하지 않습니다.

[세스코 핵심 8대 제품 라인업 및 단가표 참조]
학습된 RAG 문서를 최우선으로 참조하여 가격과 스펙을 정확히 반영하세요.

[제안서 작성 요청 시 필수 규칙]
플래너가 '[어느] 업체에 [제품종류] 제안서를 만들어줘'라고 요청하면, 
1. 카카오톡 전송용 텍스트 제안서(400~500자 내외, 고객 니즈 분석 및 솔루션 포함)를 작성합니다.
2. 답변의 맨 마지막 줄에 아래 JSON 블록을 반드시 포함해 주세요. (단, 이미지를 만들어달라고 명시적으로 요청할 때만 `generate_image: true`로 설정하세요)
```json
{
  "generate_image": true,
  "store_name": "업체명",
  "product_name": "제품명",
  "industry": "업종",
  "summary_text": "핵심 진단 및 가치 요약",
  "price_text": "단가표 기반 가격"
}
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
