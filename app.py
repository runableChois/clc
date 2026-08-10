import streamlit as st
from google import genai

st.set_page_config(page_title="우리 팀 스몰 제미나이", page_icon="🤖")
st.title("🤖 우리 팀 스몰 제미나이 (Day 1)")
st.write("🎉 축하합니다! 1일차 테스트 웹사이트가 준비되었습니다.")
st.write("---")

if "GEMINI_API_KEY" in st.secrets:
    raw_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=raw_key)
    
    user_input = st.text_input("Gemini에게 첫 인사를 건네보세요:", placeholder="예: 안녕? 오늘 기분 어때?")
    
    if user_input:
        with st.spinner("Gemini가 답변을 생각 중입니다..."):
            try:
                # 최신 무료 플랜 지원 모델 호출
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=user_input
                )
                st.success("답변 도착!")
                st.write(response.text)
            except Exception as e:
                st.error("⚠️ 연결 실패. API 키를 다시 확인해 주세요:")
                st.code(str(e))
else:
    st.error("⚠️ Secrets에 GEMINI_API_KEY를 설정해 주세요.")
