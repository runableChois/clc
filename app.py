import streamlit as st
import pandas as pd
from pypdf import PdfReader
from google import genai
from google.genai import types

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="파일 분석 & 맞춤형 AI 전문가 챗봇", page_icon="🤖", layout="wide")

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

# 2. 세션 상태(Session State) 메모리 저장소 초기화
if "file_context" not in st.session_state:
    st.session_state.file_context = ""
if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# 3. 사이드바 UI 구성
with st.sidebar:
    st.title("⚙️ 챗봇 & 문서 설정")
    
    # AI 역할 선택
    role_option = st.selectbox(
        "AI의 역할을 선택하세요:",
        ["견적 및 가격 비교 전문가", "비즈니스 마케팅 전문가", "IT/코딩 전문 개발자", "직접 입력"]
    )
    
    if role_option == "견적 및 가격 비교 전문가":
        base_instruction = "당신은 견적 및 가격 비교 전문가입니다. 사용자가 질문하면 업로드된 엑셀/PDF 데이터를 최우선으로 참고하여 마크다운 표(Table) 형태로 품목, 단가, 상세 스펙 등을 깔끔하게 정리하여 답변하세요."
    elif role_option == "비즈니스 마케팅 전문가":
        base_instruction = "당신은 베테랑 마케팅 컨설턴트입니다. 업로드된 제품 단가 및 스펙 데이터를 바탕으로 마케팅 전략과 제안서를 작성해 주세요."
    elif role_option == "IT/코딩 전문 개발자":
        base_instruction = "당신은 개발자입니다. 코드 설명, 데이터 구조 분석을 친절하게 설명해 주세요."
    else:
        base_instruction = st.text_area("맞춤형 역할을 입력하세요:", "당신은 유능하고 친절한 AI 비즈니스 보조입니다.")

    st.write("---")
    st.subheader("📁 데이터 파일 업로드 (월별 단가표/PDF)")
    
    # 엑셀 / PDF 파일 업로드창
    uploaded_file = st.file_uploader("엑셀(.xlsx, .csv) 또는 PDF(.pdf) 파일을 올리세요", type=["xlsx", "csv", "pdf"])
    
    # 파일이 업로드되면 데이터 추출 수행
    if uploaded_file is not None and st.session_state.uploaded_filename != uploaded_file.name:
        try:
            with st.spinner("파일 내용을 읽어서 AI에게 전달하는 중입니다..."):
                extracted_text = ""
                # 엑셀 파일 처리
                if uploaded_file.name.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(uploaded_file)
                    extracted_text = df.to_markdown(index=False)
                elif uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                    extracted_text = df.to_markdown(index=False)
                # PDF 파일 처리
                elif uploaded_file.name.endswith('.pdf'):
                    reader = PdfReader(uploaded_file)
                    for page in reader.pages:
                        extracted_text += page.extract_text() + "\n"
                
                st.session_state.file_context = extracted_text
                st.session_state.uploaded_filename = uploaded_file.name
                st.success(f"✅ '{uploaded_file.name}' 학습 완료!")
        except Exception as e:
            st.error(f"⚠️ 파일 읽기 실패: {e}")

    # 데이터 업로드 현황 표시
    if st.session_state.uploaded_filename:
        st.info(f"📄 **현재 학습된 데이터:**\n{st.session_state.uploaded_filename}")
        
        # 💡 [핵심] 월별 데이터 초기화/삭제 버튼
        if st.button("🗑️ 기존 데이터 삭제 (월별 업데이트)", use_container_width=True):
            st.session_state.file_context = ""
            st.session_state.uploaded_filename = None
            st.success("기존 데이터가 깔끔하게 삭제되었습니다. 새 단가표를 올려주세요!")
            st.rerun()
    else:
        st.caption("현재 학습된 파일이 없습니다.")

    st.write("---")
    
    # 대화 기록 지우기 버튼
    if st.button("🔄 대화 기록 지우기", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 메인 화면
st.title("🤖 맞춤형 데이터 기반 AI 전문가 (Day 4)")
if st.session_state.uploaded_filename:
    st.caption(f"현재 역할: **{role_option}** | 참조 중인 문서: **{st.session_state.uploaded_filename}**")
else:
    st.caption(f"현재 역할: **{role_option}** | 참고 파일 없음")
st.write("---")

# 4. Secrets에서 API 키 불러오기
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    # 이전 대화 출력
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 사용자 질문 입력
    if prompt := st.chat_input("질문을 입력하세요... (예: 세스코 OO 제품 월 단가 알려줘)"):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 이전 대화 히스토리 구성
        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        # 파일 데이터와 기본 역할을 결합한 최종 시스템 지침 작성
        final_system_instruction = base_instruction
        if st.session_state.file_context:
            final_system_instruction += (
                f"\n\n[참고 데이터 문서: {st.session_state.uploaded_filename}]\n"
                "다음은 사용자가 업로드한 문서의 데이터 내용입니다. "
                "사용자의 질문에 답변할 때는 아래 데이터를 기반으로 정확하게 정답과 가격을 찾아서 답변하세요:\n\n"
                f"{st.session_state.file_context}"
            )

        # Gemini 3 대화 세션 생성 및 요청
        with st.chat_message("assistant"):
            with st.spinner("문서 데이터를 분석하여 답변을 작성 중입니다..."):
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
