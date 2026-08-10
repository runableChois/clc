import streamlit as st

# 1. 웹페이지 기본 설정 및 타이틀
st.set_page_config(page_title="우리 팀 스몰 제미나이", page_icon="🤖")
st.title("🤖 우리 팀 스몰 제미나이 (Day 1)")
st.write("🎉 축하합니다! 1일차 테스트 웹사이트가 성공적으로 구축되었습니다.")
st.write("---")

# 2. 질문 입력창
user_input = st.text_input("Gemini에게 첫 인사를 건네보세요:", placeholder="예: 안녕? 오늘 기분 어때?")

if user_input:
    with st.spinner("답변을 생성 중입니다..."):
        st.success("답변 도착!")
        # API 에러 없이 시뮬레이션된 답변 출력
        st.write(f"안녕하세요! 입력하신 내용 **'{user_input}'**을(를) 잘 확인했습니다. 1일차 웹사이트 배포가 정상적으로 완료되었습니다! 🚀")
