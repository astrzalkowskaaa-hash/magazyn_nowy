import streamlit as st
from supabase import create_client, Client
import pandas as pd
from io import BytesIO

# --- KONFIGURACJA POŁĄCZENIA ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

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
    if not response.data: return 1
    return response.data[0]['id'] + 1

def generate_product_id(category_id):
    response = supabase.table("Produkty").select("id").eq("kategoria_id", category_id).execute()
    count_in_cat = len(response.data)
    return int(f"{category_id}{count_in_cat + 1}")

# --- INTERFEJS ---
st.set_page_config(page_title="Magazyn Pro + Raporty", layout="wide")
st.title("📦 System Zarządzania Magazynem 3.0")

categories_dict = get_categories()
products_list = get_products_data()
df = pd.DataFrame(products_list) if products_list else pd.DataFrame()

# 1. ALERTY O NISKIM STANIE
LOW_STOCK_THRESHOLD = 5
if not df.empty:
    low_stock_items = df[df['liczba'] <= LOW_STOCK_THRESHOLD]
    if not low_stock_items.empty:
        names = ", ".join([f"{row['nazwa']} ({row['liczba']} szt.)" for _, row in low_stock_items.iterrows()])
        st.warning(f"⚠️ **PRODUKTY NA WYCZERPANIU:** {names}")

# PODZIAŁ NA ZAKŁADKI
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Stan i Raporty", 
    "✨ Nowy Produkt", 
    "➕ Dodaj Ilość", 
    "📂 Kategorie",
    "🛠️ Panel Administratora"
])

# --- TAB 1: STAN, WYKRESY I EKSPORT ---
with tab1:
    if not df.empty:
        df['kategoria'] = df['Kategorie'].apply(lambda x: x['nazwa'] if x else "Brak")
        df['Wartość'] = df['liczba'] * df['cena']
        
        col_m1, col_m2, col_exp = st.columns([2, 2, 1])
        col_m1.metric("Wartość magazynu", f"{df['Wartość'].sum():,.2f} zł")
        col_m2.metric("Liczba produktów", len(df))
        
        # EKSPORT DO CSV
        csv = df[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'Wartość']].to_csv(index=False).encode('utf-8-sig')
        col_exp.download_button(
            label="📥 Pobierz Raport CSV",
            data=csv,
            file_name='raport_magazynowy.csv',
            mime='text/csv',
        )

        st.subheader("Podgląd magazynu")
        st.dataframe(df[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'Wartość']], use_container_width=True)

        st.divider()
        st.subheader("Wizualizacja zapasów")
        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            st.write("**Suma sztuk w kategoriach**")
            st.bar_chart(df.groupby('kategoria')['liczba'].sum())
        with c_chart2:
            st.write("**Wartość finansowa kategorii (zł)**")
            st.bar_chart(df.groupby('kategoria')['Wartość'].sum())
    else:
        st.info("Magazyn jest pusty.")

# --- TAB 2: NOWY PRODUKT ---
with tab2:
    st.subheader("Dodaj nowy asortyment")
    if not categories_dict:
        st.error("Brak kategorii w systemie!")
    else:
        with st.form("new_prod"):
            n_name = st.text_input("Nazwa produktu:")
            n_qty = st.number_input("Ilość:", min_value=0, step=1)
            n_price = st.number_input("Cena:", min_value=0.0, step=0.01)
            n_cat = st.selectbox("Kategoria:", list(categories_dict.keys()))
            if st.form_submit_button("Zarejestruj produkt"):
                cat_id = categories_dict[n_cat]
                # Walidacja nazwy wewnątrz kategorii
                is_duplicate = False
                if not df.empty:
                    is_duplicate = ((df['nazwa'].str.lower() == n_name.lower()) & (df['kategoria_id'] == cat_id)).any()
                
                if is_duplicate:
                    st.error("Ten produkt już istnieje w tej kategorii!")
                elif n_name:
                    p_id = generate_product_id(cat_id)
                    supabase.table("Produkty").insert({
                        "id": p_id, "nazwa": n_name, "liczba": n_qty, "cena": n_price, "kategoria_id": cat_id
                    }).execute()
                    st.success(f"Dodano produkt pod ID: {p_id}")
                    st.rerun()

# --- TAB 3: DODAJ ILOŚĆ ---
with tab3:
    st.subheader("Przyjęcie towaru (istniejący produkt)")
    if not df.empty:
        selected_name = st.selectbox("Wybierz produkt z listy:", df['nazwa'].tolist())
        row = df[df['nazwa'] == selected_name].iloc[0]
        with st.form("add_q_form"):
            st.write(f"Aktualnie: {row['liczba']} szt. | Cena: {row['cena']} zł")
            add_val = st.number_input("Ile sztuk przywieziono?", min_value=1, step=1)
            if st.form_submit_button("Dodaj do stanu"):
                new_q = int(row['liczba'] + add_val)
                supabase.table("Produkty").update({"liczba": new_q}).eq("id", int(row['id'])).execute()
                st.success("Zaktualizowano ilość.")
                st.rerun()

# --- TAB 4: KATEGORIE ---
with tab4:
    st.subheader("Zarządzanie kategoriami")
    with st.form("new_cat"):
        c_name = st.text_input("Nazwa nowej kategorii:")
        if st.form_submit_button("Dodaj kategorię"):
            if c_name:
                c_id = generate_category_id()
                supabase.table("Kategorie").insert({"id": c_id, "nazwa": c_name}).execute()
                st.success(f"Utworzono kategorię {c_name} (ID: {c_id})")
                st.rerun()

# --- TAB 5: PANEL ADMINISTRATORA ---
with tab5:
    st.subheader("Usuwanie danych (Akcje nieodwracalne)")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("🗑️ **Produkty**")
        if not df.empty:
            p_to_del = st.selectbox("Wybierz produkt do usunięcia:", ["---"] + df['nazwa'].tolist())
            if st.button("Usuń wybrany produkt") and p_to_del != "---":
                supabase.table("Produkty").delete().eq("nazwa", p_to_del).execute()
                st.rerun()
            
            if st.button("🧨 USUŃ CAŁY MAGAZYN"):
                if st.checkbox("Potwierdzam usunięcie WSZYSTKICH produktów"):
                    supabase.table("Produkty").delete().neq("id", 0).execute()
                    st.rerun()

    with col2:
        st.write("📂 **Kategorie**")
        if categories_dict:
            c_to_del = st.selectbox("Usuń kategorię:", ["---"] + list(categories_dict.keys()))
            if st.button("Usuń kategorię") and c_to_del != "---":
                try:
                    supabase.table("Kategorie").delete().eq("id", categories_dict[c_to_del]).execute()
                    st.rerun()
                except:
                    st.error("Nie można usunąć kategorii, która ma przypisane produkty!")
