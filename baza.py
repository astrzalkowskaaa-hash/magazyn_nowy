import streamlit as st
from supabase import create_client, Client
import pandas as pd
import segno
from io import BytesIO

# --- KONFIGURACJA POŁĄCZENIA ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
except Exception as e:
    st.error("Błąd Secrets! Sprawdź SUPABASE_URL i SUPABASE_KEY.")
    st.stop()

# --- FUNKCJE POMOCNICZE ---
def get_categories():
    try:
        response = supabase.table("Kategorie").select("id, nazwa").order("id").execute()
        return {item['nazwa']: item['id'] for item in response.data}
    except: return {}

def get_products_data():
    try:
        response = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, Kategorie(nazwa)").execute()
        return response.data
    except: return []

def generate_category_id():
    response = supabase.table("Kategorie").select("id").order("id", desc=True).limit(1).execute()
    return response.data[0]['id'] + 1 if response.data else 1

def generate_product_id(category_id):
    response = supabase.table("Produkty").select("id").eq("kategoria_id", category_id).execute()
    return int(f"{category_id}{len(response.data) + 1}")

def get_qr_image(data):
    qrcode = segno.make_qr(str(data))
    out = BytesIO()
    qrcode.save(out, kind='png', scale=10)
    return out.getvalue()

# --- PRZYGOTOWANIE INTERFEJSU ---
st.set_page_config(page_title="Magazyn Pro QR", layout="wide")
st.title("📦 System Zarządzania Magazynem 4.0")

categories_dict = get_categories()
products_list = get_products_data()
df = pd.DataFrame(products_list) if products_list else pd.DataFrame()

if not df.empty:
    df['kategoria'] = df['Kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else "Brak")
    df['Wartość'] = df['liczba'] * df['cena']

# --- ALERTY ---
if not df.empty:
    low_stock = df[df['liczba'] <= 5]
    if not low_stock.empty:
        st.warning(f"⚠️ **NISKI STAN:** {', '.join([f'{r.nazwa} ({r.liczba})' for _, r in low_stock.iterrows()])}")

# --- TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard & Wykresy", "✨ Nowy Produkt", "➕ Dostawa", "📂 Kategorie", "🛠️ Admin"])

# --- TAB 1: DASHBOARD & WYKRESY ---
with tab1:
    if not df.empty:
        # KPI Cards
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Wartość", f"{df['Wartość'].sum():,.2f} zł")
        c2.metric("📦 Sztuk", int(df['liczba'].sum()))
        c3.metric("🏷️ Kategorie", len(categories_dict))
        top_p = df.loc[df['Wartość'].idxmax()]
        c4.metric("💎 Top Produkt", f"{top_p['Wartość']:,.2f} zł", help=top_p['nazwa'])

        st.divider()

        # Eksport i Szukanie
        col_s, col_e = st.columns([3, 1])
        with col_s: search = st.text_input("🔍 Szukaj produktu...", "")
        with col_e: 
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Pobierz CSV", csv, "magazyn.csv", "text/csv")

        filtered_df = df[df['nazwa'].str.contains(search, case=False, na=False)]
        st.dataframe(filtered_df[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'Wartość']], use_container_width=True, hide_index=True)

        st.divider()

        # WYKRESY
        st.subheader("📊 Analityka Magazynowa")
        g1, g2 = st.columns(2)
        with g1:
            st.write("**Ilość sztuk w kategoriach**")
            st.bar_chart(data=df, x="kategoria", y="liczba", color="nazwa")
        with g2:
            st.write("**Wartość finansowa (zł) w kategoriach**")
            st.bar_chart(data=df, x="kategoria", y="Wartość", color="nazwa")

        st.divider()

        # SEKCOJA QR
        st.subheader("🖼️ Generator Etykiet QR")
        q1, q2 = st.columns([1, 2])
        with q1:
            prod_qr = st.selectbox("Wybierz produkt do QR:", df['nazwa'].tolist())
            sid = df[df['nazwa'] == prod_qr]['id'].values[0]
            img = get_qr_image(f"ID:{sid} | {prod_qr}")
            st.image(img, width=200)
            st.download_button("📥 Pobierz QR", img, f"QR_{prod_qr}.png", "image/png")
        with q2:
            st.info("Kody QR zawierają ID produktu. Możesz je drukować jako etykiety na regały.")
    else:
        st.info("Baza jest pusta.")

# --- TAB 2: NOWY PRODUKT ---
with tab2:
    if not categories_dict: st.error("Dodaj najpierw kategorię!")
    else:
        with st.form("np"):
            n = st.text_input("Nazwa:")
            q = st.number_input("Ilość:", min_value=0, step=1)
            p = st.number_input("Cena:", min_value=0.0, step=0.01)
            c = st.selectbox("Kategoria:", list(categories_dict.keys()))
            if st.form_submit_button("Dodaj"):
                cid = categories_dict[c]
                if not df.empty and ((df['nazwa'].str.lower() == n.lower()) & (df['kategoria_id'] == cid)).any():
                    st.error("Produkt już istnieje!")
                elif n:
                    pid = generate_product_id(cid)
                    supabase.table("Produkty").insert({"id":pid, "nazwa":n, "liczba":q, "cena":p, "kategoria_id":cid}).execute()
                    st.success(f"Dodano ID: {pid}"); st.rerun()

# --- TAB 3: DOSTAWA ---
with tab3:
    if not df.empty:
        sel = st.selectbox("Produkt:", df['nazwa'].tolist())
        r = df[df['nazwa'] == sel].iloc[0]
        with st.form("dq"):
            add = st.number_input("Dodaj sztuk:", min_value=1)
            if st.form_submit_button("Aktualizuj"):
                supabase.table("Produkty").update({"liczba": int(r['liczba'] + add)}).eq("id", int(r['id'])).execute()
                st.rerun()

# --- TAB 4: KATEGORIE ---
with tab4:
    with st.form("nc"):
        cn = st.text_input("Nazwa kategorii:")
        if st.form_submit_button("Dodaj kategorię"):
            if cn:
                supabase.table("Kategorie").insert({"id": generate_category_id(), "nazwa": cn}).execute()
                st.rerun()

# --- TAB 5: ADMIN ---
with tab5:
    c_a, c_b = st.columns(2)
    with c_a:
        if not df.empty:
            d_p = st.selectbox("Usuń produkt:", ["---"] + df['nazwa'].tolist())
            if st.button("Usuń produkt") and d_p != "---":
                supabase.table("Produkty").delete().eq("nazwa", d_p).execute(); st.rerun()
    with c_b:
        if categories_dict:
            d_c = st.selectbox("Usuń kategorię:", ["---"] + list(categories_dict.keys()))
            if st.button("Usuń kategorię") and d_c != "---":
                try: supabase.table("Kategorie").delete().eq("id", categories_dict[d_c]).execute(); st.rerun()
                except: st.error("Kategoria ma produkty!")
