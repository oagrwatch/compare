import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
from datetime import datetime, timedelta
import io

# Ρυθμίσεις Streamlit
st.title("Σύγκριση Ειδησεογραφικών Άρθρων")
st.write("Ανεβάστε το αρχείο Excel από το ellada24.gr και τουλάχιστον ένα από τα amna.gr, protothema.gr ή iefimerida.gr για να συγκρίνετε τους τίτλους.")

# Upload αρχείων
st.subheader("Μεταφόρτωση Αρχείων")
ellada_file = st.file_uploader("ellada24_news_articles.xlsx (υποχρεωτικό)", type=["xlsx"])
amna_file = st.file_uploader("amna_articles.xlsx (προαιρετικό)", type=["xlsx"])
thema_file = st.file_uploader("protothema_articles.xlsx (προαιρετικό)", type=["xlsx"])
iefimerida_file = st.file_uploader("iefimerida_articles.xlsx (προαιρετικό)", type=["xlsx"])

# Ρυθμίσεις παραμέτρων
st.subheader("Ρυθμίσεις Σύγκρισης")
date_range = st.date_input("Επιλέξτε εύρος ημερομηνιών", value=(datetime(2020, 1, 1), datetime(2025, 12, 31)))
date_proximity = st.slider("Χρονική εγγύτητα (ημέρες)", 0, 5, 0, help="0 = ίδια ημερομηνία, 1-5 = μέγιστη απόσταση ημερών")
similarity_threshold = st.slider("Κατώφλι ομοιότητας (%)", 50, 100, 75, step=5) / 100.0

def normalize_text(text):
    if not isinstance(text, str) or not text.strip():
        return ''  # Επιστρέφει κενό string για κενούς ή μη έγκυρους τίτλους
    return text.lower().strip()

def load_data(file, file_name):
    try:
        if file is not None:
            df = pd.read_excel(file)
            # Έλεγχος στηλών
            expected_columns = ['URL', 'Title', 'Date']
            if not all(col in df.columns for col in expected_columns):
                st.error(f"Το αρχείο {file_name} δεν έχει τις σωστές στήλες. Απαιτούνται: {expected_columns}")
                return None
            
            # Κανονικοποίηση τίτλων
            df['norm_title'] = df['Title'].apply(normalize_text)
            
            # Δοκιμή διαφορετικών μορφών ημερομηνιών
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            if df['Date'].isna().all():
                # Δοκιμή εναλλακτικής μορφής (π.χ. YYYY-MM-DD)
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            
            # Αν υπάρχουν κενές ημερομηνίες, συμπλήρωσε με προεπιλεγμένη τιμή
            default_date = datetime(2000, 1, 1)  # Προεπιλεγμένη ημερομηνία για κενές τιμές
            df['Date'] = df['Date'].fillna(default_date)
            
            # Διαγνωστικά για φόρτωση
            total_rows = len(df)
            valid_titles = len(df[df['norm_title'] != ''])
            valid_dates = len(df[df['Date'] != default_date])
            st.info(f"Αρχείο {file_name}: Φορτώθηκαν {total_rows} άρθρα. "
                    f"Έγκυροι τίτλοι: {valid_titles}. Έγκυρες ημερομηνίες: {valid_dates}.")
            
            return df
        return None
    except Exception as e:
        st.error(f"Σφάλμα κατά τη φόρτωση του {file_name}: {e}")
        return None

def compare_titles(df1, df2, site1_name, site2_name, date_start, date_end, date_proximity, similarity_threshold):
    results = []
    # Φιλτράρισμα βάσει εύρους ημερομηνιών
    df1_original_len = len(df1)
    df2_original_len = len(df2)
    df1 = df1[(df1['Date'] >= pd.to_datetime(date_start)) & (df1['Date'] <= pd.to_datetime(date_end))]
    df2 = df2[(df2['Date'] >= pd.to_datetime(date_start)) & (df2['Date'] <= pd.to_datetime(date_end))]
    
    # Διαγνωστικά για φιλτράρισμα
    st.info(f"Μετά το φιλτράρισμα ημερομηνιών: {site1_name} ({len(df1)} από {df1_original_len} άρθρα), "
            f"{site2_name} ({len(df2)} από {df2_original_len} άρθρα)")
    
    for idx1, row1 in df1.iterrows():
        title1 = row1['norm_title']
        date1 = row1['Date']
        # Συνεχίζουμε ακόμα κι αν ο τίτλος είναι κενός (θα δώσει ομοιότητα 0)
        if not title1:
            title1 = ''
        
        # Φιλτράρισμα βάσει χρονικής εγγύτητας
        df2_filtered = df2[(df2['Date'] >= date1 - timedelta(days=date_proximity)) & 
                          (df2['Date'] <= date1 + timedelta(days=date_proximity))]
        if df2_filtered.empty:
            continue
        
        for idx2, row2 in df2_filtered.iterrows():
            title2 = row2['norm_title']
            if not title2:
                title2 = ''
            
            score = fuzz.token_set_ratio(title1, title2) / 100.0
            if score >= similarity_threshold:
                results.append({
                    f'{site1_name}_Title': row1['Title'] if pd.notna(row1['Title']) else 'Κενός Τίτλος',
                    f'{site1_name}_Date': row1['Date'],
                    f'{site2_name}_Title': row2['Title'] if pd.notna(row2['Title']) else 'Κενός Τίτλος',
                    f'{site2_name}_Date': row2['Date'],
                    'Similarity': round(score, 2),
                    'Date_Diff_Days': abs((date1 - row2['Date']).days)
                })
    
    return results

# Εκτέλεση σύγκρισης όταν πατηθεί το κουμπί
if st.button("Εκτέλεση Σύγκρισης"):
    if ellada_file and (amna_file or thema_file or iefimerida_file):  # Απαιτείται ellada_file και τουλάχιστον ένα από τα άλλα τρία
        # Φόρτωση δεδομένων
        dfs = {
            'ellada24': load_data(ellada_file, 'ellada24_news_articles.xlsx'),
            'amna': load_data(amna_file, 'amna_articles.xlsx'),
            'thema': load_data(thema_file, 'protothema_articles.xlsx'),
            'iefimerida': load_data(iefimerida_file, 'iefimerida_articles.xlsx')
        }
        
        # Έλεγχος αν το ellada24 φορτώθηκε σωστά
        if dfs['ellada24'] is None:
            st.error("Η εκτέλεση σταμάτησε: Το αρχείο ellada24_news_articles.xlsx δεν φορτώθηκε σωστά.")
        elif dfs['amna'] is None and dfs['thema'] is None and dfs['iefimerida'] is None:
            st.error("Παρακαλώ ανεβάστε τουλάχιστον ένα από τα amna_articles.xlsx, protothema_articles.xlsx ή iefimerida_articles.xlsx.")
        else:
            comparisons = []
            if dfs['amna'] is not None:
                comparisons.append(('ellada24', 'amna'))
            if dfs['thema'] is not None:
                comparisons.append(('ellada24', 'thema'))
            if dfs['iefimerida'] is not None:
                comparisons.append(('ellada24', 'iefimerida'))
            
            all_results = []
            for site1, site2 in comparisons:
                results = compare_titles(
                    dfs[site1], dfs[site2], site1, site2,
                    date_range[0], date_range[1], date_proximity, similarity_threshold
                )
                all_results.extend(results)
            
            if all_results:
                df_results = pd.DataFrame(all_results)
                df_results = df_results.sort_values(by='Similarity', ascending=False)
                
                # Εμφάνιση αποτελεσμάτων στη σελίδα
                st.subheader("Αποτελέσματα Σύγκρισης")
                st.dataframe(df_results)
                
                # Στατιστικά
                st.subheader("Στατιστικά")
                st.write(f"Συνολικά παρόμοια άρθρα: {len(df_results)}")
                for site in ['amna', 'thema', 'iefimerida']:
                    if site in [comp[1] for comp in comparisons]:
                        count = len(df_results[df_results[f'{site}_Title'].notna()])
                        st.write(f"Παρόμοια άρθρα με {site}: {count}")
                
                # Download link για Excel
                output = io.BytesIO()
                df_results.to_excel(output, index=False)
                output.seek(0)
                st.download_button(
                    label="Κατέβασμα Αποτελεσμάτων (Excel)",
                    data=output,
                    file_name="comparison_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Δεν βρέθηκαν παρόμοια άρθρα με τις τρέχουσες ρυθμίσεις.")
    else:
        st.error("Παρακαλώ ανεβάστε το αρχείο ellada24_news_articles.xlsx και τουλάχιστον ένα από τα amna_articles.xlsx, protothema_articles.xlsx ή iefimerida_articles.xlsx.")
