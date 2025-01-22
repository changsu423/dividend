import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import json
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO

# Load environment variables
load_dotenv()
DART_API_KEY = os.getenv('DART_API_KEY')

# Cache decorators for API calls
@st.cache_data(ttl=3600)
def get_dart_corp_codes():
    """DART에서 한국 주식 회사 코드 조회"""
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    params = {'crtfc_key': DART_API_KEY}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        with zipfile.ZipFile(BytesIO(response.content)) as z:
            with z.open('CORPCODE.xml') as xml_file:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                data = []
                for company in root.findall('.//list'):
                    corp_code = company.findtext('corp_code')
                    corp_name = company.findtext('corp_name')
                    stock_code = company.findtext('stock_code')
                    if stock_code and stock_code.strip():
                        data.append({
                            'corp_code': corp_code,
                            'corp_name': corp_name,
                            'stock_code': stock_code
                        })
                
                return pd.DataFrame(data)
    except Exception as e:
        st.error(f"회사 코드 데이터 조회 실패: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_krx_etf_list():
    """한국거래소 ETF 목록 조회"""
    try:
        url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        params = {
            'bld': 'dbms/MDC/STAT/standard/MDCSTAT04601',
            'locale': 'ko_KR',
        }
        
        response = requests.post(url, headers=headers, data=params)
        response.raise_for_status()
        
        data = response.json()
        df = pd.DataFrame(data['output'])
        df = df[['ISU_SRT_CD', 'ISU_NM', 'ISU_CD']]
        df.columns = ['종목코드', '종목명', '표준코드']
        return df
        
    except Exception as e:
        st.error(f"ETF 목록 조회 실패: {str(e)}")
        return pd.DataFrame()

def get_korean_stock_dividend(corp_code, year, reprt_code="11011"):
    """한국 주식 배당 정보 조회"""
    url = "https://opendart.fss.or.kr/api/alotMatter.json"
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
        'bsns_year': year,
        'reprt_code': reprt_code
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
        
    except Exception as e:
        return None, f"배당 정보 조회 실패: {str(e)}"

def get_korean_etf_distribution(code, start_date, end_date):
    """한국 ETF 분배금 정보 조회"""
    try:
        url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        params = {
            'bld': 'dbms/MDC/STAT/standard/MDCSTAT04701',
            'searchType': '1',
            'isuCd': code,
            'strtDd': start_date.strftime('%Y%m%d'),
            'endDd': end_date.strftime('%Y%m%d')
        }
        
        response = requests.post(url, headers=headers, data=params)
        response.raise_for_status()
        
        data = response.json()
        if not data.get('output'):
            return pd.DataFrame(), "해당 기간의 분배금 정보가 없습니다."
            
        df = pd.DataFrame(data['output'])
        column_mapping = {
            'ETF_NM': 'ETF명',
            'BAS_DD': '기준일',
            'PAY_DD': '지급일',
            'CAS_DSB': '현금분배금',
            'STK_DSB': '주식분배금',
            'TOT_DSB': '총분배금'
        }
        df = df.rename(columns=column_mapping)
        
        # 금액 컬럼 숫자로 변환
        for col in ['현금분배금', '주식분배금', '총분배금']:
            df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce')
            
        return df, None
        
    except Exception as e:
        return None, f"분배금 정보 조회 실패: {str(e)}"

def get_us_stock_data(ticker, period="1y"):
    """미국 주식 데이터 조회"""
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period=period)
        info = stock.info
        dividends = stock.dividends
        return history, info, dividends, None
    except Exception as e:
        return None, None, None, f"데이터 조회 실패: {str(e)}"

def get_us_etf_data(ticker, period="1y"):
    """미국 ETF 데이터 조회"""
    try:
        etf = yf.Ticker(ticker)
        history = etf.history(period=period)
        info = etf.info
        distributions = etf.dividends  # ETF의 경우 배당금이 분배금을 포함
        return history, info, distributions, None
    except Exception as e:
        return None, None, None, f"데이터 조회 실패: {str(e)}"

def main():
    st.set_page_config(
        page_title="글로벌 주식/ETF 분석 대시보드",
        page_icon="📊",
        layout="wide"
    )
    
    st.title('📊 글로벌 주식/ETF 분석 대시보드')
    
    # 시장과 자산 유형 선택
    col1, col2 = st.sidebar.columns(2)
    with col1:
        market = st.radio("시장 선택", ["한국", "미국"])
    with col2:
        asset_type = st.radio("자산 유형", ["주식", "ETF"])
    
    # 선택에 따른 화면 렌더링
    if market == "한국":
        if asset_type == "주식":
            render_korean_stock_section()
        else:
            render_korean_etf_section()
    else:
        if asset_type == "주식":
            render_us_stock_section()
        else:
            render_us_etf_section()

def render_korean_stock_section():
    st.sidebar.subheader("한국 주식 검색")
    corp_codes_df = get_dart_corp_codes()
    
    search_method = st.sidebar.radio(
        "검색 방식",
        ["회사명으로 검색", "종목코드로 검색"]
    )
    
    if search_method == "회사명으로 검색":
        company_name = st.sidebar.text_input("회사명 입력", placeholder="예: 삼성전자")
        if company_name:
            matches = corp_codes_df[corp_codes_df['corp_name'].str.contains(company_name, case=False)]
            if not matches.empty:
                selected = st.sidebar.selectbox(
                    "회사 선택",
                    matches['corp_name'].tolist(),
                    format_func=lambda x: f"{x} ({matches[matches['corp_name']==x]['stock_code'].iloc[0]})"
                )
                display_korean_stock_info(matches[matches['corp_name']==selected]['corp_code'].iloc[0])
    else:
        stock_code = st.sidebar.text_input("종목코드 입력", placeholder="예: 005930")
        if stock_code:
            matches = corp_codes_df[corp_codes_df['stock_code']==stock_code]
            if not matches.empty:
                display_korean_stock_info(matches['corp_code'].iloc[0])

def render_korean_etf_section():
    st.sidebar.subheader("한국 ETF 검색")
    etf_list = get_krx_etf_list()
    
    search_term = st.sidebar.text_input("ETF 이름 검색", placeholder="예: KODEX 200")
    if search_term:
        matched_etfs = etf_list[etf_list['종목명'].str.contains(search_term, case=False)]
        if not matched_etfs.empty:
            selected = st.sidebar.selectbox(
                "ETF 선택",
                matched_etfs['종목명'].tolist(),
                format_func=lambda x: f"{x} ({matched_etfs[matched_etfs['종목명']==x]['종목코드'].iloc[0]})"
            )
            display_korean_etf_info(matched_etfs[matched_etfs['종목명']==selected]['표준코드'].iloc[0])

def render_us_stock_section():
    st.sidebar.subheader("미국 주식 검색")
    ticker = st.sidebar.text_input("티커 심볼 입력", placeholder="예: AAPL, MSFT")
    if ticker:
        period = st.sidebar.selectbox(
            "조회 기간",
            ['1mo', '3mo', '6mo', '1y', '2y', '5y'],
            format_func=lambda x: {
                '1mo': '1개월', '3mo': '3개월', '6mo': '6개월',
                '1y': '1년', '2y': '2년', '5y': '5년'
            }[x]
        )
        display_us_stock_info(ticker, period)

def render_us_etf_section():
    st.sidebar.subheader("미국 ETF 검색")
    ticker = st.sidebar.text_input("티커 심볼 입력", placeholder="예: SPY, QQQ")
    if ticker:
        period = st.sidebar.selectbox(
            "조회 기간",
            ['1mo', '3mo', '6mo', '1y', '2y', '5y'],
            format_func=lambda x: {
                '1mo': '1개월', '3mo': '3개월', '6mo': '6개월',
                '1y': '1년', '2y': '2년', '5y': '5년'
            }[x]
        )
        display_us_etf_info(ticker, period)

def display_korean_stock_info(corp_code):
    year = st.sidebar.slider("배당 정보 사업연도 선택", 2015, 2024, 2023)
    report_types = {
        "11011": "사업보고서",
        "11012": "반기보고서",
        "11013": "1분기보고서",
        "11014": "3분기보고서"
    }
    reprt_code = st.sidebar.selectbox(
        "보고서 종류",
        options=list(report_types.keys()),
        format_func=lambda x: report_types[x]
    )
    
    data, error = get_korean_stock_dividend(corp_code, year, reprt_code)
    if error:
        st.error(error)
    elif not data.empty:
        st.header(f"📈 배당 정보 ({year}년 {report_types[reprt_code]})")
        st.dataframe(data, use_container_width=True)

def display_korean_etf_info(etf_code):
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "시작일",
            value=datetime.now() - timedelta(days=365),
            max_value=datetime.now()
        )
    with col2:
        end_date = st.date_input(
            "종료일",
            value=datetime.now(),
            max_value=datetime.now()
        )
    
    data, error = get_korean_etf_distribution(etf_code, start_date, end_date)
    if error:
        st.error(error)
    elif not data.empty:
        display_distribution_summary(data)
        display_distribution_chart(data)

def display_us_stock_info(ticker, period):
    """미국 주식 정보 디스플레이"""
    history, info, dividends, error = get_us_stock_data(ticker, period)
    if error:
        st.error(error)
    else:
        st.header(f"📈 {info.get('shortName', ticker)} 주식 정보")
        st.subheader("주가 데이터")
        st.dataframe(history, use_container_width=True)

        # 주가 차트
        fig = go.Figure(data=[
            go.Candlestick(
                x=history.index,
                open=history['Open'],
                high=history['High'],
                low=history['Low'],
                close=history['Close'],
                name="주가"
            )
        ])
        fig.update_layout(
            title=f"{ticker} 주가 추이",
            yaxis_title="주가",
            xaxis_title="날짜",
            template="plotly_white"
        )
        st.plotly_chart(fig)

        # 배당 데이터
        if not dividends.empty:
            st.subheader("배당 데이터")
            st.dataframe(dividends, use_container_width=True)
            st.line_chart(dividends, use_container_width=True)

def display_us_etf_info(ticker, period):
    """미국 ETF 정보 디스플레이"""
    history, info, distributions, error = get_us_etf_data(ticker, period)
    if error:
        st.error(error)
    else:
        st.header(f"📊 {info.get('shortName', ticker)} ETF 정보")
        st.subheader("주가 데이터")
        st.dataframe(history, use_container_width=True)

        # ETF 주가 차트
        fig = go.Figure(data=[
            go.Candlestick(
                x=history.index,
                open=history['Open'],
                high=history['High'],
                low=history['Low'],
                close=history['Close'],
                name="ETF 주가"
            )
        ])
        fig.update_layout(
            title=f"{ticker} ETF 주가 추이",
            yaxis_title="주가",
            xaxis_title="날짜",
            template="plotly_white"
        )
        st.plotly_chart(fig)

        # 분배금 데이터
        if not distributions.empty:
            st.subheader("분배금 데이터")
            st.dataframe(distributions, use_container_width=True)
            st.line_chart(distributions, use_container_width=True)

def display_distribution_summary(data):
    """ETF 분배금 요약"""
    total_distributions = data["총분배금"].sum()
    st.metric("총 분배금", f"{total_distributions:,.0f} 원")

def display_distribution_chart(data):
    """ETF 분배금 차트"""
    fig = go.Figure(
        data=[go.Bar(x=data['지급일'], y=data['총분배금'], name='총 분배금')]
    )
    fig.update_layout(
        title="ETF 분배금 추이",
        yaxis_title="총 분배금",
        xaxis_title="지급일",
        template="plotly_white"
    )
    st.plotly_chart(fig)

# 앱 실행
if __name__ == "__main__":
    main()
