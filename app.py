import os
import io
import json
import re
import urllib.request
import pandas as pd
from pypdf import PdfReader # PDF 리더 라이브러리 (필수)
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types

# ==========================================
# 1. 페이지 기본 설정 및 모바일 UI 최적화 CSS
# ==========================================
st.set_page_config(
    page_title="세스코 플래너 Pro - 제품 학습 모드",
    page_icon="💼",
    layout="wide"
)

# Streamlit 배지 제거 CSS (유지)
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
# 2. 이미지 생성 엔진 (복원 - 유지)
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
    draw.text((60, 125), "세스코 공식 문서 기반 | 현장 맞춤 케어 제안", fill='#dbeafe', font=font_subhead)

    draw.rectangle([(50, 240), (width - 50, 370)], fill='#ffffff', outline='#cbd5e1', width=2)
    
    title_text = card_data.get("title", "맞춤 위생 솔루션 견적")
    draw.text((80, 268), title_text[:30], fill='#0f172a', font=font_title)
    
    subtitle_text = card_data.get("subtitle", "공식 문서 데이터 기준")
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
    draw.text((60, height - 95), "📞 서비스 문의 및 신청: 세스코 담당 플래너", fill='#ffffff', font=font_regular)
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# ==========================================
# 3. [핵심] 문서 학습 및 I/O 함수
# ==========================================
# 학습된 텍스트 데이터를 상시 보관할 파일 경로
KNOWLEDGE_BASE_PATH = "cesco_knowledge_base.txt"
# 학습된 파일의 원본 이름을 기억할 파일 경로
KNOWLEDGE_NAME_PATH = "cesco_knowledge_name.txt"
SALES_LOG_PATH = "sales_activity_log.csv"
EQUIPMENT_LOG_PATH = "team_equipment_inventory.csv"

def load_knowledge_data():
    """저장된 문서 학습 데이터를 불러옵니다."""
    if os.path.exists(KNOWLEDGE_BASE_PATH) and os.path.exists(KNOWLEDGE_NAME_PATH):
        with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
            context = f.read()
        with open(KNOWLEDGE_NAME_PATH, "r", encoding="utf-8") as f:
            filename = f.read()
        return context, filename
    return "", None

def save_knowledge_data(context, filename):
    """문서에서 추출한 텍스트를 로컬 DB에 저장합니다."""
    with open(KNOWLEDGE_BASE_PATH, "w", encoding="utf-8") as f:
        f.write(context)
    with open(KNOWLEDGE_NAME_PATH, "w", encoding="utf-8") as f:
        f.write(filename)

def delete_knowledge_data():
    """저장된 학습 데이터를 삭제합니다."""
    if os.path.exists(KNOWLEDGE_BASE_PATH):
        os.remove(KNOWLEDGE_BASE_PATH)
    if os.path.exists(KNOWLEDGE_NAME_PATH):
        os.remove(KNOWLEDGE_NAME_PATH)

def process_uploaded_file(uploaded_file):
    """[핵심] PDF/엑셀 파일을 AI 학습용 텍스트로 변환합니다."""
    extracted_text = ""
    filename = uploaded_file.name

    if filename.endswith(('.xlsx', '.xls')):
        # 엑셀 파일 처리 (유지)
        df = pd.read_excel(uploaded_file, sheet_name=0)
        df = df.dropna(how="all")
        extracted_text = df.to_markdown(index=False)
        
    elif filename.endswith('.csv'):
        # CSV 파일 처리 (유지)
        df = pd.read_csv(uploaded_file)
        df = df.dropna(how="all")
        extracted_text = df.to_markdown(index=False)
        
    elif filename.endswith('.pdf'):
        # PDF 파일 처리 (고도화 - pypdf 활용)
        reader = PdfReader(uploaded_file)
        full_text = ""
        # 💡 [고도화] 전체 페이지를 순회하며 텍스트 추출
        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text:
                full_text += f"\n--- [PDF Page {idx}] ---\n" + text + "\n"
        extracted_text = full_text

    return extracted_text, filename

# 💡 [핵심] 앱 시작 시 학습 데이터를 메모리에 상시 로드
knowledge_context, learned_filename = load_knowledge_data()

# ==========================================
# 4. 사이드바 UI (관리자 학습 기능 추가)
# ==========================================
with st.sidebar:
    st.header("⚙️ 영업 모드 설정")
    
    role_option = st.selectbox(
        "AI 영업 파트너 모드:",
        ["견적 & 요금 비교 전문가 (학습 문서 기반)", "상권 분석 & 영업지 선정 전문가", "거절 대응 & 셀링포인트 안내", "자유 질문 모드"]
    )
    
    # 💡 [고도화] AI 프롬프트에 3단계 스스로 점검 로직 주입
    if role_option == "견적 & 요금 비교 전문가 (학습 문서 기반)":
        base_instruction = (
            "당신은 영업 플래너를 보조하는 세스코 초정밀 견적 및 제품 안내 전문 컨설턴트입니다.\n"
            "[작성 논리 및 점검 수칙 (필수)]\n"
            "1. 고객의 질문이나 사진(해충 식별 포함)을 분석하세요.\n"
            "2. 하단에 제공된 [업로드된 학습 문서 데이터] 안에서만 답변을 찾으세요. 절대로 없는 내용을 지어내지 마세요 (No Hallucination).\n"
            "3. 답변을 출력하기 전, 아래 3단계 스스로 점검(Self-Correction) 과정을 거치세요:\n"
            "   - 1단계 (유무 확인): 제안하려는 제품과 서비스가 실제 문서에 존재하는가?\n"
            "   - 2단계 (정확성 확인): 제안하는 가격(단독가, 결합가 등)과 약정 조건이 문서와 완벽히 일치하는가?\n"
            "   - 3단계 (적합성 확인): 고객의 평수, 업종, 해충 문제에 가장 적합한 제안인가?\n"
            "4. 모바일 화면 가독성을 위해 인사말은 생략하고, 핵심 제안과 표, 불렛포인트로 간결하고 정확하게 답변하세요.\n"
            "5. 답변 본문에는 이미지를 첨부하지 마세요."
        )
    elif role_option == "상권 분석 & 영업지 선정 전문가":
        base_instruction = (
            "당신은 영업 플래너의 효과적인 영업 활동을 돕는 데이터 기반 상권 분석 전문가입니다.\n"
            "플래너가 특정 지역이나 상권을 입력하면, 당신의 광범위한 외부 지식을 활용하여 해당 상권을 철저히 분석하세요.\n"
            "[상권 분석 지침 (필수)]\n"
            "1. 업종 분포 분석: 해당 지역의 주요 포진 업종(예: 요식업, 오피스, 병원 등)과 그 특징을 분석하세요.\n"
            "2. 업종별 타겟 제품 제안: 요식업엔 방제+포충기, 오피스엔 공기살균기 등 상권 주요 업종에 최적화된 세스코 서비스를 추천하세요.\n"
            "3. 영업 전략 포인트 (데이터 기반 추정): 대략적인 매출 규모(추정치), 유동인구 특징, 최근 오픈 트렌드 등을 종합하여 '가장 계약 확률이 높은 영업 우선순위 장소'와 접근 전략을 3줄 이내로 핵심만 제안하세요.\n"
            "4. 장황한 설명 대신 인포그래픽형 텍스트와 불렛포인트로 간결하게 출력하세요."
        )
    else:
        base_instruction = "당신은 유능하고 친절한 AI 영업 보조입니다. 답변은 간결하게 작성하세요."

    st.divider()
    # 💡 [핵심] 현재 어떤 문서를 학습하고 있는지 상태 표시
    st.subheader("📚 현재 AI 학습 문서 상태")
    if learned_filename:
        st.success(f"**학습 완료:** `{learned_filename}`")
    else:
        st.info("현재 학습된 제품/단가표 문서가 없습니다.")

    st.divider()
    st.subheader("🔑 관리자 패널")
    admin_password_secret = st.secrets.get("ADMIN_PASSWORD", "1234")
    input_pwd = st.text_input("비밀번호 입력:", type="password")
    
    if input_pwd == admin_password_secret:
        st.success("🔓 관리자 권한 활성화됨")
        
        # 관리자 기능을 탭으로 정리
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📊 영업 대시보드", "📦 체험장비 관리", "📁 **AI 문서 학습(PDF)**"])
        
        with admin_tab1: st.write("실시간 대시보드 (유지)") # (대시보드 코드는 기존과 동일하므로 생략)
        with admin_tab2: st.write("체험장비 관리 (유지)") # (체험장비 코드는 기존과 동일하므로 생략)

        # 💡 [핵심탭] 📁 AI 문서 학습(PDF)
        with admin_tab3:
            st.subheader("📁 제품 정보 및 단가표 문서(PDF) 학습시키기")
            st.caption("PDF, 엑셀, CSV 파일을 업로드하면 AI가 분석하여 답변 시 최우선으로 참조합니다.")
            
            # 파일 업로더
            new_file = st.file_uploader("새 제품 문서 업로드", type=["pdf", "xlsx", "csv"])
            
            # 학습 버튼
            if new_file and st.button("💾 이 문서를 AI에게 학습시키기", use_container_width=True):
                try:
                    with st.spinner("AI가 문서를 정밀 분석 및 학습 중입니다. 잠시만 기다려주세요..."):
                        # [핵심] 문서 처리 함수 호출
                        parsed_text, fname = process_uploaded_file(new_file)
                        # 로컬 DB에 저장
                        save_knowledge_data(parsed_text, fname)
                        
                        st.toast(f"✅ `{fname}` 문서 학습 완료!", icon="🎉")
                        # 학습 데이터를 메모리에 즉시 반영하기 위해 리런
                        st.rerun()
                except Exception as e:
                    st.error(f"⚠️ 문서 처리 중 오류 발생: {e}")
                    
            # 삭제 버튼
            if learned_filename and st.button("🗑️ 등록된 학습 데이터 삭제", use_container_width=True, type="secondary"):
                delete_knowledge_data()
                st.toast("등록된 학습 데이터 삭제 완료!", icon="🧹")
                st.rerun()
    elif input_pwd:
        st.error("비밀번호 불일치")
    else:
        st.caption("관리자만 영업 대시보드 및 AI 문서 학습 관리가 가능합니다.")

    st.divider()
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 5. 메인 화면 & 챗봇 인터페이스 (고도화 반영)
# ==========================================
st.title("💼 우리 팀 세스코 영업지원 AI (Pro)")

# 학습 상태 메인 화면 표시 (유지)
if learned_filename:
    st.caption(f"📌 **참조 학습 문서:** {learned_filename} | AI 고도화(사진 진단 & 3-Step 점검) 모드")
else:
    st.caption("📌 **참조 단가표 없음** | 상권 분석 & 외부 지식 모드")

st.divider()

# (챗봇 인터페이스 코드는 기존과 동일하므로 생략, 💡[핵심] Gemini 전송 로직만 수정)
# ... (메시지 표시 및 입력 코드 동일) ...

    prompt_input = st.chat_input("질문을 입력하세요... (예: 사진 속 해충 뭐고 얼마야? 또는 성수동 상권 알려줘)")
    # (유저 프롬프트 처리 코드 동일) ...

    if user_prompt:
        st.chat_message("user").markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        # ... (히스토리 구성 코드 동일) ...

        # API 호출 전 시스템 프롬프트 확정 (💡 고도화 로직 주입)
        final_system_instruction = base_instruction
        
        # 💡 [핵심] 학습된 문서 데이터가 있다면, AI 프롬프트 하단에 '학습 내용'으로 주입
        if role_option == "견적 & 요금 비교 전문가 (학습 문서 기반)" and knowledge_context:
            final_system_instruction += (
                f"\n\n[업로드된 학습 문서 데이터 ({learned_filename})]\n"
                "가장 중요한 정보입니다. 답변 시 반드시 이 내용 안에서만 찾고 3번 점검하세요:\n\n"
                f"{knowledge_context}"
            )
            
        # 📸 [멀티모달 이미지 진단 프롬프트] (유지)
        if uploaded_img:
            final_system_instruction += (
                "\n\n[사진 진단 모드]\n"
                "사용자가 첨부한 현장 사진을 보고 어떤 해충인지 식별하거나, 매장/주방의 위생 상태를 진단하세요. "
                "진단 내용을 바탕으로 [업로드된 학습 문서 데이터]에서 적합한 서비스를 추천하고 정확한 가격을 안내하세요."
            )

        with st.chat_message("assistant"):
            try:
                # 💡 [핵심] 고도화된 프롬프트를 처리하기 위해 Gemini 1.5 Pro 모델 사용
                chat = client.chats.create(
                    model="gemini-1.5-pro-latest", 
                    config=types.GenerateContentConfig(
                        system_instruction=final_system_instruction
                    ),
                    history=history
                )
                
                # ... (이미지 및 텍스트 전송 로직 동일) ...
                # ... (스트리밍 답변 출력 및 리런 코드 동일) ...

# ==========================================
# 📱 [300자 제한] 카톡 요약문 & 카드 생성 (복원된 기능 유지)
# ==========================================
# ... (기존 7일차 이미지 카드 생성 코드 동일) ...

# 📝 현장 영업일지 기록 (유지)
# ... (기존 동적 재고 관리 포함된 영업일지 코드 동일) ...
