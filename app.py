import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
import os

# .env 파일에서 API 키 불러오기
load_dotenv()
DART_API_KEY = os.getenv('DART_API_KEY')

# 한국 주식 데이터 가져오기 (DART API)
def get_korean_stock_data(corp_code, year):
    """DART API를 이용해 한국 주식의 배당 정보를 가져옵니다."""
    url = "https://opendart.fss.or.kr/api/alotMatter.json"
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
        'bsns_year': year
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None, f"API 요청 오류: {response.status_code}"
    
    data = response.json()
    if data.get('status') != "000":
        return None, f"DART API 오류: {data.get('message')}"

    # 데이터프레임으로 변환
    return pd.DataFrame(data.get('list', [])), None

# 미국 주식 데이터 가져오기 (Yahoo Finance)
def get_us_stock_data(ticker, period="1y"):
    """Yahoo Finance에서 주식 데이터를 가져옵니다."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        info = stock.info
        return df, info, None
    except Exception as e:
        return None, None, f"데이터를 가져오는 중 오류가 발생했습니다: {str(e)}"

# Streamlit 앱 구현
st.title('📊 한국 및 미국 주식 차트 및 배당 정보')

# 사이드바에서 시장 선택
market = st.sidebar.radio("시장 선택", ["한국", "미국"])

if market == "한국":
    # DART에서 한국 주식 처리
    st.sidebar.subheader("한국 주식 검색")
    corp_code = st.sidebar.text_input("종목 코드 (6자리, 예: 삼성전자 = 005930)")
    year = st.sidebar.slider("배당 정보 사업연도 선택", 2000, 2025, 2024)

    if corp_code:
        data, error = get_korean_stock_data(corp_code, year)
        if error:
            st.error(error)
        else:
            st.header(f"📈 {corp_code} 배당 정보 ({year}년)")
            st.dataframe(data)
else:
    # Yahoo Finance에서 미국 주식 처리
    st.sidebar.subheader("미국 주식 검색")
    ticker = st.sidebar.text_input("티커 심볼 입력 (예: AAPL, TSLA)")
    period = st.sidebar.selectbox("데이터 기간", ['1mo', '3mo', '6mo', '1y', '2y'], format_func=lambda x: {
        '1mo': '1개월',
        '3mo': '3개월',
        '6mo': '6개월',
        '1y': '1년',
        '2y': '2년',
    }[x])

    if ticker:
        stock_data, stock_info, error = get_us_stock_data(ticker, period)
        if error:
            st.error(error)
        else:
            st.header(f"📈 {ticker} 주가 차트 및 배당 정보")
            st.metric("현재가", f"${stock_info['currentPrice']:,.2f}")
            if "dividendYield" in stock_info and stock_info["dividendYield"] is not None:
                st.metric("시가배당률", f"{stock_info['dividendYield'] * 100:.2f}%")

            # 주가 차트 그리기
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=stock_data.index,
                open=stock_data['Open'],
                high=stock_data['High'],
                low=stock_data['Low'],
                close=stock_data['Close'],
                name="주가"
            ))
            fig.update_layout(
                title=f"{ticker} 주가 차트",
                xaxis_title="날짜",
                yaxis_title="가격",
                template="plotly_white"
            )
            st.plotly_chart(fig)

---

### 2. **GitHub 파일 구조**

```plaintext
my-stock-analysis/

# .env                     # DART API 키를 저장하는 파일 (로컬에 저장)
# requirements.txt         # Python 의존성 라이브러리 목록
# app.py                   # Streamlit 메인 코드
# README.md                # 프로젝트 설명 문서
