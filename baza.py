import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- KONFIGURACJA POŁĄCZENIA ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# --- FUNKCJE POMOCNICZE ---
def get_categories():
    response = supabase.table("Kategorie").select("id, nazwa").execute()
    return {item['nazwa']: item['id'] for item in response.data}

def get_products_data():
    # Pobieramy produkty wraz z nazwą kategorii (Join)
    response = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, Kategorie(nazwa)").execute()
    return response.data

# --- INTERFEJS UŻYTKOWNIKA ---
st.set_page_config(page_title="Magazyn Supabase", layout="wide")
st.title("📦 System Zarządzania Magazynem")

# Pobieranie aktualnych danych
categories_dict = get_categories()
products_list = get_products_data()

# Podział na zakładki
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Stan i Statystyki", 
    "✨ Nowy Produkt", 
    "➕ Dodaj do istniejącego", 
    "📂 Nowa Kategoria"
])

# --- TAB 1: STAN MAGAZYNOWY I STATYSTYKI ---
with tab1:
    st.subheader("Aktualny stan magazynowy")
    if products_list:
        df = pd.DataFrame(products_list)
        # Wyciąganie nazwy kategorii z zagnieżdżonego słownika
        df['kategoria'] = df['Kategorie'].apply(lambda x: x['nazwa'] if x else "Brak")
        df['Wartość'] = df['liczba'] * df['cena']
        
        # Wyświetlanie tabeli (bez kolumn technicznych)
        st.dataframe(df[['nazwa', 'kategoria', 'liczba', 'cena', 'Wartość']], use_container_width=True)
        
        # Statystyki
        col1, col2 = st.columns(2)
        total_value = df['Wartość'].sum()
        total_items = df['liczba'].sum()
        
        col1.metric("Całkowita wartość magazynu", f"{total_value:,.2f} zł")
        col2.metric("Suma wszystkich sztuk", total_items)
    else:
        st.info("Magazyn jest pusty.")

# --- TAB 2: NOWY PRODUKT ---
with tab2:
    st.subheader("Wprowadź zupełnie nowy produkt")
    with st.form("new_product_form"):
        new_name = st.text_input("Nazwa produktu:")
        new_qty = st.number_input("Ilość początkowa:", min_value=0, step=1)
        new_price = st.number_input("Cena jednostkowa:", min_value=0.0, format="%.2f")
        new_cat = st.selectbox("Wybierz kategorię:", list(categories_dict.keys()), key="new_p_cat")
        
        if st.form_submit_button("Dodaj produkt do bazy"):
            if new_name:
                data = {
                    "nazwa": new_name,
                    "liczba": new_qty,
                    "cena": new_price,
                    "kategoria_id": categories_dict[new_cat]
                }
                supabase.table("Produkty").insert(data).execute()
                st.success(f"Dodano produkt {new_name}")
                st.rerun()
            else:
                st.error("Nazwa nie może być pusta!")

# --- TAB 3: DODAJ DO ISTNIEJĄCEGO (NADPISYWANIE/AKTUALIZACJA) ---
with tab3:
    st.subheader("Zwiększ stan istniejącego produktu")
    if products_list:
        product_names = [p['nazwa'] for p in products_list]
        selected_p_name = st.selectbox("Wybierz produkt z bazy:", product_names)
        
        # Pobranie danych wybranego produktu
        selected_p_data = next(item for item in products_list if item["nazwa"] == selected_p_name)
        
        with st.form("update_product_form"):
            st.info(f"Obecnie w magazynie: {selected_p_data['liczba']} szt.")
            add_qty = st.number_input("Ile sztuk dodać?", min_value=1, step=1)
            new_p_price = st.number_input("Zaktualizuj cenę (opcjonalnie):", value=float(selected_p_data['cena']), min_value=0.0)
            
            if st.form_submit_button("Aktualizuj magazyn"):
                new_total = selected_p_data['liczba'] + add_qty
                supabase.table("Produkty").update({
                    "liczba": new_total,
                    "cena": new_p_price
                }).eq("id", selected_p_data['id']).execute()
                
                st.success(f"Zaktualizowano {selected_p_name}. Nowy stan: {new_total}")
                st.rerun()
    else:
        st.warning("Brak produktów w bazie do zaktualizowania.")

# --- TAB 4: NOWA KATEGORIA ---
with tab4:
    st.subheader("Dodaj nową kategorię")
    with st.form("category_form"):
        cat_name = st.text_input("Nazwa kategorii (np. Elektronika, Napoje):")
        cat_desc = st.text_area("Opis kategorii:")
        
        if st.form_submit_button("Zapisz kategorię"):
            if cat_name:
                try:
                    supabase.table("Kategorie").insert({"nazwa": cat_name, "opis": cat_desc}).execute()
                    st.success(f"Dodano kategorię: {cat_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd: {e}")
            else:
                st.error("Podaj nazwę kategorii!")
