import streamlit as st
from google import genai

st.set_page_config(page_title="우리 팀 스몰 제미나이", page_icon="🤖")
st.title("🤖 우리 팀 스몰 제미나이")

if "GEMINI_API_KEY" in st.secrets:
    raw_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=raw_key)
    
    user_input = st.text_input("질문을 입력해 보세요:", placeholder="예: 안녕? 테스트 중이야.")
    
    if user_input:
        # 호출 가능한 모델 후보 목록 (한도가 남아있는 모델을 차례대로 탐색)
        candidate_models = [
            "gemini-2.5-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash"
        ]
        
        success = False
        with st.spinner("구글 서버와 통신 가능한 모델을 연결하는 중..."):
            for model_name in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=user_input
                    )
                    st.success(f"🎉 성공! [{model_name}] 모델로 연결되었습니다.")
                    st.write(response.text)
                    success = True
                    break  # 성공 시 탐색 중단
                except Exception as e:
                    # 실패 시 다음 모델로 넘어감
                    continue
        
        if not success:
            st.error("❌ 연결 가능한 무료 모델이 없습니다. 구글 AI 스튜디오에서 결제 카드 등록(Pay-as-you-go) 또는 새로운 구글 계정으로 키를 생성해야 합니다.")
else:
    st.error("⚠️ Streamlit Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
