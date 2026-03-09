import sqlite3
import pandas as pd
import html
import re
import os

# --- CONFIGURATION ---
DB_NAME = 'odds_history_v2.db'
OUTPUT_FILE = 'Cleaned_Betting_Lines.xlsx'

def clean_fraction(text):
    """
    Converts HTML entities and common betting fractions to decimals.
    Example: "-4&#189;" -> "-4.5", "pk" -> "0"
    """
    if not text or pd.isna(text):
        return None
    
    text = str(text).strip()
    text = html.unescape(text) # Decode HTML
    
    replacements = {
        '½': '.5',
        'pk': '0',
        'PK': '0',
        'Ev': '+100'
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    return text

def parse_line_and_juice(raw_value):
    """
    Splits '-4.5-105' into Line: -4.5, Juice: -105
    """
    cleaned_text = clean_fraction(raw_value)
    if not cleaned_text:
        return None, None

    # Regex to find split between line and odds (e.g. -110 at end)
    match = re.search(r'([+-]?\d+\.?\d*)([+-]\d+)$', cleaned_text)
    
    if match:
        line = match.group(1)
        juice = match.group(2)
        
        if 'o' in cleaned_text.lower(): line = f"o{line}"
        elif 'u' in cleaned_text.lower(): line = f"u{line}"
            
        return line, juice
    
    return cleaned_text, None

def main():
    if not os.path.exists(DB_NAME):
        print(f"❌ Error: Database {DB_NAME} not found.")
        return

    print(f"📂 Reading from {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM odds", conn)
    conn.close()

    clean_data = []

    print("📊 Parsing rows...")
    for _, row in df.iterrows():
        # Parse Spreads & Totals
        sh_line, sh_odds = parse_line_and_juice(row['spread_home'])
        sa_line, sa_odds = parse_line_and_juice(row['spread_away'])
        to_line, to_odds = parse_line_and_juice(row['total_over'])
        tu_line, tu_odds = parse_line_and_juice(row['total_under'])

        clean_data.append({
            'Timestamp': row['timestamp'],
            'Sport': row['sport'],
            'Home Team': row['team_home'],
            'Away Team': row['team_away'],
            'Home Spread': sh_line,
            'Home Spread Odds': sh_odds,
            'Away Spread': sa_line,
            'Away Spread Odds': sa_odds,
            'Over': to_line,
            'Over Odds': to_odds,
            'Under': tu_line,
            'Under Odds': tu_odds,
            'Home ML': clean_fraction(row['ml_home']),
            'Away ML': clean_fraction(row['ml_away'])
        })

    clean_df = pd.DataFrame(clean_data)

    print(f"💾 Saving to {OUTPUT_FILE}...")
    clean_df.to_excel(OUTPUT_FILE, index=False)
    print("✅ Done! Open the Excel file.")

if __name__ == "__main__":
    main()