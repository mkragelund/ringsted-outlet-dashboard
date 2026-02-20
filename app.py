import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- KONFIGURATION ---
INV_NAME, INV_CAT, INV_ID, INV_QTY, INV_COST, INV_RRP = 'produktnavn', 'kategorinavn', 'stregkode', 'Lager', 'kostpris', 'DKKRRP'
SALES_NAME, SALES_CAT, SALES_ID, SALES_QTY, SALES_PRICE = 'Produktnavn', 'kategorinavn', 'stregkode', 'Salg', 'salgspris'
INVENTORY_FILE, SALES_FILE, DATE_FILE = 'master_inventory.csv', 'master_sales.csv', 'dates.csv'

SIGNAL_CODES = ['500', '550', '600', '601', '602', '604', '611', '612', '613', '614', 
                '621', '622', '623', '624', '631', '632', '633', '634', '641', '642', 
                '643', '644', '650', '651', '671', '693']

# --- HJÆLPEFUNKTIONER ---
def get_brand(season_code):
    return "Signal" if str(season_code).strip() in SIGNAL_CODES else "Co'Couture"

def get_brand_logo(brand_name):
    """Matcher dine filnavne i mappen."""
    if brand_name == "Signal":
        return "Signal logo.jpg"
    elif brand_name == "Co'Couture":
        return "Cocouture logo.jpg"
    return None

def load_data(file_path):
    return pd.read_csv(file_path) if os.path.exists(file_path) else pd.DataFrame()

def save_dates(inv_date, sales_start, sales_end):
    df = pd.DataFrame({'type': ['inv', 'sales_start', 'sales_end'], 'date': [inv_date, sales_start, sales_end]})
    df.to_csv(DATE_FILE, index=False)

def split_product_details(name):
    name = str(name).strip()
    sep = '-' if '-' in name else '|'
    parts = name.split(sep)
    res = {'Sæson': 'Ukendt', 'Stylenummer': 'Ukendt', 'Style_Navn': name, 'Størrelse': 'N/A'}
    if len(parts) >= 4:
        res['Sæson'], res['Stylenummer'], res['Style_Navn'], res['Størrelse'] = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[-1].strip()
    elif len(parts) > 1:
        res['Style_Navn'], res['Størrelse'] = sep.join(parts[:-1]).strip(), parts[-1].strip()
    return pd.Series(res)

# --- APP SETUP ---
st.set_page_config(page_title="Ringsted Outlet Dashboard", layout="wide")
st.title("📊 Ringsted Outlet Dashboard")

menu = st.sidebar.radio("Menu", ["Dashboard", "Størrelses Analyse", "Lager Analyse", "Strategisk Analyse", "Indkøbs Forslag", "Upload Data"])

if menu == "Upload Data":
    st.header("Konfiguration af Data")
    col_a, col_b = st.columns(2)
    with col_a:
        inv_date = st.date_input("Dato for lageropgørelse", datetime.now())
        f_inv = st.file_uploader("Upload Lagerfil", type=['xlsx', 'csv'])
    with col_b:
        s_start = st.date_input("Start dato", datetime.now())
        s_end = st.date_input("Slut dato", datetime.now())
        f_sales = st.file_uploader("Upload Salgsfil", type=['xlsx', 'csv'])
    if st.button("💾 GEM OG OPDATER"):
        if f_inv and f_sales:
            try:
                df_i = pd.read_excel(f_inv) if f_inv.name.endswith('xlsx') else pd.read_csv(f_inv)
                df_s = pd.read_excel(f_sales) if f_sales.name.endswith('xlsx') else pd.read_csv(f_sales)
                df_i.to_csv(INVENTORY_FILE, index=False); df_s.to_csv(SALES_FILE, index=False)
                save_dates(inv_date, s_start, s_end)
                st.success("Data gemt korrekt! Skift nu menu for at se resultatet.")
            except Exception as e: st.error(f"Fejl: {e}")

else:
    inv, sales, dates = load_data(INVENTORY_FILE), load_data(SALES_FILE), load_data(DATE_FILE)
    if not inv.empty and not sales.empty and not dates.empty:
        # Præ-processering
        for df in [inv, sales]:
            name_col = INV_NAME if INV_NAME in df.columns else SALES_NAME
            details = df[name_col].apply(split_product_details)
            for col in details.columns: df[col] = details[col]
            df['Brand'] = df['Sæson'].apply(get_brand)
            
        for c in [INV_QTY, INV_COST, INV_RRP]: 
            if c in inv.columns: inv[c] = pd.to_numeric(inv[c], errors='coerce').fillna(0)
        for c in [SALES_QTY, SALES_PRICE]: sales[c] = pd.to_numeric(sales[c], errors='coerce').fillna(0)
        
        skrald = ['total', 'diverse', 'pose', 'gaveindpakning', 'gebyr']
        sales = sales[~sales[SALES_NAME].astype(str).str.lower().str.contains('|'.join(skrald))]

        # SIDEBAR FILTRE
        st.sidebar.header("🔍 Analyse Filtre")
        sel_brand = st.sidebar.multiselect("Vælg Brand", ["Signal", "Co'Couture"])
        
        # VIS LOGO HVIS ÉT BRAND ER VALGT
        if len(sel_brand) == 1:
            logo_fn = get_brand_logo(sel_brand[0])
            if logo_fn and os.path.exists(logo_fn):
                st.sidebar.image(logo_fn, use_container_width=True)

        sel_cat = st.sidebar.selectbox("Kategori", ["Alle"] + sorted(inv[INV_CAT].dropna().unique().tolist()))
        
        f_inv, f_sales = inv.copy(), sales.copy()
        if sel_brand:
            f_inv, f_sales = f_inv[f_inv['Brand'].isin(sel_brand)], f_sales[f_sales['Brand'].isin(sel_brand)]
        if sel_cat != "Alle":
            f_inv, f_sales = f_inv[f_inv[INV_CAT] == sel_cat], f_sales[f_sales[SALES_CAT] == sel_cat]

        # Fælles Beregninger
        merged_sales = pd.merge(f_sales, inv[[INV_ID, INV_COST, INV_RRP]], left_on=SALES_ID, right_on=INV_ID, how='left')
        merged_sales[INV_COST] = merged_sales[INV_COST].fillna(0)
        merged_sales[INV_RRP] = merged_sales[INV_RRP].fillna(merged_sales[SALES_PRICE])
        revenue = f_sales[SALES_PRICE].sum()
        profit = revenue - (merged_sales[SALES_QTY] * merged_sales[INV_COST]).sum()

        if menu == "Dashboard":
            st.info(f"📅 **Lager pr:** {dates.iloc[0,1]} | **Salg:** {dates.iloc[1,1]} til {dates.iloc[2,1]}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Lager (Stk)", f"{f_inv[INV_QTY].sum():,.0f}")
            m2.metric("Omsætning", f"{revenue:,.0f} kr")
            m3.metric("Profit", f"{profit:,.0f} kr")
            m4.metric("GM %", f"{(profit/revenue*100 if revenue>0 else 0):.1f}%")
            
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🏆 Top Styles")
                st.bar_chart(f_sales.groupby('Style_Navn')[SALES_QTY].sum().sort_values(ascending=False).head(10))
            with c2:
                st.subheader("📊 Brand Omsætning")
                st.bar_chart(f_sales.groupby('Brand')[SALES_PRICE].sum())

        elif menu == "Lager Analyse":
            st.subheader("📈 Dybdegående Lager & Sundhedsanalyse")
            d1, d2 = pd.to_datetime(dates.iloc[1,1]), pd.to_datetime(dates.iloc[2,1])
            days = max((d2 - d1).days + 1, 1)

            cat_inv = f_inv.groupby(INV_CAT).agg(Lager_Stk=(INV_QTY, 'sum'), Lager_Værdi_Kost=(INV_COST, lambda x: (x * f_inv.loc[x.index, INV_QTY]).sum())).reset_index()
            merged_cat = merged_sales.groupby(SALES_CAT).agg(Solgt_Stk=(SALES_QTY, 'sum'), Omsætning=(SALES_PRICE, 'sum'), Total_Kost=(SALES_QTY, lambda x: (x * merged_sales.loc[x.index, INV_COST]).sum())).reset_index()
            merged_cat.rename(columns={SALES_CAT: INV_CAT}, inplace=True)
            
            df_anal = pd.merge(cat_inv, merged_cat, on=INV_CAT, how='left').fillna(0)
            df_anal['STR %'] = (df_anal['Solgt_Stk'] / (df_anal['Lager_Stk'] + df_anal['Solgt_Stk']) * 100).fillna(0)
            df_anal['Dage til udsolgt'] = (df_anal['Lager_Stk'] / (df_anal['Solgt_Stk'] / days)).replace([float('inf')], 0).fillna(0)
            df_anal['Profit'] = df_anal['Omsætning'] - df_anal['Total_Kost']
            df_anal['GM %'] = (df_anal['Profit'] / df_anal['Omsætning'] * 100).fillna(0)
            
            st.dataframe(df_anal.sort_values(by='STR %', ascending=False).style.format({'Lager_Værdi_Kost': '{:,.0f} kr', 'Omsætning': '{:,.0f} kr', 'Profit': '{:,.0f} kr', 'GM %': '{:.1f}%', 'STR %': '{:.1f}%', 'Dage til udsolgt': '{:.0f}'}), use_container_width=True, hide_index=True)

        elif menu == "Størrelses Analyse":
            st.subheader("📏 Dybdegående Størrelses Analyse")
            col1, col2 = st.columns([1, 2])
            with col1:
                st.write("**Salg pr. størrelse**")
                st.bar_chart(f_sales.groupby('Størrelse')[SALES_QTY].sum())
            with col2:
                target_style = st.selectbox("Vælg Style for Størrelses Matrix (Lager):", sorted(f_inv['Style_Navn'].unique()))
                matrix = f_inv[f_inv['Style_Navn'] == target_style].pivot_table(index='Style_Navn', columns='Størrelse', values=INV_QTY, aggfunc='sum').fillna(0)
                st.dataframe(matrix, use_container_width=True)
            
            st.divider()
            st.write("**Broken Sizes (Styles med under 3 størrelser tilbage)**")
            broken = f_inv.groupby('Style_Navn').agg(Antal_Str=('Størrelse', 'count'), Total_Lager=(INV_QTY, 'sum'))
            st.dataframe(broken[broken['Antal_Str'] < 3].sort_values(by='Total_Lager', ascending=False), use_container_width=True)

        elif menu == "Strategisk Analyse":
            st.subheader("🎯 Rabat Analyse & Winner/Loser Matrix")
            cat_stats = merged_sales.groupby(SALES_CAT).apply(lambda x: pd.Series({'Solgt_Stk': x[SALES_QTY].sum(), 'GM %': ((x[SALES_PRICE].sum() - (x[SALES_QTY]*x[INV_COST]).sum()) / x[SALES_PRICE].sum() * 100) if x[SALES_PRICE].sum() > 0 else 0})).reset_index()
            avg_sales, avg_gm = cat_stats['Solgt_Stk'].median(), cat_stats['GM %'].median()
            def classify(row):
                if row['Solgt_Stk'] >= avg_sales and row['GM %'] >= avg_gm: return "⭐ Winner"
                if row['Solgt_Stk'] < avg_sales and row['GM %'] >= avg_gm: return "❓ Spørgsmålstegn"
                if row['Solgt_Stk'] >= avg_sales and row['GM %'] < avg_gm: return "🚜 Arbejdshest"
                return "🦴 Loser"
            cat_stats['Status'] = cat_stats.apply(classify, axis=1)
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("### Winner/Loser Status")
                st.dataframe(cat_stats.sort_values('Status'), use_container_width=True, hide_index=True)
            with c2:
                st.write("### Rabat (Markdown) Analyse")
                markdown_df = merged_sales.groupby(SALES_CAT).apply(lambda x: pd.Series({'Vejl_Værdi': (x[SALES_QTY] * x[INV_RRP]).sum(), 'Faktisk_Omsætning': x[SALES_PRICE].sum()})).reset_index()
                markdown_df['Rabat %'] = (1 - (markdown_df['Faktisk_Omsætning'] / markdown_df['Vejl_Værdi'])) * 100
                st.dataframe(markdown_df.sort_values('Rabat %', ascending=False).style.format({'Rabat %': '{:.1f}%', 'Faktisk_Omsætning': '{:,.0f} kr'}), use_container_width=True, hide_index=True)

        elif menu == "Indkøbs Forslag":
            st.subheader("📡 Reorder Radar (Indkøbs Forslag)")
            reorder_calc = f_inv.groupby('Style_Navn').agg({INV_QTY: 'sum'}).reset_index()
            sales_calc = f_sales.groupby('Style_Navn').agg({SALES_QTY: 'sum'}).reset_index()
            radar_df = pd.merge(reorder_calc, sales_calc, on='Style_Navn', how='inner')
            radar_df['Score'] = radar_df[SALES_QTY] / (radar_df[INV_QTY] + 1)
            
            st.write("Disse styles har et højt salg sammenlignet med det lave lager:")
            st.dataframe(radar_df[radar_df[INV_QTY] < 5].sort_values(by='Score', ascending=False)[['Style_Navn', INV_QTY, SALES_QTY]].rename(columns={INV_QTY: 'På lager', SALES_QTY: 'Solgt'}), use_container_width=True, hide_index=True)

    else:
        st.warning("⚠️ Ingen data fundet. Gå til 'Upload Data' for at starte dashboardet.")