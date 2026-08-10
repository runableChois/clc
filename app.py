import streamlit as st
from google import genai

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="우리 팀 제미나이 챗봇", page_icon="💬")
st.title("💬 우리 팀 제미나이 챗봇 (Day 2)")
st.write("Gemini 3 모델과 실시간으로 대화를 나눌 수 있는 챗봇입니다.")
st.write("---")

# 2. Secrets에서 API 키 불러오기
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    # 3. 세션 상태(session_state)에 대화 기록 저장소 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 4. 이전 대화 기록 화면에 말풍선으로 출력
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 5. 하단 챗봇 전용 입력창 (st.chat_input)
    if prompt := st.chat_input("메시지를 입력하세요..."):
        # (1) 사용자 메시지 화면 출력 및 세션 저장
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # (2) 이전 대화 히스토리 구성
        history = []
        for msg in st.session_state.messages[:-1]:  # 방금 입력한 메시지 전까지
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        # (3) Gemini 대화 세션 생성 및 답변 출력
        with st.chat_message("assistant"):
            with st.spinner("Gemini가 생각 중입니다..."):
                try:
                    chat = client.chats.create(
                        model="gemini-3-flash-preview",
                        history=history
                    )
                    response = chat.send_message(prompt)
                    st.markdown(response.text)
                    
                    # (4) 챗봇 답변 세션 저장
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"⚠️ 대화 중 에러가 발생했습니다: {e}")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
