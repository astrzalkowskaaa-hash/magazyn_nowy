import streamlit as st
from supabase import create_client, Client
import pandas as pd
import segno  # Nowa biblioteka do QR
from io import BytesIO

# --- KONFIGURACJA POŁĄCZENIA ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
except Exception as e:
    st.error("Błąd konfiguracji Secrets!")
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

def generate_product_id(category_id):
    response = supabase.table("Produkty").select("id").eq("kategoria_id", category_id).execute()
    count_in_cat = len(response.data)
    return int(f"{category_id}{count_in_cat + 1}")

# --- NOWA FUNKCJA: GENEROWANIE QR ---
def get_qr_image(data):
    qrcode = segno.make_qr(str(data))
    out = BytesIO()
    qrcode.save(out, kind='png', scale=10)
    return out.getvalue()

# --- PRZYGOTOWANIE DANYCH ---
st.set_page_config(page_title="Magazyn Pro + QR", layout="wide")
st.title("📦 System Zarządzania Magazynem z kodami QR")

categories_dict = get_categories()
products_list = get_products_data()
df = pd.DataFrame(products_list) if products_list else pd.DataFrame()

if not df.empty:
    df['kategoria'] = df['Kategorie'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else "Brak")
    df['Wartość'] = df['liczba'] * df['cena']

# --- NAWIGACJA ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard", "✨ Nowy Produkt", "➕ Dostawa", "📂 Kategorie", "🛠️ Admin"])

# --- TAB 1: DASHBOARD + GENERATOR QR ---
with tab1:
    if not df.empty:
        # Metryki na górze
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Wartość", f"{df['Wartość'].sum():,.2f} zł")
        m2.metric("📦 Sztuk", int(df['liczba'].sum()))
        m3.metric("📈 Asortyment", len(df))

        st.divider()
        
        # Sekcja QR KODÓW
        st.subheader("🖼️ Generator etykiet QR")
        qr_col1, qr_col2 = st.columns([1, 2])
        
        with qr_col1:
            prod_to_qr = st.selectbox("Wybierz produkt do etykiety:", df['nazwa'].tolist())
            selected_id = df[df['nazwa'] == prod_to_qr]['id'].values[0]
            
            # Generowanie obrazu QR
            qr_img = get_qr_image(f"PROD_ID: {selected_id}")
            st.image(qr_img, caption=f"Kod QR dla: {prod_to_qr}", width=200)
            
            st.download_button(
                label="📥 Pobierz kod QR do druku",
                data=qr_img,
                file_name=f"QR_{prod_to_qr}.png",
                mime="image/png"
            )
            
        with qr_col2:
            st.info("""
            **Jak używać kodów QR?**
            1. Wybierz produkt z listy po lewej.
            2. Pobierz obrazek i wydrukuj go.
            3. Naklej na regał lub opakowanie. 
            4. Skanując kod telefonem, szybko zidentyfikujesz ID w systemie.
            """)
        
        st.divider()
        st.subheader("📋 Pełna lista")
        st.dataframe(df[['id', 'nazwa', 'kategoria', 'liczba', 'cena', 'Wartość']], use_container_width=True)
    else:
        st.info("Dodaj produkty, aby zobaczyć dashboard.")

# Wstaw to w Tab 1 (Dashboard) pod wykresami
st.divider()
st.subheader("💡 Inteligentne Zalecenia")

col_rec1, col_rec2 = st.columns(2)

with col_rec1:
    # Wyliczamy produkty o najwyższej wartości, które mają niski stan
    critical_value = df[(df['liczba'] < 10) & (df['cena'] > df['cena'].mean())]
    if not critical_value.empty:
        st.error(f"**Priorytet zamówienia:** Masz mało sztuk bardzo drogich produktów: {', '.join(critical_value['nazwa'])}")
    else:
        st.success("Wszystkie kluczowe produkty są zabezpieczone.")

with col_rec2:
    # Analiza struktury
    most_common_cat = df['kategoria'].value_counts().idxmax()
    st.info(f"**Dominacja:** Twoim głównym asortymentem jest obecnie **{most_common_cat}**. Rozważ dywersyfikację, aby zmniejszyć ryzyko.")
# --- TAB 2: NOWY PRODUKT (INTELIGENTNE ID) ---
with tab2:
    st.subheader("Rejestracja nowego produktu")
    if not categories_dict:
        st.error("Baza kategorii jest pusta!")
    else:
        with st.form("form_new_p", clear_on_submit=True):
            n_name = st.text_input("Nazwa produktu:")
            n_qty = st.number_input("Ilość początkowa:", min_value=0, step=1)
            n_price = st.number_input("Cena jednostkowa (zł):", min_value=0.0, step=0.01)
            n_cat = st.selectbox("Wybierz kategorię:", list(categories_dict.keys()))
            
            if st.form_submit_button("Dodaj produkt"):
                cid = categories_dict[n_cat]
                # Sprawdzenie duplikatu
                is_dup = False
                if not df.empty:
                    is_dup = ((df['nazwa'].str.lower() == n_name.lower()) & (df['kategoria_id'] == cid)).any()
                
                if is_dup:
                    st.error(f"Produkt '{n_name}' już istnieje w tej kategorii!")
                elif n_name:
                    pid = generate_product_id(cid)
                    supabase.table("Produkty").insert({
                        "id": pid, "nazwa": n_name, "liczba": n_qty, "cena": n_price, "kategoria_id": cid
                    }).execute()
                    st.success(f"Dodano produkt: {n_name} (ID: {pid})")
                    st.rerun()

# --- TAB 3: DOSTAWA (AKTUALIZACJA) ---
with tab3:
    st.subheader("Przyjęcie towaru")
    if not df.empty:
        prod_sel = st.selectbox("Wybierz produkt z magazynu:", df['nazwa'].tolist())
        row = df[df['nazwa'] == prod_sel].iloc[0]
        with st.form("form_add_q"):
            st.info(f"Obecny stan: {row['liczba']} szt. | Cena: {row['cena']} zł")
            add_val = st.number_input("Ilość do dodania:", min_value=1, step=1)
            if st.form_submit_button("Zatwierdź dostawę"):
                new_q = int(row['liczba'] + add_val)
                supabase.table("Produkty").update({"liczba": new_q}).eq("id", int(row['id'])).execute()
                st.success("Stan zaktualizowany!")
                st.rerun()

# --- TAB 4: KATEGORIE (AUTO ID) ---
with tab4:
    st.subheader("Zarządzanie kategoriami")
    with st.form("form_new_c"):
        c_name = st.text_input("Nowa nazwa kategorii (np. Elektronika):")
        if st.form_submit_button("Utwórz kategorię"):
            if c_name:
                new_cid = generate_category_id()
                supabase.table("Kategorie").insert({"id": new_cid, "nazwa": c_name}).execute()
                st.success(f"Dodano kategorię {c_name} z ID: {new_cid}")
                st.rerun()

# --- TAB 5: ADMIN (USUWANIE) ---
with tab5:
    st.subheader("🧨 Panel Administratora")
    ca, cb = st.columns(2)
    with ca:
        st.write("**Usuń produkt**")
        if not df.empty:
            p_del = st.selectbox("Wybierz produkt do usunięcia:", ["---"] + df['nazwa'].tolist())
            if st.button("Usuń trwale") and p_del != "---":
                supabase.table("Produkty").delete().eq("nazwa", p_del).execute()
                st.rerun()
    with cb:
        st.write("**Usuń kategorię**")
        if categories_dict:
            c_del = st.selectbox("Wybierz kategorię do usunięcia:", ["---"] + list(categories_dict.keys()))
            if st.button("Usuń kategorię") and c_del != "---":
                try:
                    supabase.table("Kategorie").delete().eq("id", categories_dict[c_del]).execute()
                    st.rerun()
                except:
                    st.error("Nie można usunąć kategorii (usuń najpierw produkty z tej kategorii)!")
