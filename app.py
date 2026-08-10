import streamlit as st
import pandas as pd
from pypdf import PdfReader
from google import genai
from google.genai import types
import os

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="세스코 단가 안내 AI 서비스", page_icon="🤖", layout="wide")

# 🎨 표(Table) 가독성 향상 커스텀 CSS
st.markdown("""
<style>
    div[data-testid="stMarkdownContainer"] table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 15px 0 !important;
        font-size: 15px !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
    }
    div[data-testid="stMarkdownContainer"] th {
        background-color: #f0f2f6 !important;
        color: #1f1f1f !important;
        font-weight: 700 !important;
        padding: 12px 16px !important;
        border: 1px solid #d0d7de !important;
        text-align: center !important;
    }
    div[data-testid="stMarkdownContainer"] td {
        padding: 10px 16px !important;
        border: 1px solid #e1e4e8 !important;
        vertical-align: middle !important;
    }
    div[data-testid="stMarkdownContainer"] tr:nth-child(even) {
        background-color: #f8f9fa !important;
    }
</style>
""", unsafe_allow_html=True)

# 2. 서버 내 파일 저장 경로 설정 (모든 유저가 공유할 Master 데이터)
DATA_FILE_PATH = "saved_data_context.txt"
NAME_FILE_PATH = "saved_data_name.txt"

# 저장된 서버 데이터 불러오기 함수
def load_server_data():
    if os.path.exists(DATA_FILE_PATH) and os.path.exists(NAME_FILE_PATH):
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            context = f.read()
        with open(NAME_FILE_PATH, "r", encoding="utf-8") as f:
            filename = f.read()
        return context, filename
    return "", None

# 서버 데이터 저장 함수
def save_server_data(context, filename):
    with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(context)
    with open(NAME_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(filename)

# 서버 데이터 삭제 함수
def delete_server_data():
    if os.path.exists(DATA_FILE_PATH):
        os.remove(DATA_FILE_PATH)
    if os.path.exists(NAME_FILE_PATH):
        os.remove(NAME_FILE_PATH)

# 데이터 로드
file_context, uploaded_filename = load_server_data()

# 3. 사이드바 UI 구성
with st.sidebar:
    st.title("⚙️ 설정 및 안내")
    
    # AI 역할 선택
    role_option = st.selectbox(
        "AI의 역할을 선택하세요:",
        ["견적 및 가격 비교 전문가", "비즈니스 마케팅 전문가", "IT/코딩 전문 개발자", "직접 입력"]
    )
    
    if role_option == "견적 및 가격 비교 전문가":
        base_instruction = "당신은 견적 및 가격 비교 전문가입니다. 사용자가 질문하면 등록된 단가표/PDF 데이터를 최우선으로 참고하여 마크다운 표(Table) 형태로 품목, 단가, 상세 스펙 등을 깔끔하게 정리하여 답변하세요."
    elif role_option == "비즈니스 마케팅 전문가":
        base_instruction = "당신은 베테랑 마케팅 컨설턴트입니다. 등록된 제품 단가 및 스펙 데이터를 바탕으로 마케팅 전략과 제안서를 작성해 주세요."
    elif role_option == "IT/코딩 전문 개발자":
        base_instruction = "당신은 개발자입니다. 코드 설명, 데이터 구조 분석을 친절하게 설명해 주세요."
    else:
        base_instruction = st.text_area("맞춤형 역할을 입력하세요:", "당신은 유능하고 친절한 AI 비즈니스 보조입니다.")

    st.write("---")
    
    # 💡 [핵심] 현재 등록된 파일 정보 (일반 유저도 확인 가능)
    if uploaded_filename:
        st.success(f"📄 **현재 적용된 데이터:**\n{uploaded_filename}")
    else:
        st.info("ℹ️ 현재 등록된 단가표가 없습니다. (기본 지식으로 답변)")

    st.write("---")
    
    # 🔑 [핵심] 관리자 인증 섹션
    st.subheader("🔑 관리자 메뉴")
    
    # Secrets에 암호가 없으면 기본값 '1234' 사용
    admin_password_secret = st.secrets.get("ADMIN_PASSWORD", "1234")
    input_pwd = st.text_input("관리자 비밀번호 입력:", type="password")
    
    is_admin = (input_pwd == admin_password_secret)
    
    if is_admin:
        st.success("🔓 관리자 인증되었습니다.")
        
        # 관리자 전용 업로드 창
        uploaded_file = st.file_uploader("새 단가표/PDF 업로드", type=["xlsx", "csv", "pdf"])
        
        if uploaded_file is not None:
            if st.button("💾 이 파일로 마스터 데이터 업데이트", use_container_width=True):
                try:
                    with st.spinner("파일 변환 및 서버 저장 중..."):
                        extracted_text = ""
                        if uploaded_file.name.endswith(('.xlsx', '.xls')):
                            df = pd.read_excel(uploaded_file)
                            extracted_text = df.to_markdown(index=False)
                        elif uploaded_file.name.endswith('.csv'):
                            df = pd.read_csv(uploaded_file)
                            extracted_text = df.to_markdown(index=False)
                        elif uploaded_file.name.endswith('.pdf'):
                            reader = PdfReader(uploaded_file)
                            for page in reader.pages:
                                extracted_text += page.extract_text() + "\n"
                        
                        save_server_data(extracted_text, uploaded_file.name)
                        st.success("✅ 서버에 새 마스터 데이터가 적용되었습니다!")
                        st.rerun()
                except Exception as e:
                    st.error(f"⚠️ 저장 실패: {e}")
                    
        # 관리자 전용 삭제 버튼
        if uploaded_filename:
            if st.button("🗑️ 등록된 데이터 완전 삭제", use_container_width=True):
                delete_server_data()
                st.warning("등록된 데이터가 삭제되었습니다.")
                st.rerun()
    else:
        if input_pwd:
            st.error("❌ 비밀번호가 올바르지 않습니다.")
        else:
            st.caption("관리자만 파일 등록/삭제를 할 수 있습니다.")

    st.write("---")
    if st.button("🔄 대화 기록 지우기", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 메인 화면
st.title("🤖 세스코 단가 및 서비스 안내 AI (Day 5)")
if uploaded_filename:
    st.caption(f"현재 참조 중인 데이터: **{uploaded_filename}**")
else:
    st.caption("현재 참조 데이터 없음")
st.write("---")

# 4. Secrets에서 API 키 불러오기 및 대화 진행
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("질문을 입력하세요... (예: OO 서비스 월 단가 알려줘)"):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        # 서버에 저장된 마스터 데이터 결합
        final_system_instruction = base_instruction
        if file_context:
            final_system_instruction += (
                f"\n\n[참고 데이터 문서: {uploaded_filename}]\n"
                "다음은 관리자가 직접 등록한 서비스 및 단가 데이터입니다. "
                "사용자의 질문에는 반드시 아래 데이터를 기반으로 정확한 제품명, 스펙, 단가를 찾아 마크다운 표 등으로 답변하세요:\n\n"
                f"{file_context}"
            )

        with st.chat_message("assistant"):
            with st.spinner("답변을 작성 중입니다..."):
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
                    st.error(f"⚠️ 에러가 발생했습니다: {e}")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
