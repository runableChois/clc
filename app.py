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
    
    /* 모바일 및 웨일 브라우저 웹뷰 Material Icon 깨짐 방지 */
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
    except Exception:
        return None

# ==========================================
# 3. [AI Powered] Imagen 3 마케팅 전단지 생성 파이프라인
# ==========================================
def generate_imagen3_marketing_poster(client_genai, target_info, product_name, custom_notes, rag_context):
    """
    1. Gemini 2.5 Pro가 고객 상황(가정/사업장)과 제품을 분석하여 전문 카피와 Imagen 3 전용 고도화 프롬프트 작성
    2. Imagen 3 (imagen-3.0-generate-002) 호출하여 실사 포스터 이미지 생성
    """
    # 1단계: Gemini 전문가 분석 및 영문 광고 프롬프트 빌드
    prompt_builder_request = f"""
    You are a master creative director for premium living care and hygiene advertising.
    Analyze the following request and create a prompt for Google Imagen 3.

    [Input Data]
    - Target Audience: {target_info} (Analyze whether this is a modern family home/apartment or a commercial business)
    - Products: {product_name}
    - Custom Request/Notes: {custom_notes}
    - RAG Pricing/Spec Context: {rag_context[:1500]}

    [Poster Concept & Visual Requirements]
    - Format: Commercial promotional flyer poster, vertical 3:4 aspect ratio.
    - Top Section (60%): High-end, photorealistic commercial studio photography.
      * If Home: A stunning, sunlit modern minimalist Korean apartment interior (kitchen/living room/bathroom) featuring the sleek premium appliances operating seamlessly with pure water/crystal-clean air/sanitizing mist aesthetics.
      * If Store/Business: A pristine, hygienic, upscale store/restaurant interior with glowing clean ambiance.
      * Shot on 35mm lens, cinematic studio rim lighting, 8k resolution, Architectural Digest commercial style.
    - Bottom Section (40%): Matte dark charcoal (#0f172a) graphic layout with vibrant neon lime green (#A3E635) and crisp white typography.
      * Minimalist vector badges: 1:1 Expert Care, 99.9% Full Protection, Special Promotion.
      * High contrast action bar at bottom with bold arrow symbol.
    - No distorted artifacts, highly legible graphic layout, luxurious branding aesthetic.

    Output ONLY the final English prompt for Imagen 3 without any markdown quotes or intro.
    """
    
    try:
        res_prompt = client_genai.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt_builder_request
        )
        final_imagen_prompt = res_prompt.text.strip()
        
        # 2단계: Imagen 3 생성 호출
        result = client_genai.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=final_imagen_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="3:4",
                person_generation="ALLOW_ADULT"
            )
        )
        for gen_img in result.generated_images:
            return gen_img.image.image_bytes, None
    except Exception as e:
        return None, str(e)

# ==========================================
# 4. [Airzenic Pro] 세스코 에어제닉 전용 인포그래픽 렌더링
# ==========================================
def generate_airzenic_infographic_card(rag_data=None):
    FONT_PATH = "NanumGothic-Bold.ttf"
    if not os.path.exists(FONT_PATH):
        try:
            urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf", FONT_PATH)
        except Exception:
            pass

    prem_price = rag_data.get("prem_price", "250,000원") if rag_data else "250,000원"
    std_price = rag_data.get("std_price", "190,000원") if rag_data else "190,000원"

    width, height = 1200, 2150
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
    except Exception:
        f_header_t = f_header_s = f_section_t = f_card_t = f_card_d = f_price = f_footer = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 180)], fill='#003b7a')
    draw.rectangle([(0, 170), (width, 180)], fill='#00a3e0')
    draw.text((60, 35), "🦅 CESCO AIRZENIC PROPOSAL", fill='#38bdf8', font=ImageFont.truetype(FONT_PATH, 22))
    draw.text((60, 70), "악취는 없애고 순간의 향기로 공간을 채우는, 세스코 에어제닉!", fill='#ffffff', font=f_header_t)
    draw.text((60, 125), "우리 집 / 사업장 공간 공기, 지금 어떤가요?", fill='#cbd5e1', font=f_header_s)

    draw.text((60, 215), "🚨 이런 공간의 고민, 세스코가 해결합니다", fill='#0f172a', font=f_section_t)
    problems = [
        ("화장실의 끈질긴 암모니아 냄새", "배수구와 변기에서 발생하는 불쾌한 냄새가 상쾌함을 해칩니다."),
        ("반려동물의 배변 냄새 및 체취", "반려동물과 함께하는 공간에 배인 냄새와 체취가 고민입니다."),
        ("쓰레기통 주변의 부패한 악취", "생활 쓰레기에서 나오는 부패한 냄새가 공기를 무겁게 만듭니다."),
        ("담배 냄새 잔류", "환풍기를 틀어도 사라지지 않는 담배 냄새가 실내에 배어 있습니다."),
        ("밀폐된 공간의 답답하고 칙칙한 공기", "환기가 어려운 방이나 사무실의 공기가 답답합니다."),
        ("방향제 스프레이의 인위적인 잔향", "뿌릴 때만 잠시 가려질 뿐, 인위적인 향이 남아 불쾌합니다.")
    ]
    p_w, p_h = 525, 125
    p_start_y = 265
    for idx, (p_title, p_desc) in enumerate(problems):
        col = idx % 2
        row = idx // 2
        px = 60 if col == 0 else 615
        py = p_start_y + row * (p_h + 15)
        draw.rounded_rectangle([(px, py), (px + p_w, py + p_h)], radius=12, fill='#ffffff', outline='#cbd5e1', width=2)
        draw.text((px + 20, py + 18), f"• {p_title}", fill='#003b7a', font=f_card_t)
        desc_lines = [p_desc[i:i+30] for i in range(0, len(p_desc), 30)]
        dy = py + 52
        for line in desc_lines:
            draw.text((px + 20, dy), line, fill='#475569', font=f_card_d)
            dy += 22

    s_start_y = 735
    draw.text((60, s_start_y), "✨ CESCO Airzenic 4-Step Solution", fill='#0f172a', font=f_section_t)
    solutions = [
        ("POINT 01", "지능형 센서 감지", "사람의 움직임을 실시간으로 감지하여 자동으로 탈취/발향합니다."),
        ("POINT 02", "순간 발향 및 강력 탈취", "즉각 미세 탈취제와 향기를 분사하여 불쾌한 냄새를 제거합니다."),
        ("POINT 03", "프리미엄 향기 포트폴리오", "전문 조향사가 설계한 다양한 프리미엄 향기 중 맞춤 선택 가능합니다."),
        ("POINT 04", "간편한 설치 및 리필 교체", "벽걸이/스탠드형으로 어디든 설치 가능하며 리필 교체가 쉽습니다.")
    ]
    s_y = s_start_y + 50
    for step, s_name, s_desc in solutions:
        draw.rounded_rectangle([(60, s_y), (1140, s_y + 85)], radius=12, fill='#eff6ff', outline='#bfdbfe', width=2)
        draw.text((85, s_y + 18), step, fill='#0284c7', font=ImageFont.truetype(FONT_PATH, 16))
        draw.text((85, s_y + 42), s_name, fill='#0f172a', font=f_card_t)
        draw.text((360, s_y + 32), s_desc, fill='#334155', font=f_card_d)
        s_y += 100

    c_start_y = 1195
    draw.text((60, c_start_y), "📦 맞춤형 서비스 모델 및 단가", fill='#0f172a', font=f_section_t)
    box_w, box_h = 525, 185
    draw.rounded_rectangle([(60, c_start_y + 50), (60 + box_w, c_start_y + 50 + box_h)], radius=15, fill='#ffffff', outline='#003b7a', width=3)
    draw.text((90, c_start_y + 72), "👑 에어제닉 프리미엄형", fill='#003b7a', font=f_card_t)
    draw.text((90, c_start_y + 110), "스마트 모션 센서 및 자동 발향", fill='#475569', font=f_card_d)
    draw.text((90, c_start_y + 152), prem_price, fill='#0284c7', font=f_price)

    draw.rounded_rectangle([(615, c_start_y + 50), (615 + box_w, c_start_y + 50 + box_h)], radius=15, fill='#ffffff', outline='#cbd5e1', width=2)
    draw.text((645, c_start_y + 72), "📦 에어제닉 스탠다드형", fill='#0f172a', font=f_card_t)
    draw.text((645, c_start_y + 110), "고정 타이머 발향 기본형", fill='#475569', font=f_card_d)
    draw.text((645, c_start_y + 152), std_price, fill='#334155', font=f_price)

    ui_y = 1460
    draw.rounded_rectangle([(60, ui_y), (1140, ui_y + 130)], radius=15, fill='#0f172a', outline='#38bdf8', width=2)
    draw.ellipse([(95, ui_y + 25), (175, ui_y + 105)], fill='#38bdf8')
    draw.text((115, ui_y + 52), "황태", fill='#0f172a', font=ImageFont.truetype(FONT_PATH, 22))
    draw.text((195, ui_y + 32), "황태 팀장", fill='#ffffff', font=f_card_t)
    draw.text((195, ui_y + 72), "14시간 전 • 프로필 업데이트", fill='#94a3b8', font=f_footer)

    cta_y = 1640
    draw.rounded_rectangle([(60, cta_y), (1140, cta_y + 150)], radius=15, fill='#003b7a', outline='#38bdf8', width=3)
    draw.text((95, cta_y + 35), "📞 지금 바로 세스코 맞춤형 케어 상담을 신청하세요!", fill='#ffffff', font=f_card_t)
    draw.text((95, cta_y + 80), "“깨끗하고 안전한 공간은 고객의 발걸음을 머물게 합니다.”", fill='#38bdf8', font=f_header_s)

    draw.rectangle([(0, height - 80), (width, height)], fill='#020617')
    draw.text((60, height - 50), "CESCO 경기서북부 담당 플래너 | www.cesco.co.kr", fill='#94a3b8', font=f_footer)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# ==========================================
# 5. [LOCK - CLC AI영업툴] 고도화된 페르소나 및 시스템 지침
# ==========================================
CLC_AI_SALES_TOOL_INSTRUCTION = """
당신은 현장 B2C(가정) 및 소상공인(사업장) 영업 전문가인 'CLC AI영업툴'입니다.
주로 소상공인 대표 혹은 가정의 가장 및 결정권자를 상대로 단기 성과 구축과 계약 및 매출 증대를 이끌어내는 것이 주된 목표입니다.

[소통 및 답변 원칙]
1. 가정집 고객에게는 '사업장/매장' 등의 단어를 쓰지 말고, '가정/우리 집/가족' 관점으로 제안하세요.
2. 친절하면서도 전문적이고, 어려운 기술 용어보다는 쉬운 일상적 비유를 사용하여 소통합니다.
3. 자료 요청(제안서, 스크립트 등) 시, **항상 핵심 가치를 먼저 두괄식으로 제시**합니다.
4. **예상되는 고객의 거절/질문과 그에 대한 명확한 답변**을 반드시 포함해 주세요.
5. 답변 길이는 핵심만 간결하게 요약하며, 복잡한 내용은 표나 불렛 포인트로 정리합니다.
6. 절대 고객을 가르치려 들거나 강압적인 어투를 사용하지 않습니다.

[세스코 핵심 8대 제품 라인업]
1. 공기청정기: '판테온' (360도 필터, CA인증, CO2/PM1.0 센서)
2. 공기살균기: '센스미' (UV-C 파워 램프, 부유 바이러스·세균 99.9% 제거)
3. 탱크형 정수기: '더슬림', '더블', '더맥스' (업소용 대용량)
4. 직수 정수기: '살균온', '살균온 얼음정수기' (UVnano 코크 살균)
5. 비데: '파워방수비데', '살균방수비데', '올인원비데' (IPX6 방수)
6. 향기 제품: '에어퍼퓸200', '에어제닉' (자동 향기 분사 및 악취 분해)
7. 화장실 케어 제품: '프레쉬제닉', '핸드제닉', '새니제닉'
8. 날벌레 방지 제품: '에어커튼', '포충등'
"""

# ==========================================
# 6. 데이터 I/O 및 RAG 누적 학습
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
    try:
        if filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file, sheet_name=0)
            df = df.dropna(how="all")
            extracted_text = df.to_markdown(index=False)
        elif filename.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            df = df.dropna(how="all")
            extracted_text = df.to_markdown(index=False)
        elif filename.endswith('.pdf'):
            uploaded_file.seek(0)
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
    except Exception as e:
        return False, f"⚠️ `{filename}` 파일 읽기 실패: {str(e)}"

    if extracted_text:
        current_context, current_files = load_knowledge_data()
        if filename in current_files.split(","):
            return False, f"⚠️ `{filename}` 문서는 이미 학습되어 있습니다."

        new_context = current_context + f"\n\n--- [학습 문서: {filename}] ---\n" + extracted_text + f"\n--- [끝: {filename}] ---\n"
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
        except Exception:
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
        df = pd.concat([old_df, new_data], ignore_index=True)
    else:
        df = new_data
    df.to_csv(SALES_LOG_PATH, index=False, encoding="utf-8-sig")

def load_equipment_inventory():
    if os.path.exists(EQUIPMENT_LOG_PATH):
        df = pd.read_csv(EQUIPMENT_LOG_PATH)
        if "담당팀원" in df.columns:
            df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
        return df
    default_df = pd.DataFrame([
        {"담당플래너": "홍길동", "전체 보유대수": 5},
        {"담당플래너": "김철수", "전체 보유대수": 3}
    ])
    default_df.to_csv(EQUIPMENT_LOG_PATH, index=False, encoding="utf-8-sig")
    return default_df

def save_equipment_inventory(df):
    df.to_csv(EQUIPMENT_LOG_PATH, index=False, encoding="utf-8-sig")

# ==========================================
# 7. 사이드바 UI
# ==========================================
with st.sidebar:
    st.header("⚙️ CLC AI영업툴 센터")
    st.success("💼 **CLC AI영업툴 (Gemini 2.5 Pro + Imagen 3)**")
    st.caption("가정 B2C 및 소상공인 영업 성공을 위한 전문 시스템")

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
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📊 영업 대시보드", "📦 장비 운용 설정", "📁 단가표 학습"])
        
        with admin_tab1:
            st.write("📈 **실시간 영업 성과 & 3일 체험 전환 대시보드**")
            if os.path.exists(SALES_LOG_PATH):
                logs_df = pd.read_csv(SALES_LOG_PATH)
                st.dataframe(logs_df, use_container_width=True)
            else:
                st.info("영업일지 데이터가 없습니다.")

        with admin_tab2:
            current_inv = load_equipment_inventory()
            edited_df = st.data_editor(current_inv, num_rows="dynamic", use_container_width=True)
            if st.button("💾 전체 보유대수 저장", use_container_width=True):
                save_equipment_inventory(edited_df)
                st.toast("✅ 저장 완료!", icon="🎉")
                st.rerun()

        with admin_tab3:
            uploaded_files = st.file_uploader("단가표/제품 문서 누적 학습", type=["pdf", "xlsx", "csv"], accept_multiple_files=True)
            if uploaded_files and st.button("💾 모든 문서 누적 학습시키기", use_container_width=True):
                for up_file in uploaded_files:
                    add_file_to_cumulative_knowledge(up_file)
                st.toast("✅ 학습 완료!", icon="🎉")
                st.rerun()
                
            if learned_files_list and st.button("🗑️ 학습 데이터 초기화", use_container_width=True):
                delete_all_knowledge_data()
                st.toast("초기화 완료!", icon="🧹")
                st.rerun()
    elif input_pwd:
        st.error("비밀번호 불일치")

    st.divider()
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state["messages"] = []
        st.toast("대화 내용이 초기화되었습니다.", icon="🧹")
        st.rerun()

# ==========================================
# 8. 메인 화면 & 챗봇 인터페이스 (Gemini 2.5 Pro)
# ==========================================
st.title("💼 CLC AI영업툴 (Pro)")
st.caption("📌 **Gemini 2.5 Pro 플래그십 엔진 + Imagen 3 실사 포스터 연동**")
st.divider()

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 1초 반박 퀵카드
    with st.expander("⚡ **현장 사장님/고객 거절 반응 '1초 반박' 퀵카드 (원터치)**", expanded=False):
        q_col1, q_col2, q_col3 = st.columns(3)
        quick_rejection_prompt = None
        with q_col1:
            if st.button("🙅 '사장님 지금 안 계세요'", use_container_width=True):
                quick_rejection_prompt = "고객이 '결정권자가 지금 안 계세요'라고 거절했을 때, 명함을 확보하고 핵심 혜택을 전달하는 1초 반박 스크립트를 작성해 주세요."
            if st.button("🙅 '기존 제품/디퓨저 있어요'", use_container_width=True):
                quick_rejection_prompt = "고객이 '기존 제품 쓰고 있어요'라고 거절할 때 세스코의 정밀 살균·차별점을 강조하는 피칭 스크립트를 작성해 주세요."
        with q_col2:
            if st.button("🙅 '우린 깨끗해서 필요 없어요'", use_container_width=True):
                quick_rejection_prompt = "고객이 '우린 깨끗해서 필요 없어요'라고 할 때 잠재 리스크 방지 가치를 설명하는 설득 멘트를 작성해 주세요."
            if st.button("🙅 '공짜라 하고 돈 요구하죠?'", use_container_width=True):
                quick_rejection_prompt = "고객이 '나중에 비용 요구하려는 것 아니냐'며 의심할 때 안심시키는 신뢰 스크립트를 작성해 주세요."
        with q_col3:
            if st.button("🙅 '월 비용이 부담돼요'", use_container_width=True):
                quick_rejection_prompt = "고객이 '월 이용료가 부담된다'고 할 때 손실 방지 ROI 가치를 설명하는 반박 화법을 작성해 주세요."
            if st.button("📞 '체험/상담 후 계약 클로징'", use_container_width=True):
                quick_rejection_prompt = "상담 또는 체험 후 고객에게 공식 유료 계약으로 전환(Closing)시키는 피드백 요청 스크립트를 작성해 주세요."

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

    # 현장 사진 멀티모달 진단
    with st.expander("📸 **현장 사진 AI 진단 & 1페이지 영업 브리핑 리포트 생성**"):
        uploaded_img = st.file_uploader("현장 사진(매장, 주방, 화장실, 가정 외관 등)을 첨부하시면 AI가 시각 요소를 분석하여 맞춤 제안 리포트를 작성합니다.", type=["jpg", "jpeg", "png"])
        if uploaded_img:
            st.image(uploaded_img, caption="첨부된 사진 진단 준비 완료", width=250)

    prompt_input = st.chat_input("질문 또는 제안서 요청... (예: 대박식당에 더슬림 정수기 제안서 이미지 만들어줘 / 가정집에 비데 제안서 작성해줘)")
    
    user_prompt = None
    if quick_rejection_prompt:
        user_prompt = quick_rejection_prompt
    elif selected_faq:
        user_prompt = selected_faq
    elif uploaded_img and not prompt_input:
        user_prompt = "첨부한 현장 사진을 정밀 진단하고 맞춤 제안 리포트를 작성해 주세요."
    elif prompt_input:
        user_prompt = prompt_input

    if user_prompt and (len(st.session_state.messages) == 0 or st.session_state.messages[-1]["content"] != user_prompt):
        st.chat_message("user").markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        real_stores_data = None
        if not quick_rejection_prompt and not uploaded_img:
            real_stores_data = search_kakao_local_stores(user_prompt)

        if real_stores_data and len(real_stores_data) > 0:
            with st.expander(f"📍 **카카오 지도 실시간 검색 매장 리스트 ({len(real_stores_data)}건)**", expanded=True):
                st.dataframe(pd.DataFrame(real_stores_data)[["상호명", "업종", "주소", "전화번호"]], use_container_width=True)

        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        final_system_instruction = CLC_AI_SALES_TOOL_INSTRUCTION
        if real_stores_data and len(real_stores_data) > 0:
            stores_text_list = json.dumps(real_stores_data, ensure_ascii=False, indent=2)
            final_system_instruction += f"\n\n[카카오 지도 수집 매장 리스트]\n{stores_text_list}"
        if knowledge_context:
            final_system_instruction += f"\n\n[학습된 단가표 및 제품 정보]\n{knowledge_context}"

        with st.chat_message("assistant"):
            try:
                chat = client.chats.create(
                    model="gemini-2.5-pro", 
                    config=types.GenerateContentConfig(system_instruction=final_system_instruction),
                    history=history
                )
                
                if uploaded_img and not prompt_input:
                    from PIL import Image as PILImage
                    img_obj = PILImage.open(uploaded_img)
                    send_contents = [user_prompt, img_obj]
                else:
                    send_contents = user_prompt

                response_stream = chat.send_message_stream(send_contents)
                response_chunks = []
                def stream_generator():
                    for chunk in response_stream:
                        response_chunks.append(chunk.text)
                        yield chunk.text

                st.write_stream(stream_generator())
                full_response = "".join(response_chunks)

                # '제안서' 및 '이미지' 요청 시 Imagen 3 호출
                if any(k in user_prompt for k in ["제안서 이미지", "제안서 만들어", "제안서 생성", "이미지 만들어", "이미지 생성", "전단지"]):
                    with st.spinner("🎨 Imagen 3가 초고화질 실사 마케팅 전단지 포스터를 렌더링 중입니다..."):
                        target_info = "가정용 프리미엄 케어" if any(k in user_prompt for k in ["가정", "집", "아파트"]) else "사업장 안심 케어"
                        
                        img_bytes, err = generate_imagen3_marketing_poster(
                            client_genai=client,
                            target_info=target_info,
                            product_name=user_prompt,
                            custom_notes=full_response[:200],
                            rag_context=knowledge_context
                        )
                        if img_bytes:
                            st.image(img_bytes, caption="🎨 Imagen 3 AI 마케팅 전단지 포스터", use_container_width=True)
                            st.download_button(
                                label="📥 전단지 이미지 다운로드 (.jpg)",
                                data=img_bytes,
                                file_name="CESCO_Marketing_Flyer.jpg",
                                mime="image/jpeg",
                                use_container_width=True
                            )
                        else:
                            st.error(f"⚠️ Imagen 3 생성 오류 (Google AI Studio API 권한 또는 Billing 상태 확인 필요): {err}")

                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"⚠️ 답변 생성 실패: {e}")

    # ==========================================
    # 9. 맞춤형 제안서 & 인포그래픽 센터
    # ==========================================
    st.write("---")
    st.subheader("📋 CLC AI 맞춤형 제안서 & 인포그래픽 센터")
    tab1, tab2, tab3 = st.tabs(["📱 카톡 1페이지 제안서", "🎨 Imagen 3 AI 실사 전단지", "🌿 에어제닉 4-Step 인포그래픽"])
    
    with tab1:
        with st.form("auto_kakao_form"):
            c1, c2 = st.columns(2)
            with c1:
                auto_client = st.text_input("고객 대상 (예: 일반 가정집 / 카페)")
                auto_prod = st.text_input("제안 제품 (예: 더슬림 정수기 / 살균방수비데)")
            with c2:
                auto_loc = st.text_input("상황/특징 (예: 신축 아파트 / 위생 강조)")
            submitted_kakao = st.form_submit_button("✨ 고객 맞춤 카톡 제안서 생성 (400~500자)", use_container_width=True)
            
        if submitted_kakao and auto_client and auto_prod:
            with st.spinner("Gemini 2.5 Pro가 고객 니즈 맞춤형 카톡 제안서를 작성 중입니다..."):
                prompt_txt = f"""
                당신은 영업 전문가 'CLC AI영업툴'입니다.
                대상: '{auto_client}', 제안 제품: '{auto_prod}', 상황/특징: '{auto_loc}'
                1. 대상이 가정집인지 사업장인지 정확히 구분하여 공감대를 형성하세요.
                2. 해당 제품이 불편함을 어떻게 해결하는지 두괄식으로 명쾌하게 제시하세요.
                3. 글자수는 400~500자 내외로 제한하고, 이모지와 불렛 포인트를 사용해 가독성을 높이세요.
                학습 데이터 단가표 참조: {knowledge_context[:1500]}
                """
                res_k = client.chats.create(model="gemini-2.5-pro").send_message(prompt_txt).text
                st.success("✅ 카톡 제안서가 완성되었습니다! 우측 상단 복사 버튼을 눌러 활용하세요.")
                st.code(res_k, language="markdown")

    with tab2:
        st.write("🎨 **Google Imagen 3 실사 마케팅 전단지 포스터 생성**")
        st.caption("AI가 제품과 대상 고객에 맞는 전문 카피와 상업 광고 비주얼을 실시간으로 합성하여 전단지 포스터를 생성합니다.")
        with st.form("imagen3_flyer_form"):
            f_target = st.text_input("고객 대상 (예: 가정집 / 베이커리 카페)", value="일반 가정집")
            f_prod = st.text_input("제안 제품군 (예: 살균온정수기, 판테온, 올인원비데)", value="살균온정수기, 판테온, 올인원비데")
            f_point = st.text_input("강조 요청 사항 (예: AI가 알아서 가족 안심 케어로 추천)", value="가족 건강을 위한 99.9% 살균 케어 패키지")
            submitted_flyer = st.form_submit_button("🚀 Imagen 3 전단지 포스터 생성", use_container_width=True)
            
        if submitted_flyer and f_target and f_prod:
            with st.spinner("🎨 Imagen 3가 고화질 마케팅 전단지 포스터를 렌더링 중입니다..."):
                img_bytes, err = generate_imagen3_marketing_poster(
                    client_genai=client,
                    target_info=f_target,
                    product_name=f_prod,
                    custom_notes=f_point,
                    rag_context=knowledge_context
                )
                if img_bytes:
                    st.image(img_bytes, caption=f"🎨 Imagen 3 실사 포스터 ({f_prod})", use_container_width=True)
                    st.download_button(
                        label="📥 전단지 이미지 다운로드 (.jpg)",
                        data=img_bytes,
                        file_name=f"CESCO_{f_target}_Flyer.jpg",
                        mime="image/jpeg",
                        use_container_width=True
                    )
                else:
                    st.error(f"⚠️ Imagen 3 이미지 생성 실패: {err}\n\nGoogle AI Studio 콘솔에서 종량제 결제(Pay-as-you-go)가 활성화되어 있는지 확인해 주세요.")

    with tab3:
        st.write("🌿 **세스코 에어제닉(Airzenic) 4-Step 공식 인포그래픽**")
        st.caption("3x2 문제점 분석, 4단계 솔루션, 프리미엄/스탠다드 단가표, 황태팀장 브랜딩이 포함된 고해상도 인포그래픽 카드입니다.")
        if st.button("🚀 에어제닉 인포그래픽 생성 (.png)", use_container_width=True):
            with st.spinner("인포그래픽 렌더링 중..."):
                # RAG 단가 파싱
                rag_parsed_data = {"prem_price": "250,000원", "std_price": "190,000원"}
                if knowledge_context:
                    try:
                        ex_p = client.chats.create(model="gemini-2.5-pro").send_message(
                            f"문서에서 에어제닉 프리미엄형과 스탠다드형 가격을 찾아 JSON {{\"prem_price\":\"금액\",\"std_price\":\"금액\"}} 형식으로만 답해줘:\n{knowledge_context[:3000]}"
                        ).text
                        m = re.search(r'\{.*\}', ex_p, re.DOTALL)
                        if m:
                            rag_parsed_data = json.loads(m.group())
                    except Exception:
                        pass
                
                air_img_bytes = generate_airzenic_infographic_card(rag_data=rag_parsed_data)
                st.image(air_img_bytes, caption="세스코 에어제닉 상세 인포그래픽", use_container_width=True)
                st.download_button(
                    label="📥 인포그래픽 다운로드 (.png)",
                    data=air_img_bytes,
                    file_name="CESCO_Airzenic_Infographic.png",
                    mime="image/png",
                    use_container_width=True
                )

    # ==========================================
    # 10. 현장 영업일지 기록
    # ==========================================
    with st.expander("📝 **플래너 현장 영업 미팅 일지 기록하기 (3일 체험 관리)**"):
        st.caption("방문 매장/가정집 내역을 기록하세요. '설치 완료' 입력 시 3일 뒤 피드백 및 계약 클로징 일정이 대시보드에 자동 등록됩니다.")
        with st.form("sales_log_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                planner_input = st.text_input("담당 플래너 이름 * (예: 홍길동)")
                client_input = st.text_input("방문 고객/매장명 * (예: 대박식당 / 김고객 가정집)")
                p_deal = st.text_input("제안 견적 (예: 정수기 월 28,000원)")
                install_date_input = st.date_input("🗓️ 설치/미팅 일자", value=datetime.now())
            with col_b:
                eq_status = st.selectbox("🎁 체험/설치 여부", ["미설치", "설치 완료"])
                eq_item = st.text_input("설치 장비 품목 (선택사항)")
                reaction = st.selectbox("고객 반응/상태", ["계약 완료 🎉", "3일 무상체험 설치 완료 🎁", "긍정적 (재방문 필요)", "보류"])
                memo = st.text_input("영업 메모")
                
            submit_log = st.form_submit_button("💾 영업일지 저장 및 피드백 스케줄 연동", use_container_width=True)
            if submit_log:
                if planner_input and client_input:
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
                    st.toast("✅ 영업일지가 저장되었습니다!", icon="🎉")
                    st.rerun()
                else:
                    st.warning("⚠️ 플래너 이름과 고객명을 입력해 주세요.")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
