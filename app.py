import streamlit as st
from google import genai

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="우리 팀 스몰 제미나이", page_icon="🤖")
st.title("🤖 우리 팀 스몰 제미나이")
st.write("실시간 Google Gemini API 연결 웹앱")
st.write("---")

# 2. Secrets에서 API 키 불러오기
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)
    
    # 3. 사용자 입력창
    user_input = st.text_input("Gemini에게 질문을 입력하세요:", placeholder="예: 안녕? 오늘 기분 어때?")
    
    if user_input:
        with st.spinner("Gemini가 답변을 생성하고 있습니다..."):
            try:
                # 결제 완료된 계정의 정식 Gemini 2.0 Flash 호출
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=user_input
                )
                st.success("답변 도착!")
                st.write(response.text)
            except Exception as e:
                st.error("⚠️ API 호출 중 에러가 발생했습니다:")
                st.code(str(e))
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
