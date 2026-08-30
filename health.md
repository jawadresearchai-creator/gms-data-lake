# Registry health report

Generated: 2026-08-30T09:54:03+00:00

- Checked: **131**
- Reachable: **108**
- Failing: **23**

## Failing entries

| Source | Dataset | Status | Diagnosis |
|---|---|---|---|
| `BTS_TRANSPORT` | `tsi_freight` | 403 | 403 from www.bts.gov: the host is refusing the client, not the request. Usually User-Agent/bot filtering or a geo block. Try a browser-like UA, add a Referer header, or use the hos |
| `CENSUS_BFS` | `bfs_apps_naics` | 404 | 404 from www.census.gov: the URL is stale. The dataset almost certainly moved; re-derive it from the host's current catalogue. |
| `CENSUS_RETAIL` | `marts_current` | 404 | 404 from www.census.gov: the URL is stale. The dataset almost certainly moved; re-derive it from the host's current catalogue. |
| `CROSSREF` | `crossref_journals` | 429 | 429 from api.crossref.org: rate limited. Lower rate_limit_per_sec for this source. |
| `FED_INDUSTRIAL_PRODUCTION` | `g17_ip_current` | 200 | 200 but Content-Type is text/html — this is a web page, not a file |
| `FRED_MD_QD` | `FRED_MD` | 200 | 200 but Content-Type is text/html — this is a web page, not a file |
| `FRED_MD_QD` | `FRED_QD` | 200 | 200 but Content-Type is text/html — this is a web page, not a file |
| `GLEIF_LEI` | `lei2_golden_copy` | 404 | 404 from leidata-preview.gleif.org: the URL is stale. The dataset almost certainly moved; re-derive it from the host's current catalogue. |
| `GLEIF_LEI` | `rr_golden_copy` | 404 | 404 from leidata-preview.gleif.org: the URL is stale. The dataset almost certainly moved; re-derive it from the host's current catalogue. |
| `ILOSTAT_BULK` | `EAR_4MTH_SEX_ECO_CUR_NB_Q` | 400 | HTTP 400 from rplumber.ilo.org. |
| `IRENA_CAPACITY` | `irena_capacity` | 403 | 403 from www.irena.org: the host is refusing the client, not the request. Usually User-Agent/bot filtering or a geo block. Try a browser-like UA, add a Referer header, or use the h |
| `NOAA_CLIMATE_INDICES` | `nina34` | - | no response (DNS or connection failure) |
| `NOAA_CLIMATE_INDICES` | `oni` | - | no response (DNS or connection failure) |
| `NOAA_CLIMATE_INDICES` | `pdo` | - | no response (DNS or connection failure) |
| `OWID_TRADE` | `merchandise-exports-gdpcp` | 404 | 404 from ourworldindata.org: the URL is stale. The dataset almost certainly moved; re-derive it from the host's current catalogue. |
| `UN_COMTRADE` | `comtrade_annual_sample` | 401 | 401 from comtradeapi.un.org: credentials required. Check the source's requires_secret entry. |
| `USASPENDING_ARCHIVE` | `federal_accounts` | 405 | HTTP 405 from api.usaspending.gov. |
| `USPTO_ODP` | `patent_grant_index` | - | no response (DNS or connection failure) |
| `US_TREASURY_FISCAL` | `treasury_daily_treasury_yield` | 404 | 404 from api.fiscaldata.treasury.gov: the URL is stale. The dataset almost certainly moved; re-derive it from the host's current catalogue. |
| `WIPO_STATISTICS` | `wipo_ip_statistics` | 200 | 200 but Content-Type is text/html — this is a web page, not a file |
| `WORLD_BANK_WITS` | `Concordance/HS_to_ISIC.zip` | 200 | 200 but Content-Type is text/html — this is a web page, not a file |
| `WORLD_BANK_WITS` | `CountryProfile/en/country/ALL/year/2022/tradeflow/EXPIMP/partner/WLD/product/all` | 200 | 200 but Content-Type is text/html — this is a web page, not a file |
| `WTO_TIMESERIES` | `wto_indicators` | 401 | 401 from api.wto.org: credentials required. Check the source's requires_secret entry. |

## Reachable entries

| Source | Dataset | Size | Type |
|---|---|---|---|
| `BIS_BULK` | `WS_CBPOL` | 4,099,697 | application/zip |
| `BIS_BULK` | `WS_CREDIT_GAP` | 252,401 | application/zip |
| `BIS_BULK` | `WS_EER` | 6,595,974 | application/zip |
| `BIS_BULK` | `WS_LONG_CPI` | 871,739 | application/zip |
| `BIS_BULK` | `WS_TC` | 1,803,310 | application/zip |
| `BIS_BULK` | `WS_XRU` | 10,308,359 | application/zip |
| `BLS_TIMESERIES` | `ce/ce.data.0.AllCESSeries` | 350,221,612 | application/octet-stream |
| `BLS_TIMESERIES` | `ce/ce.industry` | 58,769 | application/octet-stream |
| `BLS_TIMESERIES` | `ce/ce.series` | 3,941,924 | application/octet-stream |
| `BLS_TIMESERIES` | `ln/ln.data.1.AllData` | 389,674,039 | application/octet-stream |
| `BLS_TIMESERIES` | `ln/ln.series` | 15,288,538 | application/octet-stream |
| `CBOE_VOLATILITY` | `vix9d_history` | 199,928 | text/csv |
| `CBOE_VOLATILITY` | `vix_history` | 472,054 | text/csv |
| `CBOE_VOLATILITY` | `vvix_history` | 108,393 | text/csv |
| `CENSUS_BDS` | `bds2023_national` | 9,038 | text/csv |
| `CENSUS_BDS` | `bds2023_sec` | 146,764 | text/csv |
| `CENSUS_BDS` | `bds2023_st` | 377,485 | text/csv |
| `CENSUS_BFS` | `bfs_monthly_state` | — | text/csv |
| `CENSUS_CBP` | `2022/cbp22co.zip` | 13,723,814 | application/zip |
| `CENSUS_CBP` | `2022/cbp22st.zip` | 11,832,849 | application/zip |
| `CENSUS_CBP` | `2022/cbp22us.zip` | 778,618 | application/zip |
| `CFPB_COMPLAINTS` | `complaints_csv` | 1,423,555,825 | binary/octet-stream |
| `CFTC_COT` | `deacot2025` | 2,392,119 | application/zip |
| `CFTC_COT` | `fut_disagg_txt_2025` | 2,420,076 | application/zip |
| `CFTC_COT` | `fut_fin_txt_2025` | 627,068 | application/zip |
| `CROSSREF` | `crossref_members` | — | application/json |
| `ECB_SDMX` | `BLS` | — | text/csv |
| `ECB_SDMX` | `BSI` | — | text/csv |
| `ECB_SDMX` | `EXR` | — | text/csv |
| `EIA_BULK` | `bulk_manifest` | 20 | text/plain |
| `EIA_BULK` | `electricity_bulk` | 288,194,311 | application/x-zip-compressed |
| `EIA_BULK` | `total_energy_bulk` | 3,215,895 | application/x-zip-compressed |
| `EMDAT_DISASTERS` | `owid_disasters` | — | text/csv |
| `EPA_GHG` | `ghgrp_emissions` | 28,389,973 | application/zip |
| `EU_TED_PROCUREMENT` | `ted_csv_2024` | 925,039 | application/json |
| `FDIC_BANKFIND` | `fdic_failures` | — | text/csv |
| `FDIC_BANKFIND` | `fdic_institutions` | — | text/csv |
| `FDIC_BANKFIND` | `fdic_locations` | — | text/csv |
| `FDIC_BANKFIND` | `fdic_sod` | — | text/csv |
| `FEDERAL_REGISTER_API` | `agencies` | 166,022 | application/json |
| `FEDERAL_REGISTER_API` | `recent_rules` | 288,946 | application/json |
| `FEDERAL_REGISTER_BULK` | `FR_2015` | 149,497,649 | application/zip |
| `FEDERAL_REGISTER_BULK` | `FR_2016` | 176,325,817 | application/zip |
| `FEDERAL_REGISTER_BULK` | `FR_2017` | 111,159,540 | application/zip |
| `FINRA_SHORT_SALE` | `short_sale_daily_index` | — | text/plain |
| `FRED_CONSUMER` | `CPIAUCSL` | 17,725 | application/csv |
| `FRED_CONSUMER` | `CPILFESL` | 15,565 | application/csv |
| `FRED_CONSUMER` | `PCEPI` | 14,729 | application/csv |
| `FRED_CONSUMER` | `PSAVERT` | — | application/csv |
| `FRED_CONSUMER` | `UMCSENT` | 13,406 | application/csv |
| `FRED_INVENTORIES` | `BUSINV` | — | application/csv |
| `FRED_INVENTORIES` | `ISRATIO` | 6,649 | application/csv |
| `FRED_INVENTORIES` | `RETAILIRSA` | — | application/csv |
| `FRED_INVENTORIES` | `TOTBUSMPCIMSA` | — | application/csv |
| `GDELT_RECENT` | `20260829041500.export.CSV.zip` | 36,145 | application/zip |
| `GDELT_RECENT` | `20260829043000.export.CSV.zip` | 49,129 | application/zip |
| `GEONAMES` | `admin1CodesASCII` | 151,536 | text/plain |
| `GEONAMES` | `cities15000` | 3,310,890 | application/zip |
| `GEONAMES` | `countryInfo` | 31,678 | text/plain |
| `ILOSTAT_BULK` | `EMP_TEMP_SEX_AGE_NB_A` | — | application/octet-stream |
| `ILOSTAT_BULK` | `UNE_TUNE_SEX_AGE_NB_A` | — | application/octet-stream |
| `IMF_WEO` | `WEO_current` | 20 | application/vnd.openxmlformats-officedoc |
| `KENNETH_FRENCH_FACTORS` | `F-F_Momentum_Factor` | 5,610 | application/x-zip-compressed |
| `KENNETH_FRENCH_FACTORS` | `F-F_Research_Data_5_Factors_2x3` | 11,901 | application/x-zip-compressed |
| `KENNETH_FRENCH_FACTORS` | `F-F_Research_Data_5_Factors_2x3_daily` | 149,894 | application/x-zip-compressed |
| `KENNETH_FRENCH_FACTORS` | `F-F_Research_Data_Factors` | 13,052 | application/x-zip-compressed |
| `KENNETH_FRENCH_FACTORS` | `F-F_Research_Data_Factors_daily` | 177,852 | application/x-zip-compressed |
| `NASDAQ_SYMBOL_DIRECTORY` | `nasdaqlisted` | 72,586 | text/plain |
| `NASDAQ_SYMBOL_DIRECTORY` | `otherlisted` | 148,226 | text/plain |
| `NYFED_GSCPI` | `gscpi` | 105,984 | application/vnd.ms-excel |
| `OECD_EDUCATION` | `DSD_REG_EDU@DF_ATTAIN` | — | application/vnd.sdmx.data+csv |
| `OECD_EDUCATION` | `DSD_REG_EDU@DF_EDU` | — | application/vnd.sdmx.data+csv |
| `OECD_ICIO` | `DSD_REV_ASAP@DF_REVKAZ` | — | application/vnd.sdmx.data+csv |
| `OECD_ICIO` | `DSD_REV_ASAP@DF_REVKGZ` | — | application/vnd.sdmx.data+csv |
| `OECD_SDMX` | `DSD_FUA_TRAN@DF_PT_ACCESS` | — | application/vnd.sdmx.data+csv |
| `OECD_SDMX` | `DSD_REV_AFRICA@DF_REVCOD` | — | application/vnd.sdmx.data+csv |
| `OECD_SDMX` | `DSD_SUBEMP@DF_SUBEMP` | — | application/vnd.sdmx.data+csv |
| `OWID_CO2` | `owid_co2` | 14,280,395 | text/csv |
| `OWID_CO2` | `owid_energy` | 9,227,319 | binary/octet-stream |
| `OWID_DIGITAL` | `broadband-penetration-by-country` | — | text/csv |
| `OWID_DIGITAL` | `mobile-cellular-subscriptions-per-100-people` | — | text/csv |
| `OWID_DIGITAL` | `number-of-internet-users` | — | text/csv |
| `OWID_DIGITAL` | `share-of-individuals-using-the-internet` | — | text/csv |
| `OWID_TRADE` | `foreign-direct-investment-net-inflows-of-gdp` | — | text/csv |
| `OWID_TRADE` | `trade-as-share-of-gdp` | — | text/csv |
| `POLICY_UNCERTAINTY` | `All_Country_Data.xlsx` | 130,388 | application/vnd.openxmlformats-officedoc |
| `POLICY_UNCERTAINTY` | `Global_Policy_Uncertainty_Data.xlsx` | 18,366 | application/vnd.openxmlformats-officedoc |
| `POLICY_UNCERTAINTY` | `US_Policy_Uncertainty_Data.xlsx` | 89,602 | application/vnd.openxmlformats-officedoc |
| `SEC_FINANCIAL_STATEMENT_SETS` | `2024q1` | 124,336,804 | application/octet-stream |
| `SEC_FINANCIAL_STATEMENT_SETS` | `2024q2` | 119,119,954 | application/octet-stream |
| `SEC_FINANCIAL_STATEMENT_SETS` | `2024q3` | 118,280,418 | application/octet-stream |
| `SEC_FINANCIAL_STATEMENT_SETS` | `2024q4` | 122,932,548 | application/octet-stream |
| `SEC_IDENTIFIERS` | `company_tickers` | 219,016 | application/json |
| `SEC_IDENTIFIERS` | `company_tickers_exchange` | 181,040 | application/json |
| `SEC_INDUSTRY_SIC` | `naics_2022` | 82,460 | application/vnd.openxmlformats-officedoc |
| `USASPENDING_ARCHIVE` | `agency_list` | 52,900 | application/json |
| `US_TREASURY_FISCAL` | `treasury_avg_interest_rates` | 38,077 | text/csv |
| `US_TREASURY_FISCAL` | `treasury_debt_to_penny` | 229,200 | text/csv |
| `WHO_GHO` | `gho_dimensions` | — | application/json |
| `WHO_GHO` | `gho_indicators` | — | application/json |
| `WORLD_BANK_API` | `WB_IDS` | — | application/json |
| `WORLD_BANK_API` | `WB_WDI` | — | application/json |
| `WORLD_BANK_API` | `WB_WGI` | — | application/json |
| `WORLD_BANK_BULK` | `GEM_CSV` | 11,283,137 | application/x-zip-compressed |
| `WORLD_BANK_BULK` | `IDS_CSV` | 11,142,704 | application/x-zip-compressed |
| `WORLD_BANK_BULK` | `WDI_CSV` | 282,845,220 | application/octet-stream |
| `WORLD_BANK_BULK` | `commodity_prices_monthly` | — | application/vnd.openxmlformats-officedoc |
| `WORLD_BANK_GOVERNANCE` | `wgi_excel` | — | application/vnd.openxmlformats-officedoc |
