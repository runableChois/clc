import streamlit as st
from google import genai

st.set_page_config(page_title="우리 팀 스몰 제미나이", page_icon="🤖")
st.title("🤖 우리 팀 스몰 제미나이 (진단 모드)")

if "GEMINI_API_KEY" in st.secrets:
    # 1. Secrets 키 앞뒤 공백 자동 제거 및 입력 확인
    raw_key = st.secrets["GEMINI_API_KEY"].strip()
    st.info(f"🔑 현재 적용된 키: `{raw_key[:5]}...{raw_key[-4:]}` (총 {len(raw_key)}자)")

    # 2. Gemini 클라이언트 생성
    client = genai.Client(api_key=raw_key)
    
    user_input = st.text_input("질문을 입력해 보세요:", placeholder="예: 안녕? 테스트 중이야.")
    
    if user_input:
        with st.spinner("구글 서버로 요청 보내는 중..."):
            try:
                # 3. Gemini 호출
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=user_input
                )
                st.success("🎉 성공! 구글 API가 정상 작동합니다.")
                st.write(response.text)
                
            except Exception as e:
                # 4. 숨겨진 진짜 구글 에러 메시지를 화면에 직접 출력
                st.error("❌ 구글 API 서버에서 거절 에러가 발생했습니다:")
                st.code(str(e))
else:
    st.error("⚠️ Streamlit Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
