# 한국 입양 통계 대시보드 (KOSIS OpenAPI + 공공데이터포털 + 복지부 보도자료)
#
# 실행:  pip install streamlit pandas requests plotly
#        KOSIS_API_KEY=발급받은키 streamlit run adoption_dashboard.py
#        (키가 없으면 보도자료 기반 2015~2025 fallback 데이터로 동작)
# 배포:  GitHub에 올린 뒤 Streamlit Community Cloud에 연결 -> 공개 URL.
#        Secrets 에 KOSIS_API_KEY (선택: DATA_GO_KR_KEY) 등록.
#
# 파일 구성 (같은 폴더에 두세요):
#   adoption_dashboard.py         이 파일
#   adoption_supplementary.json   성별/국가별/연령별/발생사유 (KOSIS 미제공 데이터)

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

HERE = Path(__file__).parent
SUPP = json.loads((HERE / "adoption_supplementary.json").read_text(encoding="utf-8"))


def secret(name: str) -> str:
    v = os.getenv(name, "")
    if v:
        return v
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


KOSIS_KEY = secret("KOSIS_API_KEY")
DATAGO_KEY = secret("DATA_GO_KR_KEY")  # 선택. 없으면 JSON에 내장된 성별 데이터 사용


# ---------------------------------------------------------------------------
# 1) KOSIS: 국내외 입양현황 (보건복지부 117 / DT_11770N001, 2000~2025)
#    분류 A01(국내외별): A03=계, A01=국내, A02=국외 / 항목 A02=입양현황 / 주기 Y
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60 * 60 * 24)  # 분당 200회 호출 제한 대비 하루 캐시
def load_kosis(api_key: str) -> pd.DataFrame:
    r = requests.get(
        "https://kosis.kr/openapi/Param/statisticsParameterData.do",
        params={
            "method": "getList", "apiKey": api_key,
            "orgId": "117", "tblId": "DT_11770N001",
            "objL1": "ALL", "itmId": "A02",
            "prdSe": "Y", "startPrdDe": "2000", "endPrdDe": "2030",
            "format": "json", "jsonVD": "Y",
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "err" in data:
        raise RuntimeError(f"KOSIS error {data.get('err')}: {data.get('errMsg')}")
    df = pd.DataFrame(data).rename(columns={"PRD_DE": "year", "C1_NM": "type", "DT": "count"})
    df["year"] = df["year"].astype(int)
    df["count"] = pd.to_numeric(df["count"].astype(str).str.replace(",", ""), errors="coerce")
    return df[["year", "type", "count"]]


def load_totals_fallback() -> pd.DataFrame:
    rows = []
    for r in SUPP["yearly_totals_fallback"]:
        rows += [
            {"year": r["year"], "type": "계", "count": r["total"]},
            {"year": r["year"], "type": "국내", "count": r["domestic"]},
            {"year": r["year"], "type": "국외", "count": r["intl"]},
        ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2) 성별: 공공데이터포털 "보건복지부_입양 아동 현황" (2010~2024)
#    - 파일 다운로드는 로그인 없이 가능. 오픈API는 활용신청 후 아래 endpoint.
#    - 2025년 값은 복지부 보도자료(2026.5)에서 보강 -> JSON 에 내장.
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60 * 60 * 24)
def load_sex_from_datago(api_key: str) -> pd.DataFrame:
    r = requests.get(
        "https://api.odcloud.kr/api/15127995/v1/uddi:c07beb15-6f96-4d5f-b7af-9c2a97acd857",
        params={"page": 1, "perPage": 500, "serviceKey": api_key},
        timeout=30,
    )
    r.raise_for_status()
    raw = pd.DataFrame(r.json()["data"])  # 컬럼: 연도, 구분명, 남성, 여성
    raw["scope"] = raw["구분명"].map({"입양아동_국내": "domestic", "입양아동_국외": "intl"})
    wide = raw.pivot(index="연도", columns="scope", values=["남성", "여성"])
    out = pd.DataFrame({
        "year": wide.index.astype(int),
        "domestic_male": wide[("남성", "domestic")].values,
        "domestic_female": wide[("여성", "domestic")].values,
        "intl_male": wide[("남성", "intl")].values,
        "intl_female": wide[("여성", "intl")].values,
    })
    return out


def load_sex() -> pd.DataFrame:
    builtin = pd.DataFrame(SUPP["by_sex"])
    if not DATAGO_KEY:
        return builtin
    try:
        live = load_sex_from_datago(DATAGO_KEY)
        # 포털 데이터 우선, 포털에 없는 연도(2025~)는 내장 데이터로 보강
        extra = builtin[~builtin["year"].isin(live["year"])]
        return pd.concat([live, extra]).sort_values("year").reset_index(drop=True)
    except Exception as e:  # 포털 장애 시 내장 데이터로 폴백
        st.warning(f"data.go.kr 호출 실패, 내장 데이터 사용: {e}")
        return builtin


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="한국 입양 통계 대시보드", layout="wide")
st.title("한국 국내·국외 입양 현황")
st.caption(
    "출처: 보건복지부 「가정위탁국내입양현황」(KOSIS DT_11770N001) · 공공데이터포털 15127995 · "
    "보건복지부 입양의 날 보도자료(2020~2026). 기준: 연내 법원 입양허가 완료 아동 수."
)

# --- 데이터 로드
if KOSIS_KEY:
    try:
        totals = load_kosis(KOSIS_KEY)
        src_note = "KOSIS OpenAPI (실시간)"
    except Exception as e:
        st.warning(f"KOSIS 호출 실패, 보도자료 fallback 사용: {e}")
        totals = load_totals_fallback()
        src_note = "보도자료 fallback"
else:
    st.info("KOSIS_API_KEY 미설정: 2015~2025 보도자료 데이터로 표시 중. 키를 넣으면 2000년부터 실시간 조회됩니다.")
    totals = load_totals_fallback()
    src_note = "보도자료 fallback"

sex = load_sex()
country = pd.DataFrame(SUPP["intl_by_country"])
age_dom = pd.DataFrame(SUPP["by_age"]["domestic"])
age_intl = pd.DataFrame(SUPP["by_age"]["intl"])
reason = pd.DataFrame(SUPP["reason"])

# --- 상단 지표
tot = totals[totals["type"] == "계"].sort_values("year")
latest, prev = tot.iloc[-1], tot.iloc[-2]
dom = totals[(totals["type"] == "국내") & (totals["year"] == latest.year)]["count"].iloc[0]
intl = totals[(totals["type"] == "국외") & (totals["year"] == latest.year)]["count"].iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric(f"{latest.year}년 전체 입양", f"{int(latest['count']):,}명", f"{int(latest['count'] - prev['count']):+,} vs 전년")
c2.metric("국내", f"{int(dom):,}명", f"{dom / latest['count']:.1%} 비중")
c3.metric("국외", f"{int(intl):,}명", f"{intl / latest['count']:.1%} 비중")
c4.metric("1958년 이후 누계", "250,540명", "국외 67.3%")
st.caption(f"연도별 합계 데이터 출처: {src_note}")

tab1, tab2, tab3, tab4 = st.tabs(["연도별 추이", "성별", "국외입양 국가별", "연령·발생사유"])

# --- Tab 1: 추이 (KOSIS)
with tab1:
    sub = totals[totals["type"].isin(["국내", "국외"])]
    st.plotly_chart(
        px.bar(sub, x="year", y="count", color="type", barmode="stack",
               title="연도별 국내·국외 입양 아동 수", labels={"year": "연도", "count": "명", "type": "구분"}),
        use_container_width=True,
    )
    share = sub.pivot(index="year", columns="type", values="count")
    share["국내 비중"] = share["국내"] / (share["국내"] + share["국외"])
    st.plotly_chart(
        px.line(share.reset_index(), x="year", y="국내 비중", markers=True,
                title="국내입양 비중 추이", labels={"year": "연도"}).update_yaxes(tickformat=".0%"),
        use_container_width=True,
    )
    with st.expander("원본 데이터"):
        st.dataframe(totals.pivot(index="year", columns="type", values="count"))

# --- Tab 2: 성별 (data.go.kr + 보도자료)
with tab2:
    long = sex.melt(id_vars="year", var_name="key", value_name="count")
    long["구분"] = long["key"].str.startswith("domestic").map({True: "국내", False: "국외"})
    long["성별"] = long["key"].str.endswith("male") & ~long["key"].str.endswith("female")
    long["성별"] = long["성별"].map({True: "남", False: "여"})
    col_a, col_b = st.columns(2)
    for col, scope in [(col_a, "국내"), (col_b, "국외")]:
        d = long[long["구분"] == scope]
        col.plotly_chart(
            px.bar(d, x="year", y="count", color="성별", barmode="stack",
                   title=f"{scope}입양 성별 (2010~{int(sex['year'].max())})",
                   labels={"year": "연도", "count": "명"},
                   color_discrete_map={"남": "#4C78A8", "여": "#F58518"}),
            use_container_width=True,
        )
    ratio = sex.assign(
        국내_여아비중=sex["domestic_female"] / (sex["domestic_male"] + sex["domestic_female"]),
        국외_남아비중=sex["intl_male"] / (sex["intl_male"] + sex["intl_female"]),
    )[["year", "국내_여아비중", "국외_남아비중"]].melt(id_vars="year", var_name="지표", value_name="비율")
    st.plotly_chart(
        px.line(ratio, x="year", y="비율", color="지표", markers=True,
                title="국내는 여아, 국외는 남아 비중이 높음", labels={"year": "연도"}).update_yaxes(tickformat=".0%"),
        use_container_width=True,
    )
    st.caption("2010~2024: 공공데이터포털 보건복지부_입양 아동 현황 / 2025: 보건복지부 2026.5 보도자료")
    with st.expander("원본 데이터"):
        st.dataframe(sex.set_index("year"))

# --- Tab 3: 국외입양 국가별 (보도자료)
with tab3:
    countries = [c for c in country.columns if c not in ("year", "total")]
    order = country[countries].sum().sort_values(ascending=False).index.tolist()
    clong = country.melt(id_vars=["year", "total"], value_vars=order, var_name="국가", value_name="count")
    clong["비중"] = clong["count"] / clong["total"]
    st.plotly_chart(
        px.bar(clong, x="year", y="count", color="국가", barmode="stack",
               category_orders={"국가": order}, title="국외입양 수용국별 아동 수 (2017~2024)",
               labels={"year": "연도", "count": "명"}),
        use_container_width=True,
    )
    yr = st.select_slider("연도 선택", options=country["year"].tolist(), value=int(country["year"].max()))
    row = clong[(clong["year"] == yr) & (clong["count"] > 0)].sort_values("count", ascending=False)
    col_p, col_t = st.columns([1, 1])
    col_p.plotly_chart(px.pie(row, names="국가", values="count", title=f"{yr}년 국외입양 {int(row['count'].sum())}명 국가별 비중", hole=0.4),
                       use_container_width=True)
    col_t.dataframe(row[["국가", "count", "비중"]].rename(columns={"count": "명"}).style.format({"비중": "{:.1%}"}),
                    hide_index=True, use_container_width=True)
    st.caption("출처: 보건복지부 입양의 날 보도자료(2020, 2023, 2024, 2025). 2025년(24명) 국가별 분포는 미공개.")
    with st.expander("원본 데이터"):
        st.dataframe(country.set_index("year"))

# --- Tab 4: 연령 및 발생사유 (보도자료)
with tab4:
    bands = SUPP["by_age"]["_bands"]
    col_1, col_2 = st.columns(2)
    for col, df_, name in [(col_1, age_dom, "국내"), (col_2, age_intl, "국외")]:
        m = df_.melt(id_vars=["year", "total"], value_vars=bands, var_name="연령", value_name="count")
        col.plotly_chart(
            px.bar(m, x="year", y="count", color="연령", barmode="stack", category_orders={"연령": bands},
                   title=f"{name}입양 연령대 (2023~2025)", labels={"year": "연도", "count": "명"}),
            use_container_width=True,
        )
    rcols = [c for c in reason.columns if c not in ("year", "total")]
    rm = reason.melt(id_vars=["year", "total"], value_vars=rcols, var_name="사유", value_name="count").dropna()
    st.plotly_chart(
        px.bar(rm, x="year", y="count", color="사유", barmode="stack", title="입양아동 발생 사유 (2022~2025)",
               labels={"year": "연도", "count": "명"}),
        use_container_width=True,
    )
    st.caption("출처: 보건복지부 2025.5 / 2026.5 보도자료 붙임 통계")
