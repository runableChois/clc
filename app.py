import io
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
import pandas as pd
from pypdf import PdfReader
import streamlit as st
import streamlit.components.v1 as components

# ==========================================
# 1. 페이지 기본 설정 및 모바일 UI 최적화 CSS
# ==========================================
st.set_page_config(
    page_title="세스코 경기서북부 플래너 AI (Pro)",
    page_icon="💼",
    layout="wide"
)

# Streamlit Cloud 배지, 헤더, 푸터 완전 은닉 스크립트
components.html("""
<script>
    function removeStreamlitBadgesOnly() {
        try {
            const parentDoc = window.parent.document;
            const selectors = [
                'footer',
                '#MainMenu',
                '[data-testid="stStatusWidget"]',
                '[data-testid="stDecoration"]',
                '[class*="viewerBadge"]',
                '[class*="stAppDeployButton"]',
                'div[class*="styles_viewerBadge"]',
                'div[class*="ViewerBadge"]',
                'button[title="View app in Streamlit Community Cloud"]'
            ];
            selectors.forEach(selector => {
                const elements = parentDoc.querySelectorAll(selector);
                elements.forEach(el => {
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                });
            });
        } catch (e) { console.log(e); }
    }
    setInterval(removeStreamlitBadgesOnly, 300);
</script>
""", height=0, width=0)

st.markdown("""
<style>
    footer {display: none !important; visibility: hidden !important;}
    #MainMenu {display: none !important;}
    .stAppDeployButton {display: none !important;}
    div[data-testid="stDecoration"] {display: none !important;}
    div[data-testid="stStatusWidget"] {display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    
    div[data-testid="stHeader"] {
        background-color: transparent !important;
        z-index: 100 !important;
    }
    
    [data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"] {
        display: flex !important;
        visibility: visible !important;
        color: #ffffff !important;
        background-color: #003b7a !important;
        border-radius: 8px !important;
        padding: 4px !important;
        margin-top: 5px !important;
        margin-left: 5px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2) !important;
    }
    
    [data-testid="collapsedControl"] button, [data-testid="stSidebarCollapseButton"] button {
        color: #ffffff !important;
    }

    .main .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 2rem !important;
    }
    
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
        h1 { font-size: 1.4rem !important; }
        div[data-testid="stMarkdownContainer"] table { font-size: 12px !important; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 통합 마스터 시스템 지침 & 제품 지식 베이스
# ==========================================
CESCO_MASTER_SYSTEM_INSTRUCTION = """
당신은 세스코(CESCO) 경기서북부(고양, 파주, 김포, 인천 검단) 영업 플래너를 전담 지원하는 '올인원 현장 영업 지원 마스터 AI'입니다.

[세스코 핵심 8대 제품 라인업 지식 기반]
1. 공기청정기: '판테온' (360도 필터, CA인증, CO2/PM1.0 센서, 초미세먼지 및 냄새 탈취)
2. 공기살균기: '센스미' (UV-C 파워 램프, S형 유로 설계, 부유 바이러스·세균 99.9% 제거, 슬림 디자인)
3. 탱크형 정수기: '더슬림', '더블', '더맥스' (업소용 대용량, 다중 필터링, 연속 출수)
4. 직수 정수기: '살균온', '살균온 얼음정수기' (UVnano 코크/아이스룸 살균, 직수형 위생 정수)
5. 비데: '파워방수비데', '살균방수비데', '듀얼비데', '올인원비데' (IPX6 강력 방수, 전해수/UV 노즐 살균)
6. 향기 제품: '에어퍼퓸200', '에어제닉' (공간 맞춤형 자동 향기 분사 및 악취 분해)
7. 화장실 케어 제품: '프레쉬제닉' (변기 세정·탈취), '핸드제닉' (비접촉 손세정기), '새니제닉' (비접촉 손소독기)
8. 날벌레 방지 제품: '에어커튼' (출입구 바람 차단), '포충등' (실내 자외선 포충/유인)

[플래너 질문 유형별 응답 작성 규칙]

1. 📍 특정 상권 / 지역 / 건물 / 장비 방문 영업 문의 시:
   - 아래 6단계 프레임워크에 따라 상세 지침서 작성:
     ① 🎯 보유 장비/제품 맞춤 타겟 업종 매칭 (3일 무료 체험 기준)
     ② ⏰ 업종별 사장님 상주 '골든타임' 시간대
     ③ 📍 건물별 입점 업종 분포, 정확한 도로명 주소 및 네이버 지도 URL 필수 작성
        (URL 형식: [📍 네이버 지도로 위치 보기](https://map.naver.com/v5/search/건물명또는주소))
     ④ 🛡️ '네이버 악성 리뷰 방지 & 매출 보호 ROI' 설득 논리 및 3일 체험 피칭 스크립트
     ⑤ 💬 3일 차 피드백 요청 및 최종 계약 전환(Closing) 화법
     ⑥ 📋 방문 구역 통합 요약표 [방문순서 | 건물명/동 | 대표 도로명주소 | 주요 입점 업종 & 골든타임 | 네이버 지도 바로가기]

2. 🔍 견적 / 요금 / 제품 단가 문의 시:
   - 업로드된 [학습 문서 데이터]가 있다면 최우선 참조.
   - 3단계 스스로 점검(문서 존재여부 → 단독가/결합가 가격 정확성 → 적합성) 후 표와 불렛포인트로 간결히 답변.

3. 🛡️ 거절 대응 문의 시:
   - 거절 반응을 뒤집는 1초 반박 스크립트와 세스코 차별점을 핵심만 명확히 답변.
"""

# ==========================================
# 3. 이미지 생성 엔진 (카톡 고화질 견적 카드용)
# ==========================================
FONT_PATH = "NanumGothic-Bold.ttf"

def ensure_korean_font():
    """한글 폰트(나눔고딕) 자동 다운로드 처리"""
    if not os.path.exists(FONT_PATH):
        font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
        try:
            urllib.request.urlretrieve(font_url, FONT_PATH)
        except Exception as e:
            st.error(f"폰트 다운로드 실패: {e}")

def create_high_res_quote_card(card_data):
    """1200x1600 초고해상도 완제품 이미지 카드 생성"""
    ensure_korean_font()
    width, height = 1200, 1600
    img = Image.new('RGB', (width, height), color='#f1f5f9')
    draw = ImageDraw.Draw(img)
    
    try:
        font_brand = ImageFont.truetype(FONT_PATH, 48)
        font_subhead = ImageFont.truetype(FONT_PATH, 24)
        font_title = ImageFont.truetype(FONT_PATH, 34)
        font_item_name = ImageFont.truetype(FONT_PATH, 30)
        font_price = ImageFont.truetype(FONT_PATH, 36)
        font_regular = ImageFont.truetype(FONT_PATH, 24)
        font_small = ImageFont.truetype(FONT_PATH, 20)
    except Exception:
        font_brand = font_subhead = font_title = font_item_name = font_price = font_regular = font_small = ImageFont.load_default()

    # 상단 헤더 영역
    draw.rectangle([(0, 0), (width, 200)], fill='#003b7a')
    draw.rectangle([(0, 190), (width, 200)], fill='#00a3e0') 
    
    draw.text((60, 45), "💎 CESCO 맞춤 솔루션 견적서", fill='#ffffff', font=font_brand)
    draw.text((60, 125), "세스코 공식 문서 기반 | 현장 맞춤 케어 제안", fill='#dbeafe', font=font_subhead)

    # 견적 제목 영역
    draw.rectangle([(50, 240), (width - 50, 370)], fill='#ffffff', outline='#cbd5e1', width=2)
    title_text = card_data.get("title", "맞춤 위생 솔루션 견적")
    draw.text((80, 268), title_text[:30], fill='#0f172a', font=font_title)
    
    subtitle_text = card_data.get("subtitle", "공식 문서 데이터 기준")
    draw.text((80, 320), subtitle_text[:40], fill='#64748b', font=font_regular)

    # 서비스 항목 카드 출력
    items = card_data.get("items", [])
    y_offset = 400
    for item in items[:4]:
        draw.rectangle([(50, y_offset), (width - 50, y_offset + 140)], fill='#ffffff', outline='#e2e8f0', width=2)
        
        name = item.get("name", "서비스 항목")
        note = item.get("note", "")
        price = item.get("price", "상담가")

        draw.text((80, y_offset + 30), name[:20], fill='#0f172a', font=font_item_name)
        if note:
            draw.text((80, y_offset + 80), note[:28], fill='#64748b', font=font_small)

        draw.rectangle([(width - 380, y_offset + 30), (width - 80, y_offset + 110)], fill='#eff6ff', outline='#bfdbfe', width=1)
        draw.text((width - 360, y_offset + 48), price, fill='#003b7a', font=font_price)
        
        y_offset += 160

    # 프로모션 배너
    promo_text = card_data.get("promotion", "")
    if promo_text:
        draw.rectangle([(50, y_offset + 10), (width - 50, y_offset + 180)], fill='#e0f2fe', outline='#0284c7', width=2)
        draw.text((80, y_offset + 35), "🎁 특별 프로모션 & 결합 혜택", fill='#0369a1', font=font_title)
        draw.text((80, y_offset + 105), promo_text[:45], fill='#0f172a', font=font_regular)

    # 하단 푸터
    draw.rectangle([(0, height - 130), (width, height)], fill='#0f172a')
    draw.text((60, height - 95), "📞 서비스 문의 및 신청: 세스코 담당 플래너", fill='#ffffff', font=font_regular)
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

# ==========================================
# 4. 데이터 I/O 및 누적 문서 학습 (RAG) 함수
# ==========================================
KNOWLEDGE_BASE_PATH = "cesco_knowledge_base.txt"
KNOWLEDGE_FILES_PATH = "cesco_knowledge_files_list.txt"
SALES_LOG_PATH = "sales_activity_log.csv"
EQUIPMENT_LOG_PATH = "team_equipment_inventory.csv"

def load_knowledge_data():
    """누적 학습 텍스트 및 학습 파일 목록 로드"""
    context = ""
    file_list_str = ""
    if os.path.exists(KNOWLEDGE_BASE_PATH):
        with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
            context = f.read()
    if os.path.exists(KNOWLEDGE_FILES_PATH):
        with open(KNOWLEDGE_FILES_PATH, "r", encoding="utf-8") as f:
            file_list_str = f.read()
    return context, file_list_str

def add_file_to_cumulative_knowledge(uploaded_file):
    """업로드된 파일(PDF, Excel, CSV)을 지식 베이스에 누적(Append) 학습"""
    extracted_text = ""
    filename = uploaded_file.name
    
    if filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(uploaded_file, sheet_name=0)
        df = df.dropna(how="all")
        extracted_text = df.to_markdown(index=False)
    elif filename.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
        df = df.dropna(how="all")
        extracted_text = df.to_markdown(index=False)
    elif filename.endswith('.pdf'):
        reader = PdfReader(uploaded_file)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"

    if extracted_text:
        current_context, current_files = load_knowledge_data()
        
        if filename in current_files.split(","):
            return False, f"⚠️ `{filename}` 문서는 이미 학습되어 있습니다."

        new_context = current_context + f"\n\n--- [학습 문서 시작: {filename}] ---\n" + extracted_text + f"\n--- [학습 문서 끝: {filename}] ---\n"
        
        with open(KNOWLEDGE_BASE_PATH, "w", encoding="utf-8") as f:
            f.write(new_context)
            
        new_files_list = (current_files + "," + filename).strip(",")
        with open(KNOWLEDGE_FILES_PATH, "w", encoding="utf-8") as f:
            f.write(new_files_list)
            
        return True, f"✅ `{filename}` 문서 학습 완료! 통합 지식 베이스에 추가되었습니다."
    return False, f"⚠️ `{filename}` 문서에서 텍스트를 추출할 수 없습니다."

def delete_all_knowledge_data():
    """전체 학습 데이터 초기화"""
    if os.path.exists(KNOWLEDGE_BASE_PATH):
        os.remove(KNOWLEDGE_BASE_PATH)
    if os.path.exists(KNOWLEDGE_FILES_PATH):
        os.remove(KNOWLEDGE_FILES_PATH)

knowledge_context, learned_files_str = load_knowledge_data()
learned_files_list = [f for f in learned_files_str.split(",") if f]

def save_sales_log(planner_name, client_name, proposed_deal, equipment_status, equipment_item, reaction, memo, install_date=None):
    """영업 일지 데이터 저장 (3일 체험 스케줄 자동 계산 포함)"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_date_str = install_date if install_date else datetime.now().strftime("%Y-%m-%d")
    
    # 체험장비 설치 시 D+3 피드백 예정일 자동 산정
    feedback_due = "-"
    if equipment_status == "설치 완료":
        try:
            inst_dt = datetime.strptime(today_date_str, "%Y-%m-%d")
            feedback_due = (inst_dt + timedelta(days=3)).strftime("%Y-%m-%d")
        except:
            feedback_due = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    new_data = pd.DataFrame([{
        "작성일시": now_str,
        "담당플래너": planner_name,
        "고객/매장명": client_name,
        "제안서비스/견적가": proposed_deal,
        "체험장비설치": equipment_status,
        "설치장비품목": equipment_item if equipment_status == "설치 완료" else "-",
        "설치일자": today_date_str if equipment_status == "설치 완료" else "-",
        "3일체험_피드백예정일": feedback_due,
        "고객반응/상태": reaction,
        "영업메모": memo
    }])
    
    if os.path.exists(SALES_LOG_PATH):
        old_df = pd.read_csv(SALES_LOG_PATH)
        if "담당팀원" in old_df.columns:
            old_df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
        for col in ["설치일자", "3일체험_피드백예정일"]:
            if col not in old_df.columns:
                old_df[col] = "-"
        df = pd.concat([old_df, new_data], ignore_index=True)
    else:
        df = new_data
    df.to_csv(SALES_LOG_PATH, index=False, encoding="utf-8-sig")

def load_equipment_inventory():
    """플래너별 체험장비 보유 대수 로드"""
    if os.path.exists(EQUIPMENT_LOG_PATH):
        df = pd.read_csv(EQUIPMENT_LOG_PATH)
        if "담당팀원" in df.columns:
            df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
        if "보유대수" in df.columns and "전체 보유대수" not in df.columns:
            df.rename(columns={"보유대수": "전체 보유대수"}, inplace=True)
        return df
    default_df = pd.DataFrame([
        {"담당플래너": "홍길동", "전체 보유대수": 5},
        {"담당플래너": "김철수", "전체 보유대수": 3},
        {"담당플래너": "이영희", "전체 보유대수": 4}
    ])
    default_df.to_csv(EQUIPMENT_LOG_PATH, index=False, encoding="utf-8-sig")
    return default_df

def save_equipment_inventory(df):
    """체험장비 보유 대수 저장"""
    df.to_csv(EQUIPMENT_LOG_PATH, index=False, encoding="utf-8-sig")

# ==========================================
# 5. 사이드바 UI (모드 선택 드롭다운 삭제로 깔끔화)
# ==========================================
with st.sidebar:
    st.header("⚙️ 세스코 영업지원 센터")
    st.success("🤖 **올인원 스마트 AI 가동 중**")
    st.caption("질문, 사진, 상권, 거절 대응 등 무엇이든 입력하면 AI가 의도를 자동 인식합니다.")

    st.divider()
    st.subheader("📚 현재 AI 학습 문서 상태")
    if learned_files_list:
        st.success(f"**누적 학습 완료 ({len(learned_files_list)}건):**")
        st.text_area("파일 목록 (RAG 최우선 참조)", value="\n".join(learned_files_list), height=100)
    else:
        st.info("현재 학습된 단가표 문서가 없습니다.")

    st.divider()
    st.subheader("🔑 관리자 패널")
    admin_password_secret = st.secrets.get("ADMIN_PASSWORD", "1234")
    input_pwd = st.text_input("비밀번호 입력:", type="password")
    
    if input_pwd == admin_password_secret:
        st.success("🔓 관리자 권한 활성화됨")
        
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["📊 영업 대시보드", "📦 체험장비 운용/할당 설정", "📁 누적 문서 학습(PDF)"])
        
        with admin_tab1:
            st.write("📈 **실시간 영업 성과 & 3일 체험 전환 대시보드**")
            if os.path.exists(SALES_LOG_PATH):
                logs_df = pd.read_csv(SALES_LOG_PATH)
                if "담당팀원" in logs_df.columns and "담당플래너" not in logs_df.columns:
                    logs_df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
                if "설치장비품목" not in logs_df.columns:
                    logs_df["설치장비품목"] = "-"
                
                inv_df = load_equipment_inventory()
                installed_counts = logs_df[logs_df["체험장비설치"] == "설치 완료"]["담당플래너"].value_counts().reset_index()
                installed_counts.columns = ["담당플래너", "설치대수"]
                
                merged_inv = pd.merge(inv_df, installed_counts, on="담당플래너", how="left").fillna(0)
                merged_inv["설치대수"] = merged_inv["설치대수"].astype(int)
                merged_inv["현재 수중 보유대수"] = merged_inv["전체 보유대수"] - merged_inv["설치대수"]
                merged_inv["설치활동률(%)"] = (merged_inv["설치대수"] / merged_inv["전체 보유대수"] * 100).round(1)
                
                st.subheader("1️⃣ 플래너별 체험장비 보유 및 설치 현황")
                st.dataframe(merged_inv[["담당플래너", "전체 보유대수", "설치대수", "현재 수중 보유대수", "설치활동률(%)"]], use_container_width=True)
                
                st.divider()
                st.subheader("⏰ 2️⃣ [3일 체험 완료] 피드백 요청 & 계약 클로징 대상 매장")
                if "3일체험_피드백예정일" in logs_df.columns:
                    active_trials = logs_df[(logs_df["체험장비설치"] == "설치 완료") & (logs_df["3일체험_피드백예정일"] != "-")]
                    if len(active_trials) > 0:
                        disp_cols = ["담당플래너", "고객/매장명", "설치장비품목", "설치일자", "3일체험_피드백예정일", "고객반응/상태"]
                        st.dataframe(active_trials[disp_cols], use_container_width=True)
                        st.info("💡 **3일 차 피드백 추천 멘트:** '사장님! 3일간 사용해 보시니 어떠셨어요? 단골손님들이 향이나 공기 좋아졌다고 안 하시던가요? 오늘부터 할인가로 계약 확정해 드릴까요?'")
                    else:
                        st.caption("현재 3일 체험 진행 중인 매장이 없습니다.")

                st.divider()
                st.subheader("3️⃣ 체험장비 설치 후 계약 성사율 분석")
                installed_group = logs_df[logs_df["체험장비설치"] == "설치 완료"]
                non_installed_group = logs_df[logs_df["체험장비설치"] != "설치 완료"]
                
                total_installed = len(installed_group)
                installed_success = len(installed_group[installed_group["고객반응/상태"].str.contains("계약 완료", na=False)])
                installed_rate = (installed_success / total_installed * 100) if total_installed > 0 else 0.0
                
                total_non = len(non_installed_group)
                non_success = len(non_installed_group[non_installed_group["고객반응/상태"].str.contains("계약 완료", na=False)])
                non_rate = (non_success / total_non * 100) if total_non > 0 else 0.0
                
                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    st.metric(label="🎁 체험장비 설치 후 계약 성사율", value=f"{installed_rate:.1f}%", delta=f"{installed_success}건 성공 / 총 {total_installed}건")
                with m_col2:
                    st.metric(label="❌ 미설치건 계약 성사율", value=f"{non_rate:.1f}%", delta=f"{non_success}건 성공 / 총 {total_non}건")
                    
                st.divider()
                st.write("📋 **전체 영업일지 데이터 대장:**")
                st.dataframe(logs_df, use_container_width=True)
                
                logs_csv = logs_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="📥 영업일지 전체 다운로드 (.csv)",
                    data=logs_csv,
                    file_name="팀_영업활동기록대장.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("영업일지 데이터가 쌓이면 실시간 분석 대시보드가 표시됩니다.")

        with admin_tab2:
            st.write("📦 **체험장비 보유 대수 & 설치 장소/내역 종합 관리**")
            st.subheader("📍 1. 체험장비 실제 설치 매장/장소 상세 내역")
            if os.path.exists(SALES_LOG_PATH):
                logs_df = pd.read_csv(SALES_LOG_PATH)
                if "담당팀원" in logs_df.columns and "담당플래너" not in logs_df.columns:
                    logs_df.rename(columns={"담당팀원": "담당플래너"}, inplace=True)
                if "설치장비품목" not in logs_df.columns:
                    logs_df["설치장비품목"] = "-"
                
                installed_logs = logs_df[logs_df["체험장비설치"] == "설치 완료"]
                if len(installed_logs) > 0:
                    display_cols = ["작성일시", "담당플래너", "고객/매장명", "설치장비품목", "3일체험_피드백예정일", "고객반응/상태", "영업메모"]
                    disp_cols_exist = [c for c in display_cols if c in installed_logs.columns]
                    st.dataframe(installed_logs[disp_cols_exist], use_container_width=True)
                else:
                    st.info("현재 현장에 설치된 체험장비 내역이 없습니다.")
            else:
                st.info("기록된 영업일지가 없습니다.")
                
            st.divider()
            st.subheader("⚙️ 2. 플래너별 체험장비 전체 할당 대수(Total) 수정")
            current_inv = load_equipment_inventory()
            
            edited_df = st.data_editor(current_inv, num_rows="dynamic", use_container_width=True)
            if st.button("💾 전체 보유대수 수정사항 저장", use_container_width=True):
                save_equipment_inventory(edited_df)
                st.toast("✅ 플래너별 체험장비 전체 할당 대수가 업데이트되었습니다!", icon="🎉")
                st.rerun()

        with admin_tab3:
            st.subheader("📁 제품 정보 및 단가표 문서(PDF) 누적 학습")
            st.caption("여러 개의 PDF, 엑셀 파일을 업로드하면 AI가 통합하여 하나의 지식 기반으로 만듭니다.")
            
            uploaded_files = st.file_uploader("여러 제품 문서 업로드 (누적 학습)", type=["pdf", "xlsx", "csv"], accept_multiple_files=True)
            
            if uploaded_files and st.button("💾 업로드된 모든 문서를 누적 학습시키기", use_container_width=True):
                success_count = 0
                error_msgs = []
                with st.spinner("AI가 여러 문서를 정밀 분석 및 통합 학습 중입니다..."):
                    for up_file in uploaded_files:
                        success, message = add_file_to_cumulative_knowledge(up_file)
                        if success:
                            success_count += 1
                        else:
                            error_msgs.append(message)
                            
                if success_count > 0:
                    st.toast(f"✅ {success_count}건의 문서 누적 학습 완료!", icon="🎉")
                if error_msgs:
                    st.warning("\n".join(error_msgs))
                st.rerun()
                    
            if learned_files_list and st.button("🗑️ 전체 학습 데이터 초기화 (삭제)", use_container_width=True, type="secondary"):
                delete_all_knowledge_data()
                st.toast("전체 학습 데이터 초기화 완료!", icon="🧹")
                st.rerun()
    elif input_pwd:
        st.error("비밀번호 불일치")
    else:
        st.caption("관리자만 영업 대시보드 및 AI 누적 문서 학습 관리가 가능합니다.")

    # 대화내용 초기화 버튼
    st.divider()
    if st.button("🔄 대화 내용 초기화", use_container_width=True):
        st.session_state["messages"] = []
        st.toast("대화 내용이 초기화되었습니다.", icon="🧹")
        st.rerun()

# ==========================================
# 6. 메인 화면 & 챗봇 인터페이스
# ==========================================
st.title("💼 우리 팀 세스코 영업지원 AI (Pro)")

if learned_files_list:
    st.caption(f"📌 **참조 학습 문서:** `{len(learned_files_list)}건 통합` | 경기서북부 올인원 AI")
else:
    st.caption("📌 **경기서북부(고양/파주/김포/검단) 올인원 스마트 영업 AI**")

st.divider()

if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    client = genai.Client(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 현장 거절 대응 1초 반박 퀵카드 (익스팬더)
    with st.expander("⚡ **현장 사장님 거절 반응 '1초 반박' 퀵카드 (원터치)**", expanded=False):
        st.caption("현장에서 사장님이 거절 멘트를 던졌을 때 버튼을 누르면 1초 만에 최적의 반박 피칭 스크립트가 출력됩니다.")
        q_col1, q_col2, q_col3 = st.columns(3)
        quick_rejection_prompt = None
        
        with q_col1:
            if st.button("🙅 '사장님 지금 안 계세요'", use_container_width=True):
                quick_rejection_prompt = "고객/매장에서 '사장님 지금 안 계세요'라고 거절했을 때, 직원/알바생을 통해 사장님 명함을 확보하고 3일 무료 체험 쿠폰을 전달하는 1초 반박 피칭 스크립트를 알려줘."
            if st.button("🙅 '기존 디퓨저/공청기 있어요'", use_container_width=True):
                quick_rejection_prompt = "사장님이 '기존에 쓰는 디퓨저나 공기청정기 있어요'라고 거절할 때, 시중 디퓨저의 악취 은폐 한계와 세스코 에어제닉/에어퍼퓸의 살균·분해 차별점을 강조하는 3일 체험 피칭 스크립트를 알려줘."
        
        with q_col2:
            if st.button("🙅 '우린 냄새 안 나고 깨끗해요'", use_container_width=True):
                quick_rejection_prompt = "사장님이 '우리 매장은 깨끗해서 필요 없어요'라고 할 때, 깨끗한 매장에 시그니처 향을 더해 프리미엄 네이버 리뷰를 확보하는 3일 체험 설득 멘트를 알려줘."
            if st.button("🙅 '공짜라 하고 돈 요구할 거죠?'", use_container_width=True):
                quick_rejection_prompt = "사장님이 '무상 설치해 주고 나중에 돈 요구하려는 것 아니냐'며 의심할 때, 100% 본사 지원 3일 무상 체험이며 마음에 안 들면 단 1원 없이 회수한다는 완벽한 안심 스크립트를 알려줘."
                
        with q_col3:
            if st.button("🙅 '월 비용이 부담돼요'", use_container_width=True):
                quick_rejection_prompt = "사장님이 '월 이용료가 부담된다'고 할 때, 네이버 악성 리뷰 1건 방지로 얻는 매출 보호 ROI 가치를 3일 체험 제안과 함께 설명하는 반박 화법을 알려줘."
            if st.button("📞 '3일 체험 후 피드백 콜 화법'", use_container_width=True):
                quick_rejection_prompt = "3일간 무상 체험 장비 설치가 끝난 사장님에게 전화/방문하여 3일간의 효과 피드백을 물어보고 공식 유료 계약으로 전환(Closing)시키는 피드백 요청 스크립트를 작성해줘."

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    selected_faq = None
    st.write("💡 **경기 서북부 주요 거점 퀵 분석 (버튼 터치):**")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📌 파주 야당역/운정 상권", use_container_width=True):
            selected_faq = "파주 야당역 음식점/유흥 상권 및 운정 신도시 상가의 특징, 포진 업종, 3일 체험 타겟 세스코 상품 및 골든타임 동선과 네이버 지도 주소를 알려줘."
    with col2:
        if st.button("📌 김포 구래동/운양동 상권", use_container_width=True):
            selected_faq = "김포 구래동 24시 외식 상권과 운양동 카페/병원 상권의 특성, 입점 건물 주소(네이버 지도), 3일 체험 제안 전략을 분석해줘."
    with col3:
        if st.button("📌 검단신도시 아라동 상권", use_container_width=True):
            selected_faq = "인천 검단신도시(아라동) 신규 입주 상가 건물들의 업종 특징, 네이버 지도 주소, 3일 체험 타겟 및 골든타임 피칭 전략을 알려줘."
    with col4:
        if st.button("📌 고양 라페스타/삼송 상권", use_container_width=True):
            selected_faq = "고양 라페스타 구상권과 삼송/덕은 신규 오피스 상권의 주요 건물별 입점 업종, 네이버 지도 주소, 에어퍼퓸/에어제닉 3일 체험 침투 전략을 분석해줘."

    st.write("---")
    
    # 현장 사진 멀티모달 진단 + 1페이지 브리핑 리포트
    with st.expander("📸 **현장 사진 AI 진단 & 1페이지 영업 브리핑 리포트 생성**"):
        uploaded_img = st.file_uploader("현장 사진(매장, 주방, 화장실, 외관 등)을 첨부하면 AI가 시각 요소를 분석하여 8대 제품 중 맞춤 제안 리포트를 생성합니다.", type=["jpg", "jpeg", "png"])
        if uploaded_img:
            st.image(uploaded_img, caption="첨부된 현장 사진 진단 준비 완료", width=250)

    prompt_input = st.chat_input("질문을 입력하세요... (예: 라페스타 에어퍼퓸 3일 체험 어디가 좋아? 또는 견적 단가표 알려줘)")
    
    # 거절 반박 퀵카드 -> 퀵 버튼 -> 입력창 순 적용
    if quick_rejection_prompt:
        user_prompt = quick_rejection_prompt
    elif selected_faq:
        user_prompt = selected_faq
    elif uploaded_img and not prompt_input:
        user_prompt = "첨부한 현장 사진을 시각적으로 정밀 진단하고, 8대 세스코 제품 라인업을 바탕으로 [1페이지 현장 영업 브리핑 리포트]를 작성해 줘."
    else:
        user_prompt = prompt_input

    if user_prompt:
        st.chat_message("user").markdown(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        history = []
        for msg in st.session_state.messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [{"text": msg["content"]}]})

        # 시스템 지침 분기 처리 (통합 마스터 엔진 적용)
        if quick_rejection_prompt:
            final_system_instruction = (
                "당신은 베테랑 세스코 영업 멘토입니다.\n"
                "지역 정보, 건물 주소, 지도 링크, 요약표 등은 절대로 작성하거나 출력하지 마세요.\n"
                "오직 요청된 거절 상황에 대한 1초 즉시 반박 킬러 스크립트(플래너 대화 화법)와 핵심 영업 팁만 불렛포인트로 3~4줄 이내로 매우 빠르고 간결하게 출력하세요."
            )
        elif uploaded_img:
            final_system_instruction = (
                "당신은 세스코 영업사원을 위한 '현장 영업 지원 전담 AI 도우미(Field Sales Intelligence AI)'입니다.\n"
                "영업사원이 업로드한 현장 사진의 시각적 요소와 상황을 정밀 분석하여 반드시 아래 [AI 브리핑 리포트 출력 표준 규격] 4가지 항목으로 정리하여 답변해 주세요.\n\n"
                "[AI 브리핑 리포트 출력 표준 규격]\n"
                "1. [현장 진단 & 위험 요소 분석]\n"
                "   - 공간 유형, 규모 추정, 위생/환경 위험 요소(공기 오염, 악취, 날벌레 유입, 화장실 습기/위생 등) 진단\n\n"
                "2. [추천 제품 & 핵심 스펙]\n"
                "   - 세스코 8대 제품 라인업 중 현장에 가장 적합한 제품 2~4개 선정 및 설치 위치, 핵심 스펙 요약\n\n"
                "3. [현장 맞춤 설득 스크립트 (영업사원용)]\n"
                "   - 해당 업주 맞춤 실전 오프닝 및 3일 무료 체험 권유 멘트\n\n"
                "4. [추천 패키지 & 견적 포인트]\n"
                "   - 제품 결합 패키지 추천 및 가치 제안(네이버 악성 리뷰 방지, 매장 브랜드 이미지 제고, ROI 등)"
            )
        else:
            final_system_instruction = CESCO_MASTER_SYSTEM_INSTRUCTION
            if knowledge_context:
                final_system_instruction += (
                    f"\n\n[업로드된 전체 통합 학습 문서 데이터 ({len(learned_files_list)}건 통합본)]\n"
                    "견적이나 제품 단가 문의 시 가장 중요한 참조 문서입니다. 답변 시 반드시 이 내용 안에서만 찾고 3번 점검하세요:\n\n"
                    f"{knowledge_context}"
                )

        with st.chat_message("assistant"):
            try:
                chat = client.chats.create(
                    model="gemini-3-flash-preview", 
                    config=types.GenerateContentConfig(
                        system_instruction=final_system_instruction
                    ),
                    history=history
                )
                
                if uploaded_img:
                    from PIL import Image as PILImage
                    img_obj = PILImage.open(uploaded_img)
                    send_contents = [user_prompt, img_obj]
                else:
                    send_contents = user_prompt

                response_stream = chat.send_message_stream(send_contents)
                
                def stream_generator():
                    for chunk in response_stream:
                        yield chunk.text

                full_response = st.write_stream(stream_generator())
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.rerun()
            except Exception as e:
                st.error(f"⚠️ 답변 생성 실패: {e}")

    # ==========================================
    # 📱 카톡 요약문 (300자 제한) & 견적 카드 생성
    # ==========================================
    st.write("---")
    if len(st.session_state.messages) > 0:
        if st.button("📱 **간결한 카톡 제안서 & 카드 이미지 생성**", use_container_width=True):
            with st.spinner("300자 이내 카톡 메시지 및 초고해상도 카드 제작 중..."):
                try:
                    recent_chat = st.session_state.messages[-1]["content"]
                    
                    summary_prompt = (
                        f"다음 견적 상담 내용을 바탕으로 고객에게 카카오톡으로 전달할 친절하고 정중한 요약 메시지를 작성해 줘.\n"
                        f"[작성 조건]\n"
                        f"1. 전체 글자 수는 공백 포함 **최대 300자 이내**로 매우 간결하게 작성할 것.\n"
                        f"2. 인사말은 1줄로 최소화하고 [매장명/추천서비스/월단가/주요혜택(3일 무상체험 포함)]만 불렛포인트로 명확히 적을 것.\n"
                        f"3. 한눈에 읽기 쉬운 카톡 전송용으로 만들 것.\n"
                        f"4. AI가 스스로 3번 점검한 정확한 제품명과 가격이어야 함.\n\n"
                        f"견적 내용:\n{recent_chat}"
                    )
                    chat = client.chats.create(model="gemini-3-flash-preview")
                    text_res = chat.send_message(summary_prompt)
                    
                    st.subheader("📱 **1. 카톡/문자 전송용 간결 메시지 (복사용)**")
                    st.code(text_res.text, language="text")
                    
                    json_prompt = (
                        f"다음 견적 내용에서 핵심 서비스와 요금 정보를 추출하여 오직 JSON 형식으로만 응답해 줘.\n"
                        f"JSON 구조 예시:\n"
                        f"{{\n"
                        f'  "title": "15평 매장 맞춤 위생 솔루션 견적",\n'
                        f'  "subtitle": "3일 무상 체험 + 방제 결합 할인가",\n'
                        f'  "items": [\n'
                        f'    {{"name": "에어제닉/에어퍼퓸", "price": "3일 무료체험", "note": "설치비 면제 혜택"}},\n'
                        f'    {{"name": "바이러스케어", "price": "30,000원/월", "note": "방제 결합 할인가"}}\n'
                        f'  ],\n'
                        f'  "promotion": "3일 체험 후 피드백 만족 시 추가 할인"\n'
                        f"}}\n\n"
                        f"견적 내용:\n{recent_chat}"
                    )
                    json_res = chat.send_message(json_prompt)
                    
                    json_match = re.search(r'\{.*\}', json_res.text, re.DOTALL)
                    if json_match:
                        card_data = json.loads(json_match.group())
                    else:
                        card_data = {
                            "title": "세스코 맞춤 솔루션 견적",
                            "subtitle": "3일 무료 체험 프로모션 적용",
                            "items": [{"name": "맞춤 위생 서비스", "price": "3일 무상체험", "note": "상세 문의"}],
                            "promotion": "3일 체험 후 만족 시 결합 할인 적용"
                        }
                    
                    st.subheader("🖼️ **2. 카톡 전송용 완성형 그래픽 견적 카드**")
                    card_img_bytes = create_high_res_quote_card(card_data)
                    
                    st.image(card_img_bytes, caption="모바일 전용 초고해상도 견적 카드 (1200x1600)", use_container_width=True)
                    
                    st.download_button(
                        label="📥 **고해상도 견적 카드 다운로드 (.png)**",
                        data=card_img_bytes,
                        file_name="CES코_고해상도_견적카드.png",
                        mime="image/png",
                        use_container_width=True
                    )
                except Exception as img_err:
                    st.error(f"⚠️ 카드 이미지 생성 중 오류가 발생했습니다: {img_err}")

    # ==========================================
    # 📝 현장 영업일지 기록 (3일 체험 스케줄 자동 연동)
    # ==========================================
    with st.expander("📝 **플래너 현장 영업 미팅 일지 기록하기 (3일 체험 관리)**"):
        st.caption("방문 매장 내역을 기록하세요. '설치 완료' 입력 시 3일 뒤 피드백 및 계약 클로징 일정이 대시보드에 자동 등록됩니다.")
        with st.form("sales_log_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                planner_input = st.text_input("담당 플래너 이름 * (예: 홍길동)")
                client_input = st.text_input("방문 매장/고객명 * (예: 대박식당)")
                p_deal = st.text_input("제안 서비스 및 견적가 (예: 에어퍼퓸 3일체험 + 월 35,000원)")
                install_date_input = st.date_input("🗓️ 체험장비 설치일자", value=datetime.now())
            with col_b:
                eq_status = st.selectbox("🎁 체험장비 설치 여부", ["미설치", "설치 완료"])
                eq_item = st.text_input("설치한 체험장비 품목 (예: 에어퍼퓸, 에어제닉 B타입 등)")
                reaction = st.selectbox("고객 반응/상태", ["계약 완료 🎉", "3일 무상체험 설치 완료 🎁", "긍정적 (재방문 필요)", "보류 (가격 부담)"])
                memo = st.text_input("영업 메모 (예: 3일 뒤 목요일 오후 2시 방문하여 피드백 확인 및 계약서 작성)")
                
            submit_log = st.form_submit_button("💾 영업일지 저장 및 3일 체험 스케줄 연동", use_container_width=True)
            if submit_log:
                if planner_input and client_input:
                    with st.spinner("영업일지 저장 및 3일 체험 일정 계산 중..."):
                        save_sales_log(
                            planner_input, 
                            client_input, 
                            p_deal, 
                            eq_status, 
                            eq_item, 
                            reaction, 
                            memo, 
                            install_date=install_date_input.strftime("%Y-%m-%d")
                        )
                        st.toast("✅ 영업일지 저장 및 3일 체험 피드백 일정이 자동 연동되었습니다!", icon="🎉")
                        st.rerun()
                else:
                    st.warning("⚠️ 필수 항목(플래너 이름, 고객명)을 입력해 주세요.")
else:
    st.error("⚠️ Streamlit Cloud Secrets에 GEMINI_API_KEY가 설정되지 않았습니다.")
