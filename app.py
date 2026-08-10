import streamlit as st
from google import genai

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="우리 팀 스몰 제미나이", page_icon="🤖")
st.title("🤖 우리 팀 스몰 제미나이")
st.write("실시간 Google Gemini 3 API 연결 웹앱")
st.write("---")

# 2. Secrets에서 API 키 불러오기
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)
    
    # 3. 사용자 입력창
    user_input = st.text_input("Gemini에게 질문을 입력하세요:", placeholder="예: 안녕? 오늘 기분 어때?")
    
    if user_input:
        with st.spinner("Gemini 3가 답변을 생성 중입니다..."):
            try:
                # 💡 구글 AI 스튜디오 공식 최신 모델 호출
                response = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=user_input
                )
                st.success("답변 도착!")
                st.write(response.text)
            except Exception as e:
                st.error("⚠️ API 호출 중 에러가 발생했습니다:")
                st.code(str(e))
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
