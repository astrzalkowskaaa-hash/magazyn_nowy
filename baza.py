Błąd AttributeError najczęściej wynika z faktu, że próbujemy użyć funkcji na obiekcie, który jej nie posiada. W Twoim kodzie najprawdopodobniej problem leży w linii: filtered_df = df[df['nazwa'].str.lower().contains(search_query)]

Metoda pandas to .str.contains(), a nie .contains(). Dodatkowo, jeśli baza jest pusta, zmienna df może nie mieć odpowiednich kolumn, co również generuje błędy.

Oto poprawiony, pełny kod aplikacji z poprawioną wyszukiwarką, nowoczesnym wyglądem i wszystkimi funkcjami, o które prosiłeś.

Python

import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- KONFIGURACJA POŁĄCZENIA ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
except Exception as e:
    st.error("Błąd konfiguracji Secrets! Sprawdź SUPABASE_URL i SUPABASE_KEY.")
    st.stop()

# --- FUNKCJE POMOCNICZE ---
def get_categories():
    try:
        response = supabase.table("Kategorie").select("id, nazwa").order("id").execute()
        return {item['nazwa']: item['id'] for item in response.data}
    except: return {}

def get_products_data():
    try:
        # Pobieramy dane z JOINem do tabeli Kategorie
        response = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, Kategorie(nazwa)").execute()
        return response.data
    except Exception as e:
        st.error(f"Błąd pobierania danych: {e}")
        return []

def generate_category_id():
    response = supabase.table("Kategorie").select("id").order("id", desc=True).limit(1).execute()
    if not response.data: return 1
    return response.data[0]['id'] + 1

def generate_product_id(category_id):
    response = supabase.table("Produkty").select("id").eq("kategoria_id", category_id).execute()
    count_in_cat = len(response.data)
    return int(f"{category_id}{count_in_cat + 1}")

# --- PRZYGOTOWANIE DANYCH ---
st.set_page_config(page_title="Magazyn Pro 3.0", layout="wide")
st.title("📦 System Zarządzania Magazynem")

categories_dict = get_categories()
products_list = get_products_data()

# Tworzymy DataFrame i czyścimy dane
if products_list:
    df = pd.DataFrame(products_list)
    # Wyciągamy nazwę kategorii z zagnieżdżonego obiektu Supabase
    df['kategoria'] = df['Kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else "Brak")
    df['Wartość'] = df['liczba'] * df['cena']
else:
    df = pd.DataFrame(columns=['id', 'nazwa', 'liczba', 'cena', 'kategoria_id', 'kategoria', 'Wartość'])

# --- 1. ALERTY O NISKIM STANIE ---
LOW_STOCK_THRESHOLD = 5
if not df.empty:
    low_stock = df[df['liczba'] <= LOW_STOCK_THRESHOLD]
    if not low_stock.empty:
        alert_text = ", ".join([f"{row['nazwa']} ({row['liczba']} szt.)" for _, row in low_stock.iterrows()])
        st.warning(f"⚠️ **PRODUKTY NA WYCZERPANIU:** {alert_text}")

# --- NAWIGACJA ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard", "✨ Nowy Produkt", "➕ Dostawa", "📂 Kategorie", "🛠️ Admin"
])

# --- TAB 1: DASHBOARD (EFEKT WOW) ---
with tab1:
    if not df.empty:
        # KPI Cards
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Wartość Magazynu", f"{df['Wartość'].sum():,.2f} zł")
        c2.metric("📦 Łączna ilość", int(df['liczba'].sum()))
        c3.metric("🏷️ Kategorie", len(categories_dict))
        c4.metric("📈 Asortyment", len(df))

        st.divider()

        # Wyszukiwarka i Tabela
        col_search, col_export = st.columns([3, 1])
        with col_search:
            search = st.text_input("🔍 Szukaj produktu...", "")
        with col_export:
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 Pobierz CSV", csv, "magazyn.csv", "text/csv")

        # Filtrowanie
        filtered_df = df[df['nazwa'].str.contains(search, case=False, na=False)]
        
        st.dataframe(
            filtered_df[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'Wartość']],
            use_container_width=True,
            column_config={
                "Wartość": st.column_config.ProgressColumn("Udział finansowy", format="%.2f zł", min_value=0, max_value=float(df['Wartość'].max())),
                "liczba": st.column_config.NumberColumn("Sztuk", format="%d 📦")
            },
            hide_index=True
        )

        st.divider()
        
        # Wykresy
        st.subheader("📊 Analiza Graficzna")
        g1, g2 = st.columns(2)
        with g1:
            st.write("**Ilość produktów w kategoriach**")
            # Wykres skumulowany: Ile sztuk każdego produktu w danej kategorii
            st.bar_chart(data=df, x="kategoria", y="liczba", color="nazwa")
        with g2:
            st.write("**Wartość produktów w kategoriach (zł)**")
            st.bar_chart(data=df, x="kategoria", y="Wartość", color="nazwa")
    else:
        st.info("Magazyn jest pusty.")

# --- TAB 2: NOWY PRODUKT ---
with tab2:
    st.subheader("Dodaj nowy typ towaru")
    if not categories_dict:
        st.error("Brak kategorii! Dodaj je w zakładce 'Kategorie'.")
    else:
        with st.form("new_p"):
            name = st.text_input("Nazwa produktu:")
            qty = st.number_input("Ilość:", min_value=0, step=1)
            price = st.number_input("Cena:", min_value=0.0, step=0.01)
            cat_name = st.selectbox("Kategoria:", list(categories_dict.keys()))
            if st.form_submit_button("Zapisz w bazie"):
                cid = categories_dict[cat_name]
                if not df.empty and ((df['nazwa'].str.lower() == name.lower()) & (df['kategoria_id'] == cid)).any():
                    st.error("Ten produkt już istnieje w tej kategorii!")
                elif name:
                    pid = generate_product_id(cid)
                    supabase.table("Produkty").insert({"id":pid, "nazwa":name, "liczba":qty, "cena":price, "kategoria_id":cid}).execute()
                    st.success(f"Dodano! ID: {pid}")
                    st.rerun()

# --- TAB 3: DOSTAWA ---
with tab3:
    st.subheader("Zwiększ stan magazynowy")
    if not df.empty:
        p_choice = st.selectbox("Wybierz produkt do uzupełnienia:", df['nazwa'].tolist())
        selected_row = df[df['nazwa'] == p_choice].iloc[0]
        with st.form("add_q"):
            add_val = st.number_input("Ile sztuk przywieziono?", min_value=1)
            if st.form_submit_button("Aktualizuj stan"):
                new_total = int(selected_row['liczba'] + add_val)
                supabase.table("Produkty").update({"liczba": new_total}).eq("id", int(selected_row['id'])).execute()
                st.success("Zaktualizowano!")
                st.rerun()

# --- TAB 4: KATEGORIE ---
with tab4:
    st.subheader("Nowa kategoria")
    with st.form("new_c"):
        c_name = st.text_input("Nazwa kategorii:")
        if st.form_submit_button("Dodaj"):
            if c_name:
                new_cid = generate_category_id()
                supabase.table("Kategorie").insert({"id": new_cid, "nazwa": c_name}).execute()
                st.rerun()

# --- TAB 5: ADMIN ---
with tab5:
    st.subheader("⚠️ Zarządzanie Krytyczne")
    col_a, col_b = st.columns(2)
    with col_a:
        if not df.empty:
            to_del = st.selectbox("Usuń produkt:", ["---"] + df['nazwa'].tolist())
            if st.button("Usuń produkt") and to_del != "---":
                supabase.table("Produkty").delete().eq("nazwa", to_del).execute()
                st.rerun()
    with col_b:
        if categories_dict:
            c_del = st.selectbox("Usuń kategorię:", ["---"] + list(categories_dict.keys()))
            if st.button("Usuń kategorię") and c_del != "---":
                try:
                    supabase.table("Kategorie").delete().eq("id", categories_dict[c_del]).execute()
                    st.rerun()
                except:
                    st.error("Kategoria ma przypisane produkty!")
