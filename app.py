import os
import pandas as pd
from pypdf import PdfReader
import streamlit as st
from google import genai
from google.genai import types

# ==========================================
# 1. 페이지 기본 설정 및 디자인 (Custom CSS)
# ==========================================
st.set_page_config(
    page_title="세스코 맞춤 단가 & 견적 안내 AI",
    page_icon="💎",
    layout="wide"
)

# 세련된 웹앱 UI 스타일링
st.markdown("""
<style>
    /* 메인 폰트 및 배경 여백 조정 */
    .main { padding: 1.5rem 2rem; }
    
    /* 카드형 컨테이너 스타일 */
    .status-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        border-left: 5px solid #0d6efd;
        margin-bottom: 1rem;
    }
    
    /* 마크다운 표 디자인 커스텀 (가독성 최적화) */
    div[data-testid="stMarkdownContainer"] table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 1rem 0 !important;
        font-size: 14.5px !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
    }
    div[data-testid="stMarkdownContainer"] th {
        background-color: #0f172a !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        padding: 12px 16px !important;
        border: 1px solid #1e293b !important;
        text-align: center !important;
    }
    div[data-testid="stMarkdownContainer"] td {
        padding: 11px 16px !important;
        border: 1px solid #e2e8f0 !important;
        vertical-align: middle !important;
    }
    div[data-testid="stMarkdownContainer"] tr:nth-child(even) {
        background-color: #f8fafc !important;
    }
    div[data-testid="stMarkdownContainer"] tr:hover {
        background-color: #f1f5f9 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 마스터 데이터 관리 파일 I/O 함수
# ==========================================
DATA_FILE_PATH = "saved_data_context.txt"
NAME_FILE_PATH = "saved_data_name.txt"

def load_master_data():
    """서버에 저장된 마스터 단가 데이터 불러오기"""
    if os.path.exists(DATA_FILE_PATH) and os.path.exists(NAME_FILE_PATH):
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            context = f.read()
        with open(NAME_FILE_PATH, "r", encoding="utf-8") as f:
            filename = f.read()
        return context, filename
    return "", None

def save_master_data(context, filename):
    """서버에 마스터 단가 데이터 저장"""
    with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(context)
    with open(NAME_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(filename)

def delete_master_data():
    """서버의 마스터 단가 데이터 삭제"""
    if os.path.exists(DATA_FILE_PATH):
        os.remove(DATA_FILE_PATH)
    if os.path.exists(NAME_FILE_PATH):
        os.remove(NAME_FILE_PATH)

def process_file_content(uploaded_file):
    """업로드된 파일(시트 1 중심 엑셀, CSV, PDF)을 마크다운 텍스트로 변환"""
    extracted_text = ""
    filename = uploaded_file.name

    if filename.endswith(('.xlsx', '.xls')):
        # 첫 번째 시트(Sheet 1)를 정밀하게 읽어옴
        df = pd.read_excel(uploaded_file, sheet_name=0)
        # 빈 줄 및 불필요 열 제거 정리
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

# 초기 데이터 로드
file_context, uploaded_filename = load_master_data()

# ==========================================
# 3. 사이드바 (설정 & 관리자 메뉴)
# ==========================================
with st.sidebar:
    st.header("⚙️ 서비스 설정")
    
    # 페르소나 및 역할 지정
    role_option = st.selectbox(
        "AI 프롬프트 모드:",
        ["견적 & 요금 비교 전문가", "비즈니스 마케팅 컨설턴트", "자유 질문 모드"]
    )
    
    if role_option == "견적 & 요금 비교 전문가":
        base_instruction = (
            "당신은 세스코 견적 및 요금 안내 전문 컨설턴트입니다.\n"
            "등록된 단가표 데이터를 바탕으로 정확한 제품명, 스펙, 요금을 안내하세요.\n"
            "가격 문의 시 **'단독가', '결합가', '프로모션가'**가 존재하는 경우, "
            "이를 한눈에 볼 수 있도록 마크다운 표(Table)로 명확히 비교하고 "
            "약정 및 제휴 조건 등 적용 조건을 함께 안내하세요."
        )
    elif role_option == "비즈니스 마케팅 컨설턴트":
        base_instruction = (
            "당신은 세스코 서비스 비즈니스 마케팅 컨설턴트입니다.\n"
            "등록된 단가 및 서비스 특징을 바탕으로 설득력 있는 고객 제안서와 셀링 포인트를 작성하세요."
        )
    else:
        base_instruction = "당신은 유능하고 친절한 AI 비즈니스 보조입니다."

    st.divider()
    
    # 마스터 데이터 상태 표시
    st.subheader("📊 학습 데이터 상태")
    if uploaded_filename:
        st.success(f"**적용 중:** `{uploaded_filename}`")
    else:
        st.info("현재 등록된 마스터 파일이 없습니다.")

    st.divider()
    
    # 관리자 인증 & 단가표 변경 섹션
    st.subheader("🔑 관리자 패널")
    admin_password_secret = st.secrets.get("ADMIN_PASSWORD", "1234")
    input_pwd = st.text_input("비밀번호 입력:", type="password")
    
    if input_pwd == admin_password_secret:
        st.caption("🔓 관리자 권한이 활성화되었습니다.")
        
        new_file = st.file_uploader("새 단가표 (시트 1 작성 엑셀/PDF)", type=["xlsx", "csv", "pdf"])
        
        if new_file and st.button("💾 마스터 데이터로 반영", use_container_width=True):
            try:
                with st.spinner("단가표 분석 및 데이터 저장 중..."):
                    parsed_text, fname = process_file_content(new_file)
                    save_master_data(parsed_text, fname)
                    st.toast("✅ 새 마스터 단가표 적용 완료!", icon="🎉")
                    st.rerun()
            except Exception as e:
                st.error(f"⚠️ 파일 처리 중 오류 발생: {e}")
                
        if uploaded_filename and st.button("🗑️ 등록 데이터 삭제", use_container_width=True, type="secondary"):
            delete_master_data()
            st.toast("등록된 데이터가 삭제되었습니다.", icon="🧹")
            st.rerun()
    elif input_pwd:
        st.error("비밀번호가 일치하지 않습니다.")
    else:
        st.caption("단가표 업데이트는 관리자만 가능합니다.")

    st.divider()
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 4. 메인 화면 & 챗봇 인터페이스
# ==========================================
st.title("💎 세스코 서비스 & 단가 안내 AI")

if uploaded_filename:
    st.caption(f"📌 **참조 문서:** {uploaded_filename} | 시트 1 기반 정밀 검색 작동 중")
else:
    st.caption("📌 **참조 문서 없음** | 기본 지식 기반으로 대답 중입니다.")

st.divider()

# API 키 및 클라이언트 초기화
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    # 대화 기록 초기화 및 출력
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 사용자 질문 입력
    if prompt := st.chat_input("궁금한 서비스나 평형별 단가를 물어보세요 (예: 15평 매장 방제 단독가 및 결합가 비교해줘)"):
        # 유저 메시지 표시 및 저장
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 대화 히스토리 구성
        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        # 최종 시스템 instruction 결합
        final_system_instruction = base_instruction
        if file_context:
            final_system_instruction += (
                f"\n\n[참조 마스터 데이터 (파일명: {uploaded_filename})]\n"
                "아래는 관리자가 직접 등록한 최신 서비스 단가표 데이터입니다. "
                "사용자의 요금 및 스펙 질문에는 반드시 아래 표 데이터에서 단독가, 결합가, 프로모션가를 찾아 정확하게 답변하세요:\n\n"
                f"{file_context}"
            )

        # AI 답변 생성
        with st.chat_message("assistant"):
            with st.spinner("단가표 데이터를 분석 중입니다..."):
                try:
                    chat = client.chats.create(
                        model="gemini-3-flash-preview",
                        config=types.GenerateContentConfig(
                            system_instruction=final_system_instruction
                        ),
                        history=history
                    )
                    response = chat.send_message(prompt)
                    st.markdown(response.text)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"⚠️ 답변 생성 실패: {e}")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
