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

        # 1. KPI CARDS - Wizualne podsumowanie
        st.markdown("### 📈 Kluczowe wskaźniki")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 Wartość całkowita", f"{df['Wartość'].sum():,.2f} zł")
        m2.metric("📦 Łączna liczba sztuk", int(df['liczba'].sum()))
        m3.metric("🏷️ Liczba kategorii", len(categories_dict))
        # Najdroższy produkt
        top_prod = df.loc[df['cena'].idxmax()]
        m4.metric("💎 Najdroższy produkt", f"{top_prod['cena']} zł", help=f"Produkt: {top_prod['nazwa']}")

        st.divider()

        # 2. INTERAKTYWNA TABELA I WYSZUKIWARKA
        st.markdown("### 🔍 Przegląd i szybka edycja")
        search_query = st.text_input("Wyszukaj produkt po nazwie...", "").lower()
        
        filtered_df = df[df['nazwa'].str.lower().contains(search_query)]
        
        # st.data_editor pozwala użytkownikowi edytować dane "w locie"
        edited_df = st.data_editor(
            filtered_df[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'Wartość']],
            use_container_width=True,
            column_config={
                "liczba": st.column_config.NumberColumn("Stan", format="%d 📦"),
                "cena": st.column_config.NumberColumn("Cena", format="%.2f zł"),
                "Wartość": st.column_config.ProgressColumn("Udział w wartości", min_value=0, max_value=float(df['Wartość'].max()), format="%.2f zł"),
            },
            disabled=["id", "kategoria", "Wartość"], # blokujemy edycję id i wyliczeń
            hide_index=True
        )

        # Przycisk zapisu zmian z edytora (opcjonalne ulepszenie)
        if st.button("💾 Zapisz zmiany z tabeli"):
            st.info("Tutaj możesz dodać logikę aktualizacji masowej (Bulk Update) w Supabase.")

        st.divider()

        # 3. ZAAWANSOWANA ANALIZA WYKRESÓW
        st.markdown("### 📊 Analityka Wizualna")
        
        col_c1, col_c2 = st.columns([1, 1])
        
        with col_c1:
            st.write("**Podział wartościowy magazynu (Kołowy)**")
            # Prosty sposób na wykres kołowy w Streamlit
            st.vega_lite_chart(df, {
                'mark': {'type': 'arc', 'innerRadius': 50},
                'encoding': {
                    'theta': {'field': 'Wartość', 'type': 'quantitative'},
                    'color': {'field': 'kategoria', 'type': 'nominal'},
                },
            }, use_container_width=True)

        with col_c2:
            st.write("**Top 5 najliczniejszych produktów**")
            top5_qty = df.nlargest(5, 'liczba')
            st.bar_chart(data=top5_qty, x="nazwa", y="liczba", color="#FF4B4B")

        # Eksport na dole dla czystości interfejsu
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📂 Eksportuj pełną bazę do Excel (CSV)", csv, 'magazyn_full.csv', 'text/csv')
    else:
        st.info("Magazyn jest pusty. Dodaj pierwszy produkt w zakładce obok!")
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
