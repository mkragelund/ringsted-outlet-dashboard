import streamlit as st
import pandas as pd
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# --- KONFIGURATION (Matcher dine Excel-kolonner) ---
I_NAME, I_CAT, I_ID, I_QTY, I_RRP, I_COST = 'produktnavn', 'kategorinavn', 'stregkode', 'Lager', 'DKKRRP', 'kostpris'
S_NAME, S_CAT, S_ID, S_QTY, S_DISC, S_TOT = 'Produktnavn', 'Kategorinavn', 'Stregkode', 'Salg', 'Rabat (DKK)', 'Total (DKK)'
INVENTORY_FILE, SALES_FILE, DATE_FILE = 'master_inventory.csv', 'master_sales.csv', 'dates.csv'

SIGNAL_CODES = ['500', '550', '600', '601', '602', '604', '611', '612', '613', '614', 
                '621', '622', '623', '624', '631', '632', '633', '634', '641', '642', 
                '643', '644', '650', '651', '671', '693']

# --- HJÆLPEFUNKTIONER ---
def get_brand(season_code):
    return "Signal" if str(season_code).strip() in SIGNAL_CODES else "Co'Couture"

def load_data(file_path):
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.strip() for c in df.columns]
            return df
        except: return pd.DataFrame()
    return pd.DataFrame()

def split_product_details(name):
    name = str(name).strip()
    sep = '-' if '-' in name else '|'
    parts = name.split(sep)
    res = {'Sæson': 'Ukendt', 'Stylenummer': 'Ukendt', 'Style_Navn': name, 'Størrelse': 'N/A'}
    if len(parts) >= 4:
        res['Sæson'], res['Stylenummer'], res['Style_Navn'], res['Størrelse'] = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[-1].strip()
    elif len(parts) > 1:
        res['Style_Navn'], res['Størrelse'] = "-".join(parts[:-1]).strip(), parts[-1].strip()
    return pd.Series(res)

# --- APP SETUP ---
st.set_page_config(page_title="Ringsted Outlet Intel", layout="wide")

inv = load_data(INVENTORY_FILE)
sales = load_data(SALES_FILE)
dates = load_data(DATE_FILE)

st.sidebar.title("🏢 Management")
menu = st.sidebar.selectbox("Vælg Analyse", ["📊 Overblik", "📏 Størrelses Profil", "🎯 Strategisk Analyse", "📥 Upload Data"])

# --- MODUL: UPLOAD DATA ---
if menu == "📥 Upload Data":
    st.header("📦 Datastyring")
    col_a, col_b = st.columns(2)
    with col_a:
        f_inv = st.file_uploader("Upload Lagerfil", type=['xlsx', 'csv'])
    with col_b:
        f_sales = st.file_uploader("Upload Salgsfil", type=['xlsx', 'csv'])
    
    if st.button("🚀 GEM OG OPDATER"):
        if f_inv:
            df_i = pd.read_excel(f_inv) if f_inv.name.endswith('xlsx') else pd.read_csv(f_inv)
            df_i.to_csv(INVENTORY_FILE, index=False)
            st.info("Lager gemt.")
        if f_sales:
            raw = pd.read_excel(f_sales) if f_sales.name.endswith('xlsx') else pd.read_csv(f_sales)
            
            # 1. Find datoer i bunden (række 240 ca.)
            s_start, s_end, extract_date = "Ukendt", "Ukendt", "Ukendt"
            try:
                for i in range(len(raw)):
                    if "periode" in str(raw.iloc[i, 0]).lower():
                        s_start, s_end, extract_date = raw.iloc[i+1, 0], raw.iloc[i+1, 1], raw.iloc[i+1, 3]
                        break
                
                # 2. Rens data: Stop ved 'Total', men behold 'Diverse' (rækken lige før)
                total_idx = raw[raw[S_NAME].astype(str).str.contains("Total", case=False, na=False)].index
                clean_sales = raw.iloc[:total_idx[0]] if not total_idx.empty else raw
                
                # Fjern kun helt tomme rækker, så 'Diverse' bliver bevaret
                clean_sales = clean_sales.dropna(subset=[S_NAME])
                clean_sales.to_csv(SALES_FILE, index=False)
                
                # Gem dato-info
                pd.DataFrame({'type':['inv','start','end','ext'], 'date':[str(datetime.now()), s_start, s_end, extract_date]}).to_csv(DATE_FILE, index=False)
                st.success(f"Salg indlæst! Periode: {s_start} - {s_end}")
                st.balloons()
            except Exception as e: st.error(f"Fejl ved behandling: {e}")

# --- DASHBOARD LOGIK ---
elif not sales.empty and not inv.empty:
    # Konvertering til tal (Sikrer Diverse tælles med)
    sales[S_QTY] = pd.to_numeric(sales[S_QTY], errors='coerce').fillna(0)
    sales[S_TOT] = pd.to_numeric(sales[S_TOT], errors='coerce').fillna(0)
    sales[S_DISC] = pd.to_numeric(sales[S_DISC], errors='coerce').fillna(0)
    inv[I_QTY] = pd.to_numeric(inv[I_QTY], errors='coerce').fillna(0)

    for df, col in [(sales, S_NAME), (inv, I_NAME)]:
        details = df[col].apply(split_product_details)
        for c in details.columns: df[c] = details[c]
    
    inv['Brand'] = inv['Sæson'].apply(get_brand)
    sales['Brand'] = sales['Sæson'].apply(get_brand)
    
    # Nedskrivning af lager
    sales_sum = sales.groupby(S_ID)[S_QTY].sum().reset_index()
    inv_current = pd.merge(inv, sales_sum, left_on=I_ID, right_on=S_ID, how='left').fillna(0)
    inv_current[I_QTY] = inv_current[I_QTY] - inv_current[S_QTY]

    brands = st.sidebar.multiselect("Vælg Brand", ["Signal", "Co'Couture"], default=["Signal", "Co'Couture"])
    f_inv = inv_current[inv_current['Brand'].isin(brands)]
    f_sales = sales[sales['Brand'].isin(brands)]

    if menu == "📊 Overblik":
        st.header("Hovednøgletal")
        c1, c2, c3 = st.columns(3)
        c1.metric("Omsætning", f"{f_sales[S_TOT].sum():,.0f} kr")
        c2.metric("Solgte enheder", f"{f_sales[S_QTY].sum():,.0f}")
        c3.metric("Lagerbeholdning", f"{f_inv[I_QTY].sum():,.0f}")
        
        col_l, col_r = st.columns([2, 1])
        with col_l:
            st.plotly_chart(px.bar(f_sales.groupby(S_CAT)[S_TOT].sum().reset_index(), x=S_CAT, y=S_TOT, color=S_CAT, title="Omsætning pr. Kategori"), use_container_width=True)
        with col_r:
            st.plotly_chart(px.pie(f_sales, values=S_TOT, names='Brand', hole=0.4, title="Brand Fordeling"), use_container_width=True)

    elif menu == "📏 Størrelses Profil":
        st.header("📏 Størrelses- & Tendensanalyse")
        prod_cats = sorted(f_inv[I_CAT].unique())
        sel_prod_cat = st.multiselect("Filtrer på Produktgruppe (Slicer):", prod_cats)
        
        d_inv, d_sales = f_inv.copy(), f_sales.copy()
        if sel_prod_cat:
            d_inv = d_inv[d_inv[I_CAT].isin(sel_prod_cat)]
            d_sales = d_sales[d_sales[S_CAT].isin(sel_prod_cat)]

        size_order = ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '34', '36', '38', '40', '42', '44', '46']
        s_stats = d_sales.groupby('Størrelse')[S_QTY].sum().reset_index().rename(columns={S_QTY: 'Solgt'})
        i_stats = d_inv.groupby('Størrelse')[I_QTY].sum().reset_index().rename(columns={I_QTY: 'På Lager'})
        
        comp = pd.merge(i_stats, s_stats, on='Størrelse', how='outer').fillna(0)
        comp['sort'] = comp['Størrelse'].apply(lambda x: size_order.index(x) if x in size_order else 99)
        comp = comp.sort_values('sort')

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(x=comp['Størrelse'], y=comp['På Lager'], name='Lager', marker_color='#1f77b4'))
        fig_comp.add_trace(go.Bar(x=comp['Størrelse'], y=comp['Solgt'], name='Salg', marker_color='#ff7f0e'))
        fig_comp.update_layout(barmode='group', title="Sammenligning: Lager vs. Salg", template="plotly_white")
        st.plotly_chart(fig_comp, use_container_width=True)

    elif menu == "🎯 Strategisk Analyse":
        st.header("Strategisk Overblik")
        col1, col2 = st.columns(2)
        with col1:
            top_cat = f_sales.groupby(S_CAT)[S_TOT].sum().sort_values(ascending=False).head(10).reset_index()
            st.plotly_chart(px.bar(top_cat, x=S_TOT, y=S_CAT, orientation='h', color=S_TOT, color_continuous_scale="Greens", title="Top 10 Kategorier (Indtjening)"), use_container_width=True)
        with col2:
            md = f_sales.groupby(S_CAT).agg({S_TOT: 'sum', S_DISC: 'sum'}).reset_index()
            md['Rabat %'] = (md[S_DISC] / (md[S_TOT] + md[S_DISC]) * 100).fillna(0)
            st.plotly_chart(px.bar(md.sort_values('Rabat %', ascending=False).head(10), x='Rabat %', y=S_CAT, orientation='h', color='Rabat %', color_continuous_scale="Reds", title="Rabat-tryk (Markdown %)"), use_container_width=True)

else:
    st.warning("⚠️ Ingen data fundet. Gå til 'Upload Data' og upload begge filer igen.")
