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
# 1. 페이지 기본 설정 및 모바일 UI 최적화 CSS
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
    
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"] {
        display: flex !important;
        visibility: visible !important;
        color: #ffffff !important;
        background-color: #003b7a !important;
        border-radius: 8px !important;
        padding: 4px !important;
        margin-top: 5px !important;
        margin-left: 5px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2) !important;
    }
    
    [data-testid="collapsedControl"] button, [data-testid="stSidebarCollapseButton"] button {
        color: #ffffff !important;
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
# 3. [AIRZENIC INFOGRAPHIC PRO] 세스코 에어제닉 전용 고품격 인포그래픽 렌더링 엔진
# ==========================================
def generate_airzenic_infographic_card():
    FONT_PATH = "NanumGothic-Bold.ttf"
    if not os.path.exists(FONT_PATH):
        try:
            urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf", FONT_PATH)
        except:
            pass

    width, height = 1200, 2100
    img = Image.new('RGB', (width, height), color='#f8fafc')
    draw = ImageDraw.Draw(img)

    try:
        f_header_t = ImageFont.truetype(FONT_PATH, 38)
        f_header_s = ImageFont.truetype(FONT_PATH, 24)
        f_section_t = ImageFont.truetype(FONT_PATH, 28)
        f_card_t = ImageFont.truetype(FONT_PATH, 22)
        f_card_d = ImageFont.truetype(FONT_PATH, 17)
        f_price = ImageFont.truetype(FONT_PATH, 26)
        f_footer = ImageFont.truetype(FONT_PATH, 18)
    except:
        f_header_t = f_header_s = f_section_t = f_card_t = f_card_d = f_price = f_footer = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 180)], fill='#003b7a')
    draw.rectangle([(0, 170), (width, 180)], fill='#00a3e0')
    
    draw.text((60, 35), "🦅 CESCO AIRZENIC PROPOSAL", fill='#38bdf8', font=ImageFont.truetype(FONT_PATH, 22))
    draw.text((60, 70), "악취는 없애고 순간의 향기로 공간을 채우는, 세스코 에어제닉!", fill='#ffffff', font=f_header_t)
    draw.text((60, 125), "우리 집 / 사무실 공간 공기, 지금 어떤가요?", fill='#cbd5e1', font=f_header_s)

    draw.text((60, 215), "🚨 이런 공간의 고민, 세스코가 해결합니다", fill='#0f172a', font=f_section_t)
    
    problems = [
        ("화장실의 끈질긴 암모니아 냄새", "배수구와 변기에서 발생하는 불쾌한 냄새가 상쾌함을 해칩니다."),
        ("반려동물의 배변 냄새 및 체취", "반려동물과 함께하는 공간에 배인 냄새와 체취가 고민입니다."),
        ("쓰레기통 주변의 부패한 악취", "생활 쓰레기에서 나오는 부패한 냄새가 공기를 무겁게 만듭니다."),
        ("담배 냄새 잔류", "환풍기를 틀어도 사라지지 않는 담배 냄새가 실내에 배어 있습니다."),
        ("밀폐된 공간의 답답하고 칙칙한 공기", "환기가 어려운 회의실이나 작은 방의 공기가 답답합니다."),
        ("방향제 스프레이의 인위적인 잔향", "뿌릴 때만 잠시 가려질 뿐, 인위적인 향이 남아 불쾌합니다.")
    ]

    p_w, p_h = 525, 120
    p_start_y = 265
    for idx, (p_title, p_desc) in enumerate(problems):
        col = idx % 2
        row = idx // 2
        px = 60 if col == 0 else 615
        py = p_start_y + row * (p_h + 15)
        
        draw.rounded_rectangle([(px, py), (px + p_w, py + p_h)], radius=12, fill='#ffffff', outline='#cbd5e1', width=2)
        draw.text((px + 20, py + 20), f"• {p_title}", fill='#003b7a', font=f_card_t)
        
        desc_lines = [p_desc[i:i+30] for i in range(0, len(p_desc), 30)]
        dy = py + 55
        for line in desc_lines:
            draw.text((px + 20, dy), line, fill='#475569', font=f_card_d)
            dy += 22

    s_start_y = 715
    draw.text((60, s_start_y), "✨ CESCO Airzenic 4-Step Solution", fill='#0f172a', font=f_section_t)

    solutions = [
        ("POINT 01", "지능형 센서 감지", "Cesco Airzenic의 센서가 사람의 움직임을 실시간으로 감지하여 자동으로 탈취/발향합니다."),
        ("POINT 02", "순간 발향 및 강력 탈취", "즉각적으로 미세한 탈취제와 향기를 분사하여 불쾌한 냄새를 제거하고 공간을 향기로 채웁니다."),
        ("POINT 03", "Cesco 프리미엄 향기 포트폴리오", "전문 조향사가 설계한 다양한 프리미엄 향기 중 공간과 선호도에 맞춰 선택 가능합니다."),
        ("POINT 04", "간편한 설치 및 리필 교체", "벽걸이/스탠드형으로 어디든 설치 가능하며, 누구나 쉽게 리필을 교체할 수 있습니다.")
    ]

    s_y = s_start_y + 50
    for step, s_name, s_desc in solutions:
        draw.rounded_rectangle([(60, s_y), (1140, s_y + 85)], radius=12, fill='#eff6ff', outline='#bfdbfe', width=2)
        draw.text((85, s_y + 18), step, fill='#0284c7', font=ImageFont.truetype(FONT_PATH, 16))
        draw.text((85, s_y + 42), s_name, fill='#0f172a', font=f_card_t)
        draw.text((360, s_y + 32), s_desc, fill='#334155', font=f_card_d)
        s_y += 100

    c_start_y = 1175
    draw.text((60, c_start_y), "📦 우리 집 / 사무실 공간에 맞는 서비스 선택", fill='#0f172a', font=f_section_t)

    box_w = 525
    box_h = 180
    
    bx_l = 60
    by_l = c_start_y + 50
    draw.rounded_rectangle([(bx_l, by_l), (bx_l + box_w, by_l + box_h)], radius=15, fill='#ffffff', outline='#0284c7', width=3)
    draw.text((bx_l + 30, by_l + 25), "👑 에어제닉 프리미엄형", fill='#003b7a', font=f_card_t)
    draw.text((bx_l + 30, by_l + 65), "스마트 센서 및 다양한 향기 옵션 제공", fill='#475569', font=f_card_d)
    draw.text((bx_l + 30, by_l + 105), "250,000원", fill='#0284c7', font=f_price)
    draw.text((bx_l + 30, by_l + 145), "※ 향기 카트리지 별도 구매", fill='#94a3b8', font=f_footer)

    bx_r = 615
    by_r = c_start_y + 50
    draw.rounded_rectangle([(bx_r, by_r), (bx_r + box_w, by_r + box_h)], radius=15, fill='#ffffff', outline='#cbd5e1', width=2)
    draw.text((bx_r + 30, by_r + 25), "📦 에어제닉 스탠다드형", fill='#0f172a', font=f_card_t)
    draw.text((bx_r + 30, by_r + 65), "고정된 향기 설정, 센서 미포함 보급형", fill='#475569', font=f_card_d)
    draw.text((bx_r + 30, by_r + 105), "190,000원", fill='#334155', font=f_price)

    ui_y = 1435
    draw.rounded_rectangle([(60, ui_y), (1140, ui_y + 130)], radius=15, fill='#0f172a', outline='#38bdf8', width=2)
    draw.ellipse([(95, ui_y + 25), (95 + 80, ui_y + 25 + 80)], fill='#38bdf8')
    draw.text((115, ui_y + 52), "황태", fill='#0f172a', font=ImageFont.truetype(FONT_PATH, 22))
    draw.text((195, ui_y + 32), "황태 팀장", fill='#ffffff', font=f_card_t)
    draw.text((195, ui_y + 72), "14시간 전 • 프로필 업데이트", fill='#94a3b8', font=f_footer)
    draw.text((1000, ui_y + 52), "❤️ 💬", fill='#38bdf8', font=f_card_t)

    cta_y = 1625
    draw.rounded_rectangle([(60, cta_y), (1140, cta_y + 150)], radius=15, fill='#003b7a', outline='#38bdf8', width=3)
    draw.text((95, cta_y + 35), "📞 지금 바로 세스코 에어제닉 3일 무상 체험을 신청하세요!", fill='#ffffff', font=f_card_t)
    draw.text((95, cta_y + 80), "“깨끗하고 향기로운 공간은 고객의 발걸음을 머물게 합니다.”", fill='#38bdf8', font=f_header_s)

    draw.rectangle([(0, height - 80), (width, height)], fill='#020617')
    draw.text((60, height - 50), "CESCO 경기서북부 담당 플래너 | www.cesco.co.kr | Innovation for Tomorrow", fill='#94a3b8', font=f_footer)
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# ==========================================
# 4. [LOCK - CLC AI영업툴] 고도화된 페르소나 및 시스템 지침
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

[세스코 핵심 8대 제품 라인업]
1. 공기청정기: '판테온' (360도 필터, CA인증, CO2/PM1.0 센서)
2. 공기살균기: '센스미' (UV-C 파워 램프, 부유 바이러스·세균 99.9% 제거)
3. 탱크형 정수기: '더슬림', '더블', '더맥스' (업소용 대용량)
4. 직수 정수기: '살균온', '살균온 얼음정수기' (UVnano 살균)
5. 비데: '파워방수비데', '살균방수비데', '듀얼비데', '올인원비데' (IPX6 방수)
6. 향기 제품: '에어퍼퓸200', '에어제닉' (자동 향기 분사 및 악취 분해)
7. 화장실 케어 제품: '프레쉬제닉', '핸드제닉', '새니제닉'
8. 날벌레 방지 제품: '에어커튼', '포충등'

[플래너 상권 및 영업 전략 수립 규칙]
상권이나 영업 전략을 물어보면 아래 4가지 요소를 중심으로 실전적인 동선과 화법을 구성하세요.
1. 보유 장비 맞춤 타겟 업종 선정 (예: 뷰티숍, 로비형 카페 등)
2. 구체적 상권 동선 및 층별 침투 전략
3. 사장님을 사로잡는 킬러 오프닝 피칭 화법 및 무상 체험 유도
4. 3일 무상 체험 후 유료 계약(Closing) 콜 노하우
"""

# ==========================================
# 5. 데이터 I/O 및 누적 문서 학습 (RAG) 함수
# ==========================================
KNOWLEDGE_BASE_PATH = "cesco_knowledge_base.txt"
KNOWLEDGE_FILES_PATH = "cesco_knowledge_files_list.txt"
SALES_LOG_PATH = "sales_activity_log.csv"
EQUIPMENT_LOG_PATH = "team_equipment_inventory.csv"

def load_knowledge_data():
    context = ""
    file_list_str = ""
    if os.path.exists(KNOWLEDGE_BASE_PATH):
        with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
            context = f.read()
    if os.path.exists(KNOWLEDGE_FILES_PATH):
        with open(KNOWLEDGE_FILES_PATH, "r", encoding="utf-8") as f:
            file_list_str = f.read()
    return context, file_list_str

def add_file_to_cumulative_knowledge(uploaded_file):
    extracted_text = ""
    filename = uploaded_file.name
    
    if filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file, sheet_name=0)
        df = df.dropna(how="all")
        extracted_text = df.to_markdown(index=False)
    elif filename.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
        df = df.dropna(how="all")
        extracted_text = df.to_markdown(index=False)
    elif filename.endswith('.pdf'):
        reader = PdfReader(uploaded_file)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"

    if extracted_text:
        current_context, current_files = load_knowledge_data()
        if filename in current_files.split(","):
            return False, f"⚠️ `{filename}` 문서는 이미 학습되어 있습니다."

        new_context = current_context + f"\n\n--- [학습 문서 시작: {filename}] ---\n" + extracted_text + f"\n--- [학습 문서 끝: {filename}] ---\n"
        with open(KNOWLEDGE_BASE_PATH, "w", encoding="utf-8") as f:
            f.write(new_context)
            
        new_files_list = (current_files + "," + filename).strip(",")
        with open(KNOWLEDGE_FILES_PATH, "w", encoding="utf-8") as f:
            f.write(new_files_list)
            
        return True, f"✅ `{filename}` 문서 학습 완료!"
    return False, f"⚠️ 텍스트를 추출할 수 없습니다."

def delete_all_knowledge_data():
    if os.path.exists(KNOWLEDGE_BASE_PATH):
        os.remove(KNOWLEDGE_BASE_PATH)
    if os.path.exists(KNOWLEDGE_FILES_PATH):
        os.remove(KNOWLEDGE_FILES_PATH)

knowledge_context, learned_files_str = load_knowledge_data()
learned_files_list = [f for f in learned_files_str.split(",") if f]

def save_sales_log(planner_name, client_name, proposed_deal, equipment_status, equipment_item, reaction, memo, install_date=None):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_date_str = install_date if install_date else datetime.now().strftime("%Y-%m-%d")
    
    feedback_due = "-"
    if equipment_status == "설치 완료":
        try:
            inst_dt = datetime.strptime(today_date_str, "%Y-%m-%d")
            feedback_due = (inst_dt + timedelta(days=3)).strftime("%Y-%m-%d")
        except:
            feedback_due = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    new_data = pd.DataFrame([{
        "작성일시": now_str,
        "담당플래너": planner_name,
        "고객/매장명": client_name,
        "제안서비스/견적가": proposed_deal,
        "체험장비설치": equipment_status,
        "설치장비품목": equipment_item if equipment_status == "설치 완료" else "-",
        "설치일자": today_date_str if equipment_status == "설치 완료" else "-",
        "3일체험_피드백예정일": feedback_due,
        "고객반응/상태": reaction,
        "영업메모": memo
    }])
    
    if os.path.exists(SALES_LOG_PATH):
        old_df = pd.read_csv(SALES_LOG_PATH)
        if "담당팀원" in old_df.columns:
            old_df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
        for col in ["설치일자", "3일체험_피드백예정일"]:
            if col not in old_df.columns:
                old_df[col] = "-"
        df = pd.concat([old_df, new_data], ignore_index=True)
    else:
        df = new_data
    df.to_csv(SALES_LOG_PATH, index=False, encoding="utf-8-sig")

def load_equipment_inventory():
    if os.path.exists(EQUIPMENT_LOG_PATH):
        df = pd.read_csv(EQUIPMENT_LOG_PATH)
        if "담당팀원" in df.columns:
            df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
        if "보유대수" in df.columns and "전체 보유대수" not in df.columns:
            df.rename(columns={"보유대수": "전체 보유대수"}, inplace=True)
        return df
    default_df = pd.DataFrame([
        {"담당플래너": "홍길동", "전체 보유대수": 5},
        {"담당플래너": "김철수", "전체 보유대수": 3},
        {"담당플래너": "이영희", "전체 보유대수": 4}
    ])
    default_df.to_csv(EQUIPMENT_LOG_PATH, index=False, encoding="utf-8-sig")
    return default_df

def save_equipment_inventory(df):
    df.to_csv(EQUIPMENT_LOG_PATH, index=False, encoding="utf-8-sig")

# ==========================================
# 6. 사이드바 UI
# ==========================================
with st.sidebar:
    st.header("⚙️ CLC AI영업툴 센터")
    st.success("💼 **CLC AI영업툴 가동 중**")
    st.caption("소상공인 및 가정 B2C 영업 성공을 위한 전문 비서 시스템입니다.")

    st.divider()
    st.subheader("📚 현재 AI 학습 문서 상태")
    if learned_files_list:
        st.success(f"**누적 학습 완료 ({len(learned_files_list)}건):**")
        st.text_area("파일 목록 (RAG 최우선 참조)", value="\n".join(learned_files_list), height=100)
    else:
        st.info("현재 학습된 단가표 문서가 없습니다.")

    st.divider()
    st.subheader("🔑 관리자 패널")
    admin_password_secret = st.secrets.get("ADMIN_PASSWORD", "1234")
    input_pwd = st.text_input("비밀번호 입력:", type="password")
    
    if input_pwd == admin_password_secret:
        st.success("🔓 관리자 권한 활성화됨")
        
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📊 영업 대시보드", "📦 체험장비 운용/할당 설정", "📁 누적 문서 학습(PDF)"])
        
        with admin_tab1:
            st.write("📈 **실시간 영업 성과 & 3일 체험 전환 대시보드**")
            if os.path.exists(SALES_LOG_PATH):
                logs_df = pd.read_csv(SALES_LOG_PATH)
                if "담당팀원" in logs_df.columns and "담당플래너" not in logs_df.columns:
                    logs_df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
                if "설치장비품목" not in logs_df.columns:
                    logs_df["설치장비품목"] = "-"
                
                inv_df = load_equipment_inventory()
                installed_counts = logs_df[logs_df["체험장비설치"] == "설치 완료"]["담당플래너"].value_counts().reset_index()
                installed_counts.columns = ["담당플래너", "설치대수"]
                
                merged_inv = pd.merge(inv_df, installed_counts, on="담당플래너", how="left").fillna(0)
                merged_inv["설치대수"] = merged_inv["설치대수"].astype(int)
                merged_inv["현재 수중 보유대수"] = merged_inv["전체 보유대수"] - merged_inv["설치대수"]
                merged_inv["설치활동률(%)"] = (merged_inv["설치대수"] / merged_inv["전체 보유대수"] * 100).round(1)
                
                st.subheader("1️⃣ 플래너별 체험장비 보유 및 설치 현황")
                st.dataframe(merged_inv[["담당플래너", "전체 보유대수", "설치대수", "현재 수중 보유대수", "설치활동률(%)"]], use_container_width=True)
                
                st.divider()
                st.subheader("⏰ 2️⃣ [3일 체험 완료] 피드백 요청 & 계약 클로징 대상 매장")
                if "3일체험_피드백예정일" in logs_df.columns:
                    active_trials = logs_df[(logs_df["체험장비설치"] == "설치 완료") & (logs_df["3일체험_피드백예정일"] != "-")]
                    if len(active_trials) > 0:
                        disp_cols = ["담당플래너", "고객/매장명", "설치장비품목", "설치일자", "3일체험_피드백예정일", "고객반응/상태"]
                        st.dataframe(active_trials[disp_cols], use_container_width=True)
                        st.info("💡 **3일 차 피드백 추천 멘트:** '사장님! 3일간 사용해 보시니 어떠셨어요? 단골손님들이 향이나 공기 좋아졌다고 안 하시던가요? 오늘부터 할인가로 계약 확정해 드릴까요?'")
                    else:
                        st.caption("현재 3일 체험 진행 중인 매장이 없습니다.")

                st.divider()
                st.subheader("3️⃣ 체험장비 설치 후 계약 성사율 분석")
                installed_group = logs_df[logs_df["체험장비설치"] == "설치 완료"]
                non_installed_group = logs_df[logs_df["체험장비설치"] != "설치 완료"]
                
                total_installed = len(installed_group)
                installed_success = len(installed_group[installed_group["고객반응/상태"].str.contains("계약 완료", na=False)])
                installed_rate = (installed_success / total_installed * 100) if total_installed > 0 else 0.0
                
                total_non = len(non_installed_group)
                non_success = len(non_installed_group[non_installed_group["고객반응/상태"].str.contains("계약 완료", na=False)])
                non_rate = (non_success / total_non * 100) if total_non > 0 else 0.0
                
                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    st.metric(label="🎁 체험장비 설치 후 계약 성사율", value=f"{installed_rate:.1f}%", delta=f"{installed_success}건 성공 / 총 {total_installed}건")
                with m_col2:
                    st.metric(label="❌ 미설치건 계약 성사율", value=f"{non_rate:.1f}%", delta=f"{non_success}건 성공 / 총 {total_non}건")
                    
                st.divider()
                st.write("📋 **전체 영업일지 데이터 대장:**")
                st.dataframe(logs_df, use_container_width=True)
                
                logs_csv = logs_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="📥 영업일지 전체 다운로드 (.csv)",
                    data=logs_csv,
                    file_name="팀_영업활동기록대장.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("영업일지 데이터가 쌓이면 실시간 분석 대시보드가 표시됩니다.")

        with admin_tab2:
            st.write("📦 **체험장비 보유 대수 & 설치 장소/내역 종합 관리**")
            st.subheader("📍 1. 체험장비 실제 설치 매장/장소 상세 내역")
            if os.path.exists(SALES_LOG_PATH):
                logs_df = pd.read_csv(SALES_LOG_PATH)
                if "담당팀원" in logs_df.columns and "담당플래너" not in logs_df.columns:
                    logs_df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
                if "설치장비품목" not in logs_df.columns:
                    logs_df["설치장비품목"] = "-"
                
                installed_logs = logs_df[logs_df["체험장비설치"] == "설치 완료"]
                if len(installed_logs) > 0:
                    display_cols = ["작성일시", "담당플래너", "고객/매장명", "설치장비품목", "3일체험_피드백예정일", "고객반응/상태", "영업메모"]
                    disp_cols_exist = [c for c in display_cols if c in installed_logs.columns]
                    st.dataframe(installed_logs[disp_cols_exist], use_container_width=True)
                else:
                    st.info("현재 현장에 설치된 체험장비 내역이 없습니다.")
            else:
                st.info("기록된 영업일지가 없습니다.")
                
            st.divider()
            st.subheader("⚙️ 2. 플래너별 체험장비 전체 할당 대수(Total) 수정")
            current_inv = load_equipment_inventory()
            
            edited_df = st.data_editor(current_inv, num_rows="dynamic", use_container_width=True)
            if st.button("💾 전체 보유대수 수정사항 저장", use_container_width=True):
                save_equipment_inventory(edited_df)
                st.toast("✅ 플래너별 체험장비 전체 할당 대수가 업데이트되었습니다!", icon="🎉")
                st.rerun()

        with admin_tab3:
            st.subheader("📁 제품 정보 및 단가표 문서(PDF) 누적 학습")
            st.caption("여러 개의 PDF, 엑셀 파일을 업로드하면 AI가 통합하여 하나의 지식 기반으로 만듭니다.")
            
            uploaded_files = st.file_uploader("여러 제품 문서 업로드 (누적 학습)", type=["pdf", "xlsx", "csv"], accept_multiple_files=True)
            
            if uploaded_files and st.button("💾 업로드된 모든 문서를 누적 학습시키기", use_container_width=True):
                success_count = 0
                error_msgs = []
                with st.spinner("AI가 여러 문서를 정밀 분석 및 통합 학습 중입니다..."):
                    for up_file in uploaded_files:
                        success, message = add_file_to_cumulative_knowledge(up_file)
                        if success:
                            success_count += 1
                        else:
                            error_msgs.append(message)
                            
                if success_count > 0:
                    st.toast(f"✅ {success_count}건의 문서 누적 학습 완료!", icon="🎉")
                if error_msgs:
                    st.warning("\n".join(error_msgs))
                st.rerun()
                    
            if learned_files_list and st.button("🗑️ 전체 학습 데이터 초기화 (삭제)", use_container_width=True, type="secondary"):
                delete_all_knowledge_data()
                st.toast("전체 학습 데이터 초기화 완료!", icon="🧹")
                st.rerun()
    elif input_pwd:
        st.error("비밀번호 불일치")
    else:
        st.caption("관리자만 영업 대시보드 및 AI 누적 문서 학습 관리가 가능합니다.")

    st.divider()
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state["messages"] = []
        st.session_state["img_processed"] = False
        st.toast("대화 내용이 초기화되었습니다.", icon="🧹")
        st.rerun()

# ==========================================
# 7. 메인 화면 & 챗봇 인터페이스
# ==========================================
st.title("💼 CLC AI영업툴 (Pro)")

if learned_files_list:
    st.caption(f"📌 **참조 학습 문서:** `{len(learned_files_list)}건 통합` | 소상공인·가정 B2C 영업 전문가 비서")
else:
    st.caption("📌 **소상공인·가정 B2C 영업 전문가 비서 시스템**")

st.divider()

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    if "img_processed" not in st.session_state:
        st.session_state.img_processed = False

    # 현장 거절 대응 1초 반박 퀵카드 (익스팬더)
    with st.expander("⚡ **현장 사장님 거절 반응 '1초 반박' 퀵카드 (원터치)**", expanded=False):
        st.caption("현장에서 사장님이 거절 멘트를 던졌을 때 버튼을 누르면 1초 만에 최적의 반박 피칭 스크립트가 출력됩니다.")
        q_col1, q_col2, q_col3 = st.columns(3)
        quick_rejection_prompt = None
        
        with q_col1:
            if st.button("🙅 '사장님 지금 안 계세요'", use_container_width=True):
                quick_rejection_prompt = "고객/매장에서 '사장님 지금 안 계세요'라고 거절했을 때, 직원/알바생을 통해 사장님 명함을 확보하고 3일 무료 체험 쿠폰을 전달하는 1초 반박 피칭 스크립트를 안내해 주세요."
            if st.button("🙅 '기존 디퓨저/공청기 있어요'", use_container_width=True):
                quick_rejection_prompt = "사장님이 '기존에 쓰는 디퓨저나 공기청정기 있어요'라고 거절할 때, 시중 디퓨저의 악취 은폐 한계와 세스코 에어제닉/에어퍼퓸의 살균·분해 차별점을 강조하는 3일 체험 피칭 스크립트를 안내해 주세요."
        
        with q_col2:
            if st.button("🙅 '우린 냄새 안 나고 깨끗해요'", use_container_width=True):
                quick_rejection_prompt = "사장님이 '우리 매장은 깨끗해서 필요 없어요'라고 할 때, 깨끗한 매장에 시그니처 향을 더해 프리미엄 네이버 리뷰를 확보하는 3일 체험 설득 멘트를 안내해 주세요."
            if st.button("🙅 '공짜라 하고 돈 요구할 거죠?'", use_container_width=True):
                quick_rejection_prompt = "사장님이 '무상 설치해 주고 나중에 돈 요구하려는 것 아니냐'며 의심할 때, 100% 본사 지원 3일 무상 체험이며 마음에 안 들면 단 1원 없이 회수한다는 안심 스크립트를 안내해 주세요."
                
        with q_col3:
            if st.button("🙅 '월 비용이 부담돼요'", use_container_width=True):
                quick_rejection_prompt = "사장님이 '월 이용료가 부담된다'고 할 때, 네이버 악성 리뷰 1건 방지로 얻는 매출 보호 ROI 가치를 3일 체험 제안과 함께 설명하는 반박 화법을 안내해 주세요."
            if st.button("📞 '3일 체험 후 피드백 콜 화법'", use_container_width=True):
                quick_rejection_prompt = "3일간 무상 체험 장비 설치가 끝난 사장님에게 전화/방문하여 3일간의 효과 피드백을 물어보고 공식 유료 계약으로 전환(Closing)시키는 피드백 요청 스크립트를 안내해 주세요."

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    selected_faq = None
    st.write("💡 **경기 서북부 주요 거점 영업 타겟 분석 (버튼 터치):**")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📌 파주 야당역 상권", use_container_width=True):
            selected_faq = "파주 야당역"
    with col2:
        if st.button("📌 김포 구래동 상권", use_container_width=True):
            selected_faq = "김포 구래동"
    with col3:
        if st.button("📌 검단신도시 아라동", use_container_width=True):
            selected_faq = "검단신도시 아라동"
    with col4:
        if st.button("📌 고양 라페스타 B동", use_container_width=True):
            selected_faq = "고양 라페스타 B동"

    st.write("---")
    
    # 현장 사진 멀티모달 진단 + 1페이지 브리핑 리포트
    with st.expander("📸 **현장 사진 AI 진단 & 1페이지 영업 브리핑 리포트 생성**"):
        uploaded_img = st.file_uploader("현장 사진(매장, 주방, 화장실, 외관 등)을 첨부하시면 AI가 시각 요소를 분석하여 8대 제품 중 맞춤 제안 리포트를 작성해 드립니다.", type=["jpg", "jpeg", "png"], key="uploaded_file")
        if uploaded_img:
            st.image(uploaded_img, caption="첨부된 현장 사진 진단 준비 완료", width=250)

    prompt_input = st.chat_input("상권 및 보유 장비를 입력하세요... (예: 일산 라페스타에서 에어퍼퓸과 에어제닉으로 영업하려고 해. 어디를 가볼까?)")
    
    user_prompt = None
    if quick_rejection_prompt:
        user_prompt = quick_rejection_prompt
    elif selected_faq:
        user_prompt = selected_faq
    elif uploaded_img and not prompt_input and not st.session_state.img_processed:
        user_prompt = "첨부한 현장 사진을 시각적으로 정밀 진단하고, 8대 제품 라인업을 바탕으로 [1페이지 현장 영업 브리핑 리포트]를 작성해 주세요."
    elif prompt_input:
        user_prompt = prompt_input

    if user_prompt and (len(st.session_state.messages) == 0 or st.session_state.messages[-1]["content"] != user_prompt):
        st.chat_message("user").markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        real_stores_data = None
        if not quick_rejection_prompt and not uploaded_img:
            real_stores_data = search_kakao_local_stores(user_prompt)

        if real_stores_data and len(real_stores_data) > 0:
            with st.expander(f"📍 **카카오 지도 실시간 검색 매장 리스트 ({len(real_stores_data)}건 수집됨)**", expanded=True):
                st.dataframe(pd.DataFrame(real_stores_data)[["상호명", "업종", "주소", "전화번호"]], use_container_width=True)

        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        if quick_rejection_prompt:
            final_system_instruction = (
                "당신은 소상공인·가정 B2C 영업 전문가 'CLC AI영업툴'입니다.\n"
                "지역 정보, 건물 주소, 지도 링크, 요약표 등은 절대로 작성하거나 출력하지 마세요.\n"
                "오직 요청된 거절 상황에 대한 1초 즉시 반박 킬러 스크립트와 예상되는 고객 질문 및 답변을 불렛 포인트로 간결히 출력하세요."
            )
        elif uploaded_img and not st.session_state.img_processed:
            st.session_state.img_processed = True
            final_system_instruction = (
                "당신은 소상공인·가정 B2C 영업 전문가 'CLC AI영업툴'입니다.\n"
                "업로드된 현장 사진의 시각적 요소와 상황을 정밀 분석하여 [핵심 가치 두괄식 요약], [예상 고객 질문 및 답변], [추천 제품 및 제안 포인트]를 표나 불렛 포인트로 간결하게 정리해 주세요."
            )
        else:
            final_system_instruction = CLC_AI_SALES_TOOL_INSTRUCTION
            
            if real_stores_data and len(real_stores_data) > 0:
                stores_text_list = json.dumps(real_stores_data, ensure_ascii=False, indent=2)
                final_system_instruction += (
                    f"\n\n[★필수 지침★ 카카오 지도 실시간 수집 매장 리스트 ({len(real_stores_data)}건)]\n"
                    "아래 카카오 지도 실시간 매장 리스트 중에서 **3일 무상 체험 설치 성공 확률이 가장 높은 우선순위 1순위 매장과 2순위 매장(실제 상호명 2곳)**을 선별하여 두괄식으로 안내해 주세요.\n"
                    "그리고 예상되는 고객 질문(거절 포인트)과 답변을 함께 포함해 주세요:\n"
                    f"{stores_text_list}"
                )

            if knowledge_context:
                final_system_instruction += (
                    f"\n\n[업로드된 전체 통합 학습 문서 데이터 ({len(learned_files_list)}건 통합본)]\n"
                    "견적이나 제품 단가 문의 시 가장 중요한 참조 문서입니다. 답변 시 반드시 이 내용 안에서만 찾고 3번 점검하세요:\n\n"
                    f"{knowledge_context}"
                )

        with st.chat_message("assistant"):
            try:
                chat = client.chats.create(
                    model="gemini-3-flash-preview", 
                    config=types.GenerateContentConfig(
                        system_instruction=final_system_instruction
                    ),
                    history=history
                )
                
                if uploaded_img and not prompt_input and not st.session_state.get("img_sent", False):
                    from PIL import Image as PILImage
                    img_obj = PILImage.open(uploaded_img)
                    send_contents = [user_prompt, img_obj]
                    st.session_state.img_sent = True
                else:
                    send_contents = user_prompt

                response_stream = chat.send_message_stream(send_contents)
                
                def stream_generator():
                    for chunk in response_stream:
                        yield chunk.text

                full_response = st.write_stream(stream_generator())
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"⚠️ 답변 생성 실패: {e}")

    # ==========================================
    # 📱 AI 자동 완성형 카톡 제안서 & 에어제닉 인포그래픽 생성 센터
    # ==========================================
    st.write("---")
    st.subheader("📋 CLC AI영업툴 - 맞춤형 제안서 및 에어제닉 인포그래픽 센터")
    st.caption("기획하신 **세스코 에어제닉(Airzenic) 전용 인포그래픽 제안서**(문제점 3x2, 4단계 솔루션, 가격 비교, 황태팀장 브랜딩)를 원터치로 생성합니다.")
    
    proposal_tab1, proposal_tab2 = st.tabs(["📱 카톡 1페이지 요약 제안서", "🌿 에어제닉 상세 인포그래픽 (황태팀장 Pro)"])
    
    with proposal_tab1:
        with st.form("auto_kakao_form"):
            c1, c2 = st.columns(2)
            with c1:
                auto_store = st.text_input("상호명 / 고객명", placeholder="예: 야당역 브런치 카페")
                auto_ind = st.text_input("업종", placeholder="예: 카페 / 디저트")
            with c2:
                auto_loc = st.text_input("지역 / 상권", placeholder="예: 파주 야당역 상권")
                
            submitted_auto_kakao = st.form_submit_button("✨ AI 카톡 제안서 텍스트 생성하기", use_container_width=True)
            
        if submitted_auto_kakao:
            if not auto_store or not auto_ind:
                st.warning("상호명과 업종을 입력해 주세요.")
            else:
                kakao_formatted_text = f"""━━━━━━━━━━━━━━━━━━━━
🌿 [세스코(CESCO) 에어제닉 향기·탈취 솔루션 제안서]
━━━━━━━━━━━━━━━━━━━━

안녕하세요! 
'{auto_store}' 대표님, 사업장에 가장 최적화된 악취 제거 및 향기 케어 솔루션을 제안드립니다. 🔬✨

━━━━━━━━━━━━━━━━━━━━
📍 1. 사업장 진단 요약
━━━━━━━━━━━━━━━━━━━━
• 위치 및 상권: {auto_loc}
• 업종({auto_ind}): 화장실 및 홀 잔류 악취 완벽 차단

━━━━━━━━━━━━━━━━━━━━
🛡️ 2. 추천 제품: 세스코 에어제닉
━━━━━━━━━━━━━━━━━━━━
• 지능형 센서 감지 자동 탈취/발향
• 프리미엄 조향사 설계 향기 카트리지
• 3일 무상 체험 후 결정 가능

━━━━━━━━━━━━━━━━━━━━
💡 "상쾌한 향기는 고객의 발걸음을 머물게 합니다."
지금 바로 세스코 프리미엄 케어를 경험해보세요!
━━━━━━━━━━━━━━━━━━━━"""
                st.success("✅ 카톡 제안서 텍스트가 완성되었습니다!")
                st.code(kakao_formatted_text, language="markdown")

    with proposal_tab2:
        st.write("🌿 **세스코 에어제닉(Airzenic) 공식 인포그래픽 프로포절**")
        st.caption("기획하신 3x2 문제점 그리드, 4단계 Solution, 가격 비교표, 황태팀장 브랜딩 UI가 모두 담긴 고품격 인포그래픽을 생성합니다.")
        
        if st.button("🚀 에어제닉 인포그래픽 제안서 카드 생성하기 (.png)", use_container_width=True):
            with st.spinner("에어제닉 인포그래픽 템플릿을 정밀 렌더링 중입니다..."):
                img_bytes = generate_airzenic_infographic_card()
                st.image(img_bytes, caption="세스코 에어제닉 상세 인포그래픽 제안서", use_container_width=True)
                st.download_button(
                    label="📥 에어제닉 인포그래픽 다운로드 (.png)",
                    data=img_bytes,
                    file_name="CESCO_Airzenic_Infographic.png",
                    mime="image/png",
                    use_container_width=True
                )

    # ==========================================
    # 📝 현장 영업일지 기록 (3일 체험 스케줄 자동 연동)
    # ==========================================
    with st.expander("📝 **플래너 현장 영업 미팅 일지 기록하기 (3일 체험 관리)**"):
        st.caption("방문 매장 내역을 기록하세요. '설치 완료' 입력 시 3일 뒤 피드백 및 계약 클로징 일정이 대시보드에 자동 등록됩니다.")
        with st.form("sales_log_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                planner_input = st.text_input("담당 플래너 이름 * (예: 홍길동)")
                client_input = st.text_input("방문 매장/고객명 * (예: 대박식당)")
                p_deal = st.text_input("제안서 서비스 및 견적가 (예: 에어퍼퓸 3일체험 + 월 35,000원)")
                install_date_input = st.date_input("🗓️ 체험장비 설치일자", value=datetime.now())
            with col_b:
                eq_status = st.selectbox("🎁 체험장비 설치 여부", ["미설치", "설치 완료"])
                eq_item = st.text_input("설치한 체험장비 품목 (예: 에어퍼퓸, 에어제닉 B타입 등)")
                reaction = st.selectbox("고객 반응/상태", ["계약 완료 🎉", "3일 무상체험 설치 완료 🎁", "긍정적 (재방문 필요)", "보류 (가격 부담)"])
                memo = st.text_input("영업 메모 (예: 3일 뒤 목요일 오후 2시 방문하여 피드백 확인 및 계약서 작성)")
                
            submit_log = st.form_submit_button("💾 영업일지 저장 및 3일 체험 스케줄 연동", use_container_width=True)
            if submit_log:
                if planner_input and client_input:
                    with st.spinner("영업일지 저장 및 3일 체험 일정 계산 중..."):
                        save_sales_log(
                            planner_input, 
                            client_input, 
                            p_deal, 
                            eq_status, 
                            eq_item, 
                            reaction, 
                            memo, 
                            install_date=install_date_input.strftime("%Y-%m-%d")
                        )
                        st.toast("✅ 영업일지 저장 및 3일 체험 피드백 일정이 자동 연동되었습니다!", icon="🎉")
                        st.rerun()
                else:
                    st.warning("⚠️ 필수 항목(플래너 이름, 고객명)을 입력해 주세요.")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
