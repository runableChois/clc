import streamlit as st
from google import genai

# 1. 웹페이지 기본 설정 및 타이틀
st.set_page_config(page_title="우리 팀 스몰 제미나이", page_icon="🤖")
st.title("🤖 우리 팀 스몰 제미나이 (Day 1)")
st.write("🎉 축하합니다! 1일차 테스트 웹사이트가 준비되었습니다.")
st.write("---")

# 2. Streamlit Secrets에서 API 키를 안전하게 불러오기
if "GEMINI_API_KEY" in st.secrets:
    # Gemini 클라이언트 생성
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    
    # 질문 입력창
    user_input = st.text_input("Gemini에게 첫 인사를 건네보세요:", placeholder="예: 안녕? 오늘 기분 어때?")
    
    if user_input:
        with st.spinner("Gemini가 답변을 생각 중입니다..."):
            # Gemini 2.5 Flash 모델 호출
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=user_input
            )
            st.success("답변 도착!")
            st.write(response.text)
else:
    st.error("⚠️ API 키가 설정되지 않았습니다. Streamlit Cloud 설정(Secrets)에 GEMINI_API_KEY를 입력해 주세요.")
