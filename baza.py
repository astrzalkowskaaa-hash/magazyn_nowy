import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- KONFIGURACJA POŁĄCZENIA ---
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

# --- FUNKCJE POMOCNICZE ---
def get_categories():
    response = supabase.table("Kategorie").select("id, nazwa").order("id").execute()
    return {item['nazwa']: item['id'] for item in response.data}

def get_products_data():
    # Pobieramy produkty z joinem do kategorii
    response = supabase.table("Produkty").select("id, nazwa, liczba, cena, kategoria_id, Kategorie(nazwa)").execute()
    return response.data

def generate_category_id():
    response = supabase.table("Kategorie").select("id").order("id", desc=True).limit(1).execute()
    if not response.data:
        return 1
    return response.data[0]['id'] + 1

def generate_product_id(category_id):
    # Liczymy produkty w danej kategorii, aby nadać ID typu: [id_kat][kolejny_numer]
    response = supabase.table("Produkty").select("id").eq("kategoria_id", category_id).execute()
    count_in_cat = len(response.data)
    new_id_str = f"{category_id}{count_in_cat + 1}"
    return int(new_id_str)

# --- INTERFEJS UŻYTKOWNIKA ---
st.set_page_config(page_title="Magazyn Inteligentne ID", layout="wide")
st.title("📦 Magazyn z Inteligentnym Systemem ID")

# Odświeżanie danych
categories_dict = get_categories()
products_list = get_products_data()

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Stan i Statystyki", 
    "✨ Nowy Produkt", 
    "➕ Dodaj Ilość", 
    "📂 Nowa Kategoria"
])

# --- TAB 1: STAN ---
with tab1:
    if products_list:
        df = pd.DataFrame(products_list)
        df['kategoria'] = df['Kategorie'].apply(lambda x: x['nazwa'] if x else "Brak")
        df['Wartość'] = df['liczba'] * df['cena']
        
        st.subheader("Lista produktów w magazynie")
        st.dataframe(df[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'Wartość']], use_container_width=True)
        
        c1, c2 = st.columns(2)
        c1.metric("Całkowita wartość", f"{df['Wartość'].sum():,.2f} zł")
        c2.metric("Liczba asortymentu", len(df))
    else:
        st.info("Baza danych jest obecnie pusta.")

# --- TAB 2: NOWY PRODUKT (Z WALIDACJĄ DUPLIKATÓW) ---
with tab2:
    st.subheader("Rejestracja nowego typu produktu")
    if not categories_dict:
        st.warning("Najpierw musisz utworzyć przynajmniej jedną kategorię.")
    else:
        with st.form("new_product_form"):
            new_name = st.text_input("Nazwa produktu (unikalna w kategorii):")
            new_qty = st.number_input("Ilość na start:", min_value=0, step=1)
            new_price = st.number_input("Cena jednostkowa:", min_value=0.0, format="%.2f")
            selected_cat_name = st.selectbox("Przypisz do kategorii:", list(categories_dict.keys()))
            
            if st.form_submit_button("Dodaj do bazy"):
                if new_name:
                    cat_id = categories_dict[selected_cat_name]
                    
                    # Sprawdzenie czy produkt już istnieje w tej kategorii
                    duplicate_check = supabase.table("Produkty")\
                        .select("id")\
                        .eq("nazwa", new_name)\
                        .eq("kategoria_id", cat_id)\
                        .execute()
                    
                    if duplicate_check.data:
                        st.error(f"Produkt '{new_name}' już istnieje w kategorii {selected_cat_name}! "
                                 "Użyj zakładki 'Dodaj Ilość', aby zwiększyć jego stan.")
                    else:
                        p_id = generate_product_id(cat_id)
                        data = {
                            "id": p_id,
                            "nazwa": new_name,
                            "liczba": new_qty,
                            "cena": new_price,
                            "kategoria_id": cat_id
                        }
                        supabase.table("Produkty").insert(data).execute()
                        st.success(f"Pomyślnie dodano: {new_name} (ID: {p_id})")
                        st.rerun()
                else:
                    st.error("Wpisz nazwę produktu.")

# --- TAB 3: DODAJ ILOŚĆ (ISTNIEJĄCY) ---
with tab3:
    st.subheader("Aktualizacja stanu magazynowego")
    if products_list:
        # Tworzymy listę do wyboru z czytelnym opisem
        product_options = {f"{p['nazwa']} (ID: {p['id']})": p for p in products_list}
        choice = st.selectbox("Wybierz produkt:", list(product_options.keys()))
        selected_p = product_options[choice]
        
        with st.form("add_qty_form"):
            st.info(f"Obecny stan: {selected_p['liczba']} szt. | Cena: {selected_p['cena']} zł")
            add_val = st.number_input("Liczba nowych sztuk:", min_value=1, step=1)
            update_price = st.checkbox("Zaktualizować też cenę?")
            new_price_val = st.number_input("Nowa cena:", value=float(selected_p['cena']), min_value=0.0)
            
            if st.form_submit_button("Potwierdź dostawę"):
                new_total = selected_p['liczba'] + add_val
                update_data = {"liczba": new_total}
                if update_price:
                    update_data["cena"] = new_price_val
                
                supabase.table("Produkty").update(update_data).eq("id", selected_p['id']).execute()
                st.success(f"Zaktualizowano produkt. Nowy stan: {new_total}")
                st.rerun()
    else:
        st.warning("Brak produktów w bazie.")

# --- TAB 4: NOWA KATEGORIA ---
with tab4:
    st.subheader("Definiowanie nowej kategorii")
    with st.form("new_cat_form"):
        new_cat_name = st.text_input("Nazwa kategorii (np. Warzywa):")
        if st.form_submit_button("Utwórz kategorię"):
            if new_cat_name:
                # Sprawdzenie czy kategoria już istnieje
                cat_exists = [name for name in categories_dict.keys() if name.lower() == new_cat_name.lower()]
                if cat_exists:
                    st.error("Taka kategoria już istnieje!")
                else:
                    c_id = generate_category_id()
                    supabase.table("Kategorie").insert({"id": c_id, "nazwa": new_cat_name}).execute()
                    st.success(f"Utworzono kategorię '{new_cat_name}' z numerem ID: {c_id}")
                    st.rerun()
