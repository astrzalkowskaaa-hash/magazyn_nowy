import streamlit as st
from supabase import create_client, Client

# --- KONFIGURACJA POŁĄCZENIA ---
# Dane pobierane z "Secrets" w Streamlit Cloud dla bezpieczeństwa
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(URL, KEY)

def get_categories():
    response = supabase.table("Kategorie").select("id, nazwa").execute()
    return {item['nazwa']: item['id'] for item in response.data}

def get_existing_products():
    response = supabase.table("Produkty").select("nazwa").execute()
    return list(set([item['nazwa'] for item in response.data]))

# --- INTERFEJS UŻYTKOWNIKA ---
st.title("📦 System Zarządzania Magazynem")

# 1. Pobieranie danych do podpowiedzi
existing_product_names = get_existing_products()
categories_dict = get_categories()

st.subheader("Dodaj nowy produkt")

with st.form("product_form", clear_on_submit=True):
    # Podpowiedzi: Streamlitowy selectbox lub text_input z listą
    # Używamy selectbox do wyboru istniejącego lub wpisania nowego (poprzez radio)
    mode = st.radio("Wybierz tryb:", ["Nowy produkt", "Uzupełnij istniejący (podpowiedź)"])
    
    if mode == "Uzupełnij istniejący (podpowiedź)":
        nazwa = st.selectbox("Wybierz produkt z bazy:", [""] + existing_product_names)
    else:
        nazwa = st.text_input("Nazwa nowego produktu:")

    liczba = st.number_input("Ilość (liczba):", min_value=0, step=1)
    cena = st.number_input("Cena (numeric):", min_value=0.0, format="%.2f")
    
    kategoria_nazwa = st.selectbox("Kategoria:", list(categories_dict.keys()))
    kategoria_id = categories_dict[kategoria_nazwa]

    submit = st.form_submit_button("Zapisz w magazynie")

# 2. Logika zapisu
if submit:
    if nazwa and liczba >= 0:
        data = {
            "nazwa": nazwa,
            "liczba": liczba,
            "cena": cena,
            "kategoria_id": kategoria_id
        }
        
        try:
            response = supabase.table("Produkty").insert(data).execute()
            st.success(f"Pomyślnie dodano produkt: {nazwa}")
            st.balloons()
        except Exception as e:
            st.error(f"Błąd podczas zapisu: {e}")
    else:
        st.warning("Proszę podać nazwę produktu.")

# --- PODGLĄD MAGAZYNU ---
st.divider()
st.subheader("Aktualny stan magazynowy")
if st.button("Odśwież listę"):
    inventory = supabase.table("Produkty").select("nazwa, liczba, cena, Kategorie(nazwa)").execute()
    if inventory.data:
        st.table(inventory.data)
