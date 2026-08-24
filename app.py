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
# 2. 카카오 지도 API 매장 검색
# ==========================================
def search_kakao_local_stores(query_text):
    kakao_key = st.secrets.get("KAKAO_REST_API_KEY", "4b59cf7aff54ff6e7b451b761d5befaf").strip()
    if not kakao_key:
        return None
    
    clean_query = query_text
    for stop_word in ["입점 매장", "입점매장", "매장 리스트", "점포 리스트", "상권", "특징", "전략", "분석해줘", "알려줘", "추천"]:
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
# 3. 폴백용 그래픽 카드 생성 엔진 (Pillow)
# ==========================================
def generate_general_proposal_card(client_info, product_name, summary_text, price_text):
    FONT_PATH = "NanumGothic-Bold.ttf"
    if not os.path.exists(FONT_PATH):
        try:
            urllib.request.urlretrieve("https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf", FONT_PATH)
        except Exception:
            pass

    width, height = 1200, 1800
    img = Image.new('RGB', (width, height), color='#0f172a')
    draw = ImageDraw.Draw(img)

    try:
        f_hero = ImageFont.truetype(FONT_PATH, 44)
        f_title = ImageFont.truetype(FONT_PATH, 30)
        f_sub = ImageFont.truetype(FONT_PATH, 24)
        f_box_t = ImageFont.truetype(FONT_PATH, 24)
        f_box_b = ImageFont.truetype(FONT_PATH, 20)
        f_cta_h = ImageFont.truetype(FONT_PATH, 32)
        f_foot = ImageFont.truetype(FONT_PATH, 18)
    except Exception:
        f_hero = f_title = f_sub = f_box_t = f_box_b = f_cta_h = f_foot = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 220)], fill='#001e3d')
    draw.rectangle([(0, 210), (width, 220)], fill='#a3e635')
    draw.text((60, 40), "🦅 CESCO 맞춤형 솔루션 제안서", fill='#38bdf8', font=f_sub)
    draw.text((60, 85), f"{product_name} 프리미엄 제안", fill='#ffffff', font=f_hero)
    draw.text((60, 155), f"제안 대상: {client_info}", fill='#cbd5e1', font=f_sub)

    draw.rounded_rectangle([(60, 260), (1140, 540)], radius=16, fill='#1e293b', outline='#334155', width=2)
    draw.text((95, 295), "📌 고객 맞춤 진단 및 도입 효과", fill='#38bdf8', font=f_box_t)
    clean_summary = summary_text.replace("\n", " ").strip()
    sum_lines = [clean_summary[i:i+42] for i in range(0, len(clean_summary), 42)]
    sy = 350
    for line in sum_lines[:4]:
        draw.text((95, sy), f"• {line}", fill='#f1f5f9', font=f_box_b)
        sy += 38

    draw.rounded_rectangle([(60, 580), (1140, 880)], radius=16, fill='#1e293b', outline='#334155', width=2)
    draw.text((95, 615), f"✨ {product_name} 핵심 구성 및 견적", fill='#a3e635', font=f_box_t)
    draw.text((95, 675), "• 전문 테크니션 1:1 정밀 관리 및 위생 점검", fill='#f1f5f9', font=f_box_b)
    draw.text((95, 725), "• 공간 맞춤형 친환경 고효율 설계 적용", fill='#f1f5f9', font=f_box_b)
    draw.text((95, 790), f"💰 제안 견적: {price_text}", fill='#ffffff', font=f_title)

    draw.text((60, 920), "🎁 제공 혜택 및 안심 보장", fill='#ffffff', font=f_title)
    b_w, b_h = 345, 240
    benefits = [
        ("👤 1:1 전담 관리", "전문 담당자의\n정기 점검 및\n신속한 사후 A/S"),
        ("🛡️ 품질 안심 보장", "공인 시험성적 검증\n유해균 차단 및\n최적 위생 환경 유지"),
        ("✨ 맞춤 프로모션", "공간별 최적 견적\n및 특별 프로모션 적용")
    ]
    for idx, (b_t, b_d) in enumerate(benefits):
        bx = 60 + idx * (b_w + 22)
        draw.rounded_rectangle([(bx, 970), (bx + b_w, 970 + b_h)], radius=14, fill='#1e293b', outline='#0284c7', width=2)
        draw.text((bx + 20, 995), b_t, fill='#a3e635', font=f_box_t)
        by_text = 1050
        for line in b_d.split('\n'):
            draw.text((bx + 20, by_text), line, fill='#e2e8f0', font=f_box_b)
            by_text += 30

    cta_y = 1260
    draw.rounded_rectangle([(60, cta_y), (1140, cta_y + 190)], radius=18, fill='#a3e635', outline='#ffffff', width=2)
    draw.text((95, cta_y + 35), "➔ 지금 바로 맞춤형 상담을 신청해 보세요!", fill='#0f172a', font=f_cta_h)
    draw.text((95, cta_y + 90), "“쾌적하고 위생적인 공간이 건강한 일상을 만듭니다.”", fill='#1e293b', font=f_title)
    draw.text((95, cta_y + 135), "세스코 공식 서비스 플래너 | www.cesco.co.kr", fill='#334155', font=f_box_b)

    draw.rectangle([(0, height - 70), (width, height)], fill='#020617')
    draw.text((60, height - 45), "Clean & Safe Living Care Solution • CESCO", fill='#64748b', font=f_foot)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# ==========================================
# 4. [Imagen 3 전용 고화질 전단지 생성 함수]
# ==========================================
def generate_imagen3_flyer(client_genai, client_info, product_name, summary_text):
    """
    1단계: Gemini 3 Pro가 첨부 이미지 스타일의 영문 Imagen 3 프롬프트 구성
    2단계: imagen-3.0-generate-002 호출하여 실사 마케팅 전단지 생성
    """
    prompt_builder = f"""
    Write a highly detailed English prompt for Google Imagen 3 to generate a commercial advertising promotional flyer poster.
    Product: {product_name}
    Target/Context: {client_info}
    Key Selling Point: {summary_text}
    Design Style:
    - Vertical layout, split composition.
    - Top half: A crisp, cinematic, high-end studio commercial photograph of the sleek modern appliance in an aesthetic living/working space, soft studio rim lighting.
    - Bottom half: Dark navy/charcoal background with neon lime-green and crisp white graphic layout, neat bullet points with minimalist modern icons.
    - Bold call-to-action bar with a clean arrow icon at the very bottom.
    - Professional, premium branding, 8k resolution, commercial advertising photography.
    Return ONLY the raw prompt string in English.
    """
    try:
        res = client_genai.models.generate_content(
            model="gemini-3-pro-preview",
            contents=prompt_builder
        )
        final_img_prompt = res.text.strip()

        result = client_genai.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=final_img_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="3:4"
            )
        )
        for gen_img in result.generated_images:
            return gen_img.image.image_bytes
    except Exception as e:
        # Billing 미연결 또는 오류 시 Pillow 카드로 안전하게 대체
        return generate_general_proposal_card(client_info, product_name, summary_text, "단가표 참조")

# ==========================================
# 5. 시스템 지침
# ==========================================
CLC_AI_SALES_TOOL_INSTRUCTION = """
당신은 현장 B2C(가정) 및 소상공인(사업장) 영업 전문가 'CLC AI영업툴'입니다.
고객 상황(가정집인지, 매장인지)을 질문 문맥에서 정확히 파악하여 답변하세요.

[답변 원칙]
1. 가정집 고객에게는 '사업장/매장' 등의 단어를 절대 쓰지 말고, '가정/우리 집/가족' 관점으로 제안하세요.
2. 3일 무료체험이 해당하지 않거나 언급되지 않은 제품에는 '3일 체험'을 억지로 넣지 마세요.
3. 특정 지사명을 강제하지 말고 플래너의 요청 맥락에 맞추세요.
4. 카톡 제안서 요청 시, 400~500자 내외의 마크다운 형식으로 작성하세요.
5. 제안서 이미지를 요청받은 경우에만 이미지 카드를 함께 출력합니다.
"""

# ==========================================
# 6. 데이터 I/O 및 RAG 함수
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

        new_context = current_context + f"\n\n--- [학습 문서: {filename}] ---\n" + extracted_text
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
    st.success("💼 **CLC AI영업툴 가동 중**")
    st.caption("가정 B2C 및 소상공인 영업 지원 비서 (Gemini 3 Pro + Imagen 3)")

    st.divider()
    st.subheader("📚 현재 AI 학습 문서 상태")
    if learned_files_list:
        st.success(f"**학습 완료 ({len(learned_files_list)}건):**")
        st.text_area("파일 목록", value="\n".join(learned_files_list), height=100)
    else:
        st.info("현재 학습된 단가표 문서가 없습니다.")

    st.divider()
    st.subheader("🔑 관리자 패널")
    admin_password_secret = st.secrets.get("ADMIN_PASSWORD", "1234")
    input_pwd = st.text_input("비밀번호 입력:", type="password")
    
    if input_pwd == admin_password_secret:
        st.success("🔓 관리자 권한 활성화됨")
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📊 영업 대시보드", "📦 장비 설정", "📁 문서 학습"])
        
        with admin_tab1:
            if os.path.exists(SALES_LOG_PATH):
                logs_df = pd.read_csv(SALES_LOG_PATH)
                st.dataframe(logs_df, use_container_width=True)
            else:
                st.info("기록된 영업일지가 없습니다.")

        with admin_tab2:
            current_inv = load_equipment_inventory()
            edited_df = st.data_editor(current_inv, num_rows="dynamic", use_container_width=True)
            if st.button("💾 보유대수 저장", use_container_width=True):
                save_equipment_inventory(edited_df)
                st.toast("✅ 저장 완료!", icon="🎉")
                st.rerun()

        with admin_tab3:
            uploaded_files = st.file_uploader("단가표/제품 문서 업로드", type=["pdf", "xlsx", "csv"], accept_multiple_files=True)
            if uploaded_files and st.button("💾 누적 학습시키기", use_container_width=True):
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
    if st.button("🔄 대화 초기화", use_container_width=True):
        st.session_state["messages"] = []
        st.toast("초기화되었습니다.", icon="🧹")
        st.rerun()

# ==========================================
# 8. 메인 챗봇 인터페이스
# ==========================================
st.title("💼 CLC AI영업툴 (Pro)")
st.caption("📌 **Gemini 3 Pro (추론) + Imagen 3 (실사 전단지 생성)**")
st.divider()

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 1초 반박 퀵카드
    with st.expander("⚡ **현장 거절 반응 '1초 반박' 퀵카드**", expanded=False):
        q_col1, q_col2, q_col3 = st.columns(3)
        quick_rejection_prompt = None
        with q_col1:
            if st.button("🙅 '결정권자 부재'", use_container_width=True):
                quick_rejection_prompt = "고객이 '결정권자가 지금 없다'고 할 때 명함을 확보하고 핵심 혜택을 전달하는 화법을 작성해 주세요."
        with q_col2:
            if st.button("🙅 '기존 제품 사용 중'", use_container_width=True):
                quick_rejection_prompt = "고객이 '기존 제품 쓰고 있다'고 할 때 세스코의 살균 관리 차별점을 설명하는 화법을 작성해 주세요."
        with q_col3:
            if st.button("🙅 '비용 부담'", use_container_width=True):
                quick_rejection_prompt = "고객이 '월 이용료가 부담된다'고 할 때 가성비와 손실 방지 가치를 설명하는 화법을 작성해 주세요."

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt_input = st.chat_input("질문 또는 제안서 요청... (예: 대박식당에 더슬림 정수기 제안서 이미지 만들어줘 / 일반 가정집에 비데 제안서 작성해줘)")
    user_prompt = quick_rejection_prompt if quick_rejection_prompt else prompt_input

    if user_prompt and (len(st.session_state.messages) == 0 or st.session_state.messages[-1]["content"] != user_prompt):
        st.chat_message("user").markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        final_system_instruction = CLC_AI_SALES_TOOL_INSTRUCTION
        if knowledge_context:
            final_system_instruction += f"\n\n[학습 문서]\n{knowledge_context}"

        with st.chat_message("assistant"):
            try:
                chat = client.chats.create(
                    model="gemini-3-pro-preview", 
                    config=types.GenerateContentConfig(system_instruction=final_system_instruction),
                    history=history
                )
                
                response_stream = chat.send_message_stream(user_prompt)
                response_chunks = []
                def stream_generator():
                    for chunk in response_stream:
                        response_chunks.append(chunk.text)
                        yield chunk.text

                st.write_stream(stream_generator())
                full_response = "".join(response_chunks)
                
                # 제안서 이미지 생성 요청 판별
                if any(k in user_prompt for k in ["제안서 이미지", "제안서 만들어", "제안서 생성", "이미지 만들어", "이미지 생성", "전단지"]):
                    with st.spinner("Imagen 3가 실사 마케팅 전단지 이미지를 생성 중입니다..."):
                        target_info = "일반 고객 맞춤"
                        if "가정" in user_prompt or "집" in user_prompt:
                            target_info = "가정용 프리미엄 케어"
                        elif any(k in user_prompt for k in ["식당", "카페", "매장", "업체"]):
                            target_info = "사업장 안심 케어"
                            
                        p_name = "세스코 케어 솔루션"
                        for prod in ["에어제닉", "더슬림", "판테온", "센스미", "에어퍼퓸", "정수기", "비데"]:
                            if prod in user_prompt:
                                p_name = f"세스코 {prod}"
                                break

                        img_bytes = generate_imagen3_flyer(
                            client_genai=client,
                            client_info=target_info,
                            product_name=p_name,
                            summary_text=full_response[:120]
                        )
                        st.image(img_bytes, caption=f"Imagen 3 생성 제안서 포스터 ({p_name})", use_container_width=True)
                        st.download_button(
                            label="📥 제안서 전단지 다운로드 (.jpg)",
                            data=img_bytes,
                            file_name=f"CESCO_{p_name}_Flyer.jpg",
                            mime="image/jpeg",
                            use_container_width=True
                        )

                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"⚠️ 답변 생성 실패: {e}")

    # ==========================================
    # 9. 탭 기반 수동 제안서 생성 센터
    # ==========================================
    st.write("---")
    st.subheader("📋 맞춤형 제안서 센터")
    tab1, tab2 = st.tabs(["📱 카톡 제안서 (마크다운 복사)", "🌿 Imagen 3 전단지 생성"])
    
    with tab1:
        with st.form("auto_kakao_form"):
            c1, c2 = st.columns(2)
            with c1:
                auto_client = st.text_input("고객 대상 (예: 일반 가정집 / 카페)")
                auto_prod = st.text_input("제안 제품 (예: 더슬림 정수기 / 살균방수비데)")
            with c2:
                auto_loc = st.text_input("특징 (예: 신축 아파트 / 위생 강조)")
            submitted_kakao = st.form_submit_button("✨ 카톡 제안서 생성 (400~500자)", use_container_width=True)
            
        if submitted_kakao and auto_client and auto_prod:
            with st.spinner("제안서 작성 중..."):
                prompt_txt = f"대상: {auto_client}, 제품: {auto_prod}, 특징: {auto_loc}. 대상에 맞게 400~500자 카톡 마크다운 제안서를 작성해줘."
                res_k = client.chats.create(model="gemini-3-pro-preview").send_message(prompt_txt).text
                st.code(res_k, language="markdown")

    with tab2:
        with st.form("custom_flyer_form"):
            f_target = st.text_input("대상 (예: 가정집 / 베이커리 카페)")
            f_prod = st.text_input("제품명 (예: 세스코 더슬림 정수기)")
            f_point = st.text_input("강조 포인트 (예: 99.9% 살균 케어 / 슬림 디자인)")
            submitted_flyer = st.form_submit_button("🚀 Imagen 3 전단지 포스터 생성", use_container_width=True)
            
        if submitted_flyer and f_target and f_prod:
            with st.spinner("Imagen 3 고화질 렌더링 중..."):
                img_bytes = generate_imagen3_flyer(
                    client_genai=client,
                    client_info=f_target,
                    product_name=f_prod,
                    summary_text=f_point if f_point else "맞춤형 위생 케어"
                )
                st.image(img_bytes, caption=f"Imagen 3 전단지 ({f_prod})", use_container_width=True)
                st.download_button(
                    label="📥 이미지 다운로드 (.jpg)",
                    data=img_bytes,
                    file_name=f"CESCO_{f_prod}.jpg",
                    mime="image/jpeg",
                    use_container_width=True
                )
else:
    st.error("⚠️ GEMINI_API_KEY가 설정되지 않았습니다.")
