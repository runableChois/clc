import os
import io
import json
import re
import urllib.request
import pandas as pd
from pypdf import PdfReader
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types

# ==========================================
# 1. 페이지 기본 설정 및 모바일 UI 최적화 CSS
# ==========================================
st.set_page_config(
    page_title="영업팀 전용 AI 단가 & 견적 지원 시스템",
    page_icon="💼",
    layout="wide"
)

# 💡 Streamlit Cloud 배지/왕관 아이콘만 핀포인트 제거 스크립트
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
        div[data-testid="stMarkdownContainer"] th, 
        div[data-testid="stMarkdownContainer"] td { padding: 6px 8px !important; }
    }
    
    div[data-testid="stMarkdownContainer"] table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 0.8rem 0 !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
    }
    div[data-testid="stMarkdownContainer"] th {
        background-color: #003b7a !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        padding: 8px 10px !important;
        border: 1px solid #002d5e !important;
        text-align: center !important;
    }
    div[data-testid="stMarkdownContainer"] td {
        padding: 8px 10px !important;
        border: 1px solid #e2e8f0 !important;
        vertical-align: middle !important;
    }
    div[data-testid="stMarkdownContainer"] tr:nth-child(even) {
        background-color: #f8fafc !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 고해상도 그래픽 카드 엔진
# ==========================================
FONT_PATH = "NanumGothic-Bold.ttf"

def ensure_korean_font():
    if not os.path.exists(FONT_PATH):
        font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
        try:
            urllib.request.urlretrieve(font_url, FONT_PATH)
        except Exception as e:
            st.error(f"폰트 다운로드 실패: {e}")

def create_high_res_quote_card(card_data):
    ensure_korean_font()
    width, height = 1200, 1600
    img = Image.new('RGB', (width, height), color='#f1f5f9')
    draw = ImageDraw.Draw(img)
    
    try:
        font_brand = ImageFont.truetype(FONT_PATH, 48)
        font_subhead = ImageFont.truetype(FONT_PATH, 24)
        font_title = ImageFont.truetype(FONT_PATH, 34)
        font_item_name = ImageFont.truetype(FONT_PATH, 30)
        font_price = ImageFont.truetype(FONT_PATH, 36)
        font_regular = ImageFont.truetype(FONT_PATH, 24)
        font_small = ImageFont.truetype(FONT_PATH, 20)
    except:
        font_brand = font_subhead = font_title = font_item_name = font_price = font_regular = font_small = ImageFont.load_default()

    draw.rectangle([(0, 0), (width, 200)], fill='#003b7a')
    draw.rectangle([(0, 190), (width, 200)], fill='#00a3e0')
    draw.text((60, 45), "💎 CESCO 맞춤 솔루션 견적서", fill='#ffffff', font=font_brand)
    draw.text((60, 125), "세스코 공식 단가 기준 | 현장 맞춤 위생 케어 제안", fill='#dbeafe', font=font_subhead)

    draw.rectangle([(50, 240), (width - 50, 370)], fill='#ffffff', outline='#cbd5e1', width=2)
    title_text = card_data.get("title", "맞춤 위생 솔루션 견적")
    draw.text((80, 268), title_text[:30], fill='#0f172a', font=font_title)
    subtitle_text = card_data.get("subtitle", "공식 결합 할인 및 프로모션 혜택 적용")
    draw.text((80, 320), subtitle_text[:40], fill='#64748b', font=font_regular)

    items = card_data.get("items", [])
    y_offset = 400
    for item in items[:4]:
        draw.rectangle([(50, y_offset), (width - 50, y_offset + 140)], fill='#ffffff', outline='#e2e8f0', width=2)
        name = item.get("name", "서비스 항목")
        note = item.get("note", "")
        price = item.get("price", "상담가")

        draw.text((80, y_offset + 30), name[:20], fill='#0f172a', font=font_item_name)
        if note:
            draw.text((80, y_offset + 80), note[:28], fill='#64748b', font=font_small)

        draw.rectangle([(width - 380, y_offset + 30), (width - 80, y_offset + 110)], fill='#eff6ff', outline='#bfdbfe', width=1)
        draw.text((width - 360, y_offset + 48), price, fill='#003b7a', font=font_price)
        y_offset += 160

    promo_text = card_data.get("promotion", "")
    if promo_text:
        draw.rectangle([(50, y_offset + 10), (width - 50, y_offset + 180)], fill='#e0f2fe', outline='#0284c7', width=2)
        draw.text((80, y_offset + 35), "🎁 특별 프로모션 & 결합 혜택", fill='#0369a1', font=font_title)
        draw.text((80, y_offset + 105), promo_text[:45], fill='#0f172a', font=font_regular)

    draw.rectangle([(0, height - 130), (width, height)], fill='#0f172a')
    draw.text((60, height - 95), "📞 서비스 문의 & 무료 현장 진단: 세스코 담당 영업팀", fill='#ffffff', font=font_regular)
    draw.text((60, height - 55), "※ 본 견적은 현장 상황 및 약정 조건에 따라 변동될 수 있습니다.", fill='#94a3b8', font=font_small)
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# ==========================================
# 3. 데이터 I/O 함수
# ==========================================
DATA_FILE_PATH = "saved_data_context.txt"
NAME_FILE_PATH = "saved_data_name.txt"
SALES_LOG_PATH = "sales_activity_log.csv"
EQUIPMENT_LOG_PATH = "team_equipment_inventory.csv"

def load_master_data():
    if os.path.exists(DATA_FILE_PATH) and os.path.exists(NAME_FILE_PATH):
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            context = f.read()
        with open(NAME_FILE_PATH, "r", encoding="utf-8") as f:
            filename = f.read()
        return context, filename
    return "", None

def save_master_data(context, filename):
    with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(context)
    with open(NAME_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(filename)

def delete_master_data():
    if os.path.exists(DATA_FILE_PATH):
        os.remove(DATA_FILE_PATH)
    if os.path.exists(NAME_FILE_PATH):
        os.remove(NAME_FILE_PATH)

def save_sales_log(member_name, client_name, proposed_deal, equipment_status, equipment_item, reaction, memo):
    new_data = pd.DataFrame([{
        "작성일시": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "담당플래너": member_name,
        "고객/매장명": client_name,
        "제안서비스/견적가": proposed_deal,
        "체험장비설치": equipment_status,
        "설치장비품목": equipment_item if equipment_status == "설치 완료" else "-",
        "고객반응/상태": reaction,
        "영업메모": memo
    }])
    if os.path.exists(SALES_LOG_PATH):
        old_df = pd.read_csv(SALES_LOG_PATH)
        # 하위 호환 컬럼 변경
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
        {"담당플래너": "홍길동", "보유대수": 5},
        {"담당플래너": "김철수", "보유대수": 3},
        {"담당플래너": "이영희", "보유대수": 4}
    ])
    default_df.to_csv(EQUIPMENT_LOG_PATH, index=False, encoding="utf-8-sig")
    return default_df

def save_equipment_inventory(df):
    df.to_csv(EQUIPMENT_LOG_PATH, index=False, encoding="utf-8-sig")

def process_file_content(uploaded_file):
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
        for idx, page in enumerate(reader.pages, start=1):
            extracted_text += f"\n[PDF Page {idx}]\n" + page.extract_text() + "\n"

    return extracted_text, filename

file_context, uploaded_filename = load_master_data()

# ==========================================
# 4. 사이드바 UI
# ==========================================
with st.sidebar:
    st.header("⚙️ 영업 모드 설정")
    
    role_option = st.selectbox(
        "AI 영업 파트너 모드:",
        ["견적 & 요금 비교 전문가", "거절 대응 & 셀링포인트 안내", "자유 질문 모드"]
    )
    
    if role_option == "견적 & 요금 비교 전문가":
        base_instruction = (
            "당신은 영업 플래너를 보조하는 세스코 견적 및 요금 안내 전문 컨설턴트입니다.\n"
            "등록된 단가표 데이터를 바탕으로 정확한 제품명, 스펙, 요금을 신속히 안내하세요.\n"
            "핵심 단독가, 결합가, 프로모션가를 마크다운 표(Table)와 요약 불렛포인트로 간결하고 짧게 작성하세요."
        )
    elif role_option == "거절 대응 & 셀링포인트 안내":
        base_instruction = (
            "당신은 베테랑 영업 멘토입니다.\n"
            "플래너가 고객의 거절 반응을 입력하면, 핵심 반박 논리와 차별점을 3줄 이내로 핵심만 알려주세요."
        )
    else:
        base_instruction = "당신은 유능하고 친절한 AI 영업 보조입니다. 답변은 간결하게 작성하세요."

    st.divider()
    st.subheader("📊 학습 단가표 상태")
    if uploaded_filename:
        st.success(f"**적용 중:** `{uploaded_filename}`")
    else:
        st.info("현재 등록된 마스터 단가표가 없습니다.")

    st.divider()
    st.subheader("🔑 관리자 패널")
    admin_password_secret = st.secrets.get("ADMIN_PASSWORD", "1234")
    input_pwd = st.text_input("비밀번호 입력:", type="password")
    
    if input_pwd == admin_password_secret:
        st.success("🔓 관리자 권한 활성화됨")
        
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📊 영업 대시보드", "📦 체험장비 보유/설치 관리", "📁 단가표 관리"])
        
        # 📊 [1. 대시보드 탭]
        with admin_tab1:
            st.write("📈 **실시간 영업 성과 대시보드**")
            
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
                merged_inv["잔여재고"] = merged_inv["보유대수"] - merged_inv["설치대수"]
                merged_inv["설치활동률(%)"] = (merged_inv["설치대수"] / merged_inv["보유대수"] * 100).round(1)
                
                st.subheader("1️⃣ 플래너별 체험장비 보유/설치/잔여재고 현황")
                st.dataframe(merged_inv[["담당플래너", "보유대수", "설치대수", "잔여재고", "설치활동률(%)"]], use_container_width=True)
                
                chart_data = merged_inv.set_index("담당플래너")[["보유대수", "설치대수", "잔여재고"]]
                st.bar_chart(chart_data)
                
                st.divider()
                st.subheader("2️⃣ 체험장비 설치 후 계약 성사율 분석")
                
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
                st.subheader("3️⃣ 인기 제안 상품 & 서비스 순위")
                product_counts = logs_df["제안서비스/견적가"].value_counts().head(5)
                st.bar_chart(product_counts)
                
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

        # 📦 [2. 체험장비 보유 및 설치 상세 관리 탭]
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
                    display_cols = ["작성일시", "담당플래너", "고객/매장명", "설치장비품목", "고객반응/상태", "영업메모"]
                    st.dataframe(installed_logs[display_cols], use_container_width=True)
                else:
                    st.info("현재 현장에 설치된 체험장비 내역이 없습니다.")
            else:
                st.info("기록된 영업일지가 없습니다.")
                
            st.divider()
            
            st.subheader("⚙️ 2. 플래너별 체험장비 보유 대수 수정")
            current_inv = load_equipment_inventory()
            
            edited_df = st.data_editor(current_inv, num_rows="dynamic", use_container_width=True)
            if st.button("💾 보유 대수 수정사항 저장", use_container_width=True):
                save_equipment_inventory(edited_df)
                st.toast("✅ 플래너별 체험장비 보유 대수가 업데이트되었습니다!", icon="🎉")
                st.rerun()

        # 📁 [3. 단가표 관리 탭]
        with admin_tab3:
            new_file = st.file_uploader("새 단가표 (시트 1 작성 엑셀/PDF)", type=["xlsx", "csv", "pdf"])
            if new_file and st.button("💾 마스터 데이터로 반영", use_container_width=True):
                try:
                    with st.spinner("단가표 분석 및 저장 중..."):
                        parsed_text, fname = process_file_content(new_file)
                        save_master_data(parsed_text, fname)
                        st.toast("✅ 새 마스터 단가표 적용 완료!", icon="🎉")
                        st.rerun()
                except Exception as e:
                    st.error(f"⚠️ 파일 처리 오류: {e}")
                    
            if uploaded_filename and st.button("🗑️ 등록 데이터 삭제", use_container_width=True, type="secondary"):
                delete_master_data()
                st.toast("등록 데이터 삭제 완료!", icon="🧹")
                st.rerun()
    elif input_pwd:
        st.error("비밀번호 불일치")
    else:
        st.caption("관리자만 영업 대시보드 및 단가표 관리가 가능합니다.")

    st.divider()
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 5. 메인 화면 & 챗봇 인터페이스
# ==========================================
st.title("💼 우리 팀 세스코 영업지원 AI")

if uploaded_filename:
    st.caption(f"📌 **참조 단가표:** {uploaded_filename}")
else:
    st.caption("📌 **참조 단가표 없음** | 기본 지식 모드")

st.divider()

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    selected_faq = None
    st.write("💡 **빠른 단가 조회:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 15평 매장 단독/결합가 비교", use_container_width=True):
            selected_faq = "15평 매장 기준 단독가, 결합가, 프로모션가를 핵심만 간결하게 표로 비교해줘."
    with col2:
        if st.button("🛡️ 타사 대비 핵심 강점 보기", use_container_width=True):
            selected_faq = "타사 대비 세스코 핵심 차별점 3가지를 짧고 강력하게 정리해줘."
    with col3:
        if st.button("🎁 이번 달 프로모션 혜택", use_container_width=True):
            selected_faq = "이번 달 프로모션 할인 혜택과 주요 단가를 간결하게 보여줘."

    st.write("---")
    
    with st.expander("📸 **현장 해충/매장 사진 추천받기**"):
        uploaded_img = st.file_uploader("현장 사진 첨부", type=["jpg", "jpeg", "png"])
        if uploaded_img:
            st.image(uploaded_img, caption="첨부된 사진", width=200)

    prompt_input = st.chat_input("질문 입력... (예: 25평 식당 결합가 얼마야?)")
    user_prompt = selected_faq if selected_faq else prompt_input

    if user_prompt:
        st.chat_message("user").markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        final_system_instruction = base_instruction
        if file_context:
            final_system_instruction += (
                f"\n\n[참조 단가표 ({uploaded_filename})]\n"
                "아래 단가표에서 핵심 요금만 정확히 찾아 **간결하게** 답변하세요:\n\n"
                f"{file_context}"
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
                
                if uploaded_img:
                    img_obj = Image.open(uploaded_img)
                    send_contents = [user_prompt, img_obj]
                else:
                    send_contents = user_prompt

                response_stream = chat.send_message_stream(send_contents)
                
                def stream_generator():
                    for chunk in response_stream:
                        yield chunk.text

                full_response = st.write_stream(stream_generator())
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ 답변 생성 실패: {e}")

    # ==========================================
    # 📱 [300자 제한] 카톡 요약문 & 카드 생성
    # ==========================================
    st.write("---")
    if len(st.session_state.messages) > 0:
        if st.button("📱 **간결한 카톡 제안서 & 카드 이미지 생성**", use_container_width=True):
            with st.spinner("300자 이내 카톡 메시지 및 고해상도 카드 제작 중..."):
                try:
                    recent_chat = st.session_state.messages[-1]["content"]
                    
                    summary_prompt = (
                        f"다음 견적 내용을 바탕으로 카카오톡 전송용 메시지를 작성해 줘.\n"
                        f"[작성 조건]\n"
                        f"1. 전체 글자 수는 공백 포함 **최대 300자 이내**로 매우 간결하게 작성할 것.\n"
                        f"2. 인사말은 1줄로 최소화하고 [매장명/추천서비스/월단가/주요혜택]만 불렛포인트로 명확히 적을 것.\n"
                        f"3. 한눈에 읽기 쉬운 카톡 전송용으로 만들 것.\n\n"
                        f"견적 내용:\n{recent_chat}"
                    )
                    chat = client.chats.create(model="gemini-3-flash-preview")
                    text_res = chat.send_message(summary_prompt)
                    
                    st.subheader("📱 **1. 카톡 전송용 간결 메시지 (복사용)**")
                    st.code(text_res.text, language="text")
                    
                    json_prompt = (
                        f"다음 견적 내용에서 핵심 서비스와 요금 정보만 추출하여 오직 JSON으로 응답해 줘.\n"
                        f"JSON 예시:\n"
                        f"{{\n"
                        f'  "title": "15평 매장 맞춤 위생 솔루션",\n'
                        f'  "subtitle": "공식 결합 할인 적용가",\n'
                        f'  "items": [\n'
                        f'    {{"name": "보일러/유충 방제", "price": "45,000원/월", "note": "월 1회 점검"}},\n'
                        f'    {{"name": "바이러스케어", "price": "30,000원/월", "note": "결합 할인가"}}\n'
                        f'  ],\n'
                        f'  "promotion": "초기 설치비 면제 혜택"\n'
                        f"}}\n\n"
                        f"견적 내용:\n{recent_chat}"
                    )
                    json_res = chat.send_message(json_prompt)
                    
                    json_match = re.search(r'\{.*\}', json_res.text, re.DOTALL)
                    if json_match:
                        card_data = json.loads(json_match.group())
                    else:
                        card_data = {
                            "title": "세스코 맞춤 솔루션 견적",
                            "subtitle": "공식 단가 기준 안내",
                            "items": [{"name": "맞춤 위생 서비스", "price": "상담가", "note": "상세 문의"}],
                            "promotion": "프로모션 및 결합 할인 조건 적용 가능"
                        }
                    
                    st.subheader("🖼️ **2. 완성형 이미지 견적 카드**")
                    card_img_bytes = create_high_res_quote_card(card_data)
                    st.image(card_img_bytes, caption="모바일 전용 초고해상도 견적 카드 (1200x1600)", use_container_width=True)
                    st.download_button(
                        label="📥 **고해상도 견적 카드 다운로드 (.png)**",
                        data=card_img_bytes,
                        file_name="세스코_고해상도_견적카드.png",
                        mime="image/png",
                        use_container_width=True
                    )
                except Exception as img_err:
                    st.error(f"⚠️ 생성 중 오류 발생: {img_err}")

    # ==========================================
    # 📝 현장 영업일지 기록 (플래너 명칭 적용)
    # ==========================================
    with st.expander("📝 **플래너 현장 영업 미팅 일지 기록하기**"):
        st.caption("오늘 방문한 매장/고객과의 상담 내역을 기록하면 전체 영업 대장에 저장됩니다.")
        with st.form("sales_log_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                m_name = st.text_input("담당 플래너 이름 * (예: 홍길동)")
                c_name = st.text_input("방문 매장/고객명 * (예: 대박식당)")
                p_deal = st.text_input("제안 서비스 및 견적가 (예: 방제+바이러스 결합 월 65,000원)")
            with col_b:
                eq_status = st.selectbox("🎁 체험장비 설치 여부", ["미설치", "설치 완료"])
                eq_item = st.text_input("설치한 체험장비 품목 (예: 공기살균기 B타입, 포충기 등)")
                reaction = st.selectbox("고객 반응/상태", ["계약 완료 🎉", "긍정적 (계약 임박)", "검토 중 (재방문 필요)", "보류 (가격 부담)"])
                memo = st.text_input("영업 메모 (예: 다음 주 화요일에 사장님 재방문 예정)")
                
            submit_log = st.form_submit_button("💾 영업일지 저장하기", use_container_width=True)
            if submit_log:
                if m_name and c_name:
                    save_sales_log(m_name, c_name, p_deal, eq_status, eq_item, reaction, memo)
                    st.success("🎉 영업일지가 성공적으로 저장되었습니다!")
                else:
                    st.warning("⚠️ 필수 항목(플래너 이름, 고객명)을 입력해 주세요.")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
