import streamlit as st
from google import genai
from google.genai import types

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="맞춤형 AI 전문가 챗봇", page_icon="🤖", layout="wide")

# 2. 사이드바(Sidebar) UI 구성
with st.sidebar:
    st.title("⚙️ 챗봇 설정")
    
    # (1) AI 역할(페르소나) 선택
    role_option = st.selectbox(
        "AI의 역할을 선택하세요:",
        ["비즈니스 마케팅 전문가", "견적 및 가격 비교 전문가", "친절한 영어 회화 튜터", "IT/코딩 전문 개발자", "직접 입력"]
    )
    
    # (2) 역할별 시스템 프롬프트(System Instruction) 설정
    if role_option == "비즈니스 마케팅 전문가":
        system_instruction = "당신은 15년 경력의 베테랑 비즈니스 마케팅 컨설턴트입니다. 사용자의 질문에 전문적이고 설득력 있는 마케팅 전략과 제안을 답변하세요."
    elif role_option == "견적 및 가격 비교 전문가":
         system_instruction = (
            "당신은 견적 산출 및 가격 비교 전문가입니다. "
            "사용자가 상품, 서비스, 프로젝트 견적이나 가격 정보를 물어보면 "
            "반드시 마크다운 표(Table) 형태로 항목, 수량, 단가, 예상 금액, 비고 등을 깔끔하게 정리하여 답변하세요.")
    elif role_option == "친절한 영어 회화 튜터":
        system_instruction = "당신은 친절한 영어 튜터입니다. 사용자가 한국어로 말하면 자연스러운 영어 표현을 알려주고, 영어 대화를 유도해 주세요."
    elif role_option == "IT/코딩 전문 개발자":
        system_instruction = "당신은 개발자입니다. 코드 설명, 버그 수정, 알고리즘 구현을 명확하고 친절하게 설명해 주세요."
    else:
        system_instruction = st.text_area("맞춤형 역할을 입력하세요:", "당신은 유능하고 친절한 AI 비즈니스 보조입니다.")

    st.write("---")
    
    # (3) 대화 초기화 버튼
    if st.button("🔄 대화 기록 지우기", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 메인 화면 타이틀
st.title("🤖 맞춤형 AI 전문가 챗봇 (Day 3)")
st.caption(f"현재 설정된 역할: **{role_option}**")
st.write("---")

# 3. Secrets에서 API 키 불러오기
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    # 4. 대화 기록 저장소 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 5. 이전 대화 기록 화면 출력
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 6. 하단 메시지 입력창
    if prompt := st.chat_input("질문을 입력하세요..."):
        # 사용자 메시지 표시 및 저장
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 이전 대화 히스토리 구성
        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        # Gemini 3 대화 세션 생성 (System Instruction 포함)
        with st.chat_message("assistant"):
            with st.spinner("전문가가 답변을 작성 중입니다..."):
                try:
                    chat = client.chats.create(
                        model="gemini-3-flash-preview",
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction
                        ),
                        history=history
                    )
                    response = chat.send_message(prompt)
                    st.markdown(response.text)
                    
                    # 챗봇 답변 저장
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"⚠️ 에러가 발생했습니다: {e}")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
