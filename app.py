import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
DART_API_KEY = os.getenv('DART_API_KEY')

def get_korean_stock_data(corp_code, year, reprt_code="11011"):
    """
    Fetch dividend information for Korean stocks using the DART API.
    
    Args:
        corp_code (str): Company code (6 digits)
        year (int): Business year
        reprt_code (str): Report code
            - "11011": 사업보고서
            - "11012": 반기보고서
            - "11013": 1분기보고서
            - "11014": 3분기보고서
        
    Returns:
        tuple: (DataFrame of dividend data, error message if any)
    """
    url = "https://opendart.fss.or.kr/api/alotMatter.json"
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
        'bsns_year': year,
        'reprt_code': reprt_code  # 사업보고서 기준
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        if data.get('status') != "000":
            return None, f"DART API 오류: {data.get('message')}"
            
        if not data.get('list'):
            return pd.DataFrame(), "데이터가 없습니다."
            
        df = pd.DataFrame(data['list'])
        
        # 컬럼명을 한글로 변경
        column_mapping = {
            'thstrm': '당기',
            'frmtrm': '전기',
            'lwfr': '전전기',
            'stock_knd': '주식 종류',
            'thstrm_dd': '당기 배당일',
            'frmtrm_dd': '전기 배당일',
            'lwfr_dd': '전전기 배당일'
        }
        
        df = df.rename(columns=column_mapping)
        return df, None
        
    except requests.exceptions.RequestException as e:
        return None, f"API 요청 오류: {str(e)}"

def get_us_stock_data(ticker, period="1y"):
    """
    Fetch stock data from Yahoo Finance.
    
    Args:
        ticker (str): Stock ticker symbol
        period (str): Time period for data (e.g., '1y', '6mo')
        
    Returns:
        tuple: (DataFrame of stock data, stock info dict, error message if any)
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        info = stock.info
        return df, info, None
    except Exception as e:
        return None, None, f"데이터를 가져오는 중 오류가 발생했습니다: {str(e)}"

def main():
    st.set_page_config(
        page_title="주식 분석 대시보드",
        page_icon="📊",
        layout="wide"
    )
    
    st.title('📊 한국 및 미국 주식 차트 및 배당 정보')
    
    # Market selection in sidebar
    market = st.sidebar.radio("시장 선택", ["한국", "미국"])
    
    if market == "한국":
        render_korean_stock_section()
    else:
        render_us_stock_section()

def render_korean_stock_section():
    st.sidebar.subheader("한국 주식 검색")
    
    # 종목 코드 입력
    corp_code = st.sidebar.text_input(
        "종목 코드 입력", 
        placeholder="6자리 코드 (예: 005930)",
        help="삼성전자: 005930, SK하이닉스: 000660"
    )
    
    # 사업연도 선택
    year = st.sidebar.slider("배당 정보 사업연도 선택", 2000, 2025, 2024)
    
    # 보고서 종류 선택
    report_types = {
        "11011": "사업보고서",
        "11012": "반기보고서",
        "11013": "1분기보고서",
        "11014": "3분기보고서"
    }
    reprt_code = st.sidebar.selectbox(
        "보고서 종류",
        options=list(report_types.keys()),
        format_func=lambda x: report_types[x],
        help="조회할 보고서 종류를 선택하세요"
    )
    
    if corp_code:
        if len(corp_code) != 6:
            st.error("종목 코드는 6자리여야 합니다.")
            return
            
        data, error = get_korean_stock_data(corp_code, year, reprt_code)
        
        if error:
            if "데이터가 없습니다" in error:
                st.warning(f"{year}년 {report_types[reprt_code]}의 배당 정보가 없습니다.")
            else:
                st.error(error)
        elif data.empty:
            st.warning("해당 연도의 배당 정보가 없습니다.")
        else:
            st.header(f"📈 {corp_code} 배당 정보 ({year}년 {report_types[reprt_code]})")
            st.dataframe(data, use_container_width=True)

def render_us_stock_section():
    st.sidebar.subheader("미국 주식 검색")
    ticker = st.sidebar.text_input(
        "티커 심볼 입력", 
        placeholder="예: AAPL, TSLA",
        help="AAPL: Apple, MSFT: Microsoft"
    )
    
    period_options = {
        '1mo': '1개월', '3mo': '3개월', '6mo': '6개월',
        '1y': '1년', '2y': '2년'
    }
    period = st.sidebar.selectbox(
        "데이터 기간", 
        list(period_options.keys()),
        format_func=lambda x: period_options[x]
    )
    
    if ticker:
        stock_data, stock_info, error = get_us_stock_data(ticker, period)
        if error:
            st.error(error)
        else:
            display_us_stock_info(ticker, stock_data, stock_info)

def display_us_stock_info(ticker, stock_data, stock_info):
    # Create two columns for metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("현재가", f"${stock_info['currentPrice']:,.2f}")
    with col2:
        if "dividendYield" in stock_info and stock_info["dividendYield"] is not None:
            st.metric("시가배당률", f"{stock_info['dividendYield'] * 100:.2f}%")
    with col3:
        if "marketCap" in stock_info:
            market_cap_b = stock_info['marketCap'] / 1e9
            st.metric("시가총액", f"${market_cap_b:.1f}B")

    # Create candlestick chart
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
        yaxis_title="가격 (USD)",
        template="plotly_white",
        height=600
    )
    
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
