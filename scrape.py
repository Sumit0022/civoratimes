import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
import concurrent.futures
import time
import re

main_url = 'https://en.wikipedia.org/wiki/2022_Uttar_Pradesh_Legislative_Assembly_election'
r = requests.get(main_url, headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(r.text, 'html.parser')

constituencies = []
tables = soup.find_all('table', {'class': 'wikitable'})
for t in tables:
    headers = [th.text.strip() for th in t.find_all('th')][:5]
    if 'Constituency' in headers:
        for tr in t.find_all('tr')[1:]:
            tds = tr.find_all(['td', 'th'])
            if not tds:
                continue
            
            # Determine if this row has a District column by checking if first col is a number
            first_col = tds[0].text.strip()
            a_tag = None
            
            # For table 17
            if 'Turnout' in headers:
                if not first_col.isdigit() and first_col != '#':
                    # Has district column
                    if len(tds) > 2:
                        a_tag = tds[2].find('a')
                else:
                    # No district column
                    if len(tds) > 1:
                        a_tag = tds[1].find('a')
            else:
                continue
                
            if a_tag and 'href' in a_tag.attrs:
                name = a_tag.text.strip()
                href = a_tag['href']
                if href.startswith('http'):
                    link = href
                else:
                    link = 'https://en.wikipedia.org' + href
                constituencies.append({'name': name, 'url': link})

# Deduplicate
seen = set()
unique_consts = []
for c in constituencies:
    if c['name'] not in seen:
        seen.add(c['name'])
        unique_consts.append(c)

print(f"Found {len(unique_consts)} unique constituencies")

def get_votes(url):
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        tables = soup.find_all('table', {'class': 'wikitable'})
        
        for t in tables:
            headers = [th.text.strip() for th in t.find_all('th')]
            if '2022' in t.text and 'Party' in t.text and 'Votes' in t.text:
                # Find indices of Party and Votes
                # The headers might be in the first tr or scattered
                rows = t.find_all('tr')
                votes_data = {}
                for row in rows[1:]:
                    texts = [td.text.strip().replace('\u2212', '-') for td in row.find_all(['td', 'th']) if td.text.strip()]
                    if len(texts) >= 3:
                        party = texts[0].upper()
                        if 'MAJORITY' in party or 'TURNOUT' in party or 'REGISTERED' in party or 'ELECTORS' in party or 'SWING' in party:
                            continue
                        # find the first string that looks like a valid vote count
                        votes_str = ''
                        for txt in texts[1:]:
                            clean = txt.replace(',', '')
                            if clean.isdigit():
                                votes_str = clean
                                break
                        if votes_str:
                            v = int(votes_str)
                            votes_data[party] = votes_data.get(party, 0) + v
                if votes_data:
                    return votes_data
    except Exception as e:
        print(f"Error {url}: {e}")
    return {}

results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(get_votes, c['url']): c for c in unique_consts}
    for i, future in enumerate(concurrent.futures.as_completed(futures)):
        c = futures[future]
        votes = future.result()
        c['votes'] = votes
        results.append(c)
        if i % 50 == 0:
            print(f"Processed {i}/{len(unique_consts)}")

# Process results
final_data = []
for i, c in enumerate(results):
    name = c['name']
    vd = c.get('votes', {})
    
    bjp_plus = 0
    sp_plus = 0
    bsp = 0
    inc = 0
    others = 0
    
    for p, v in vd.items():
        if p in ['BJP', 'BHARATIYA JANATA PARTY', 'APNA DAL (SONELAL)', 'APNA DAL (S)', 'AD(S)', 'NISHAD', 'NISHAD PARTY', 'NISHAD']:
            bjp_plus += v
        elif p in ['SP', 'SAMAJWADI PARTY', 'RLD', 'RASHTRIYA LOK DAL', 'SBSP', 'SUHELDEV BHARATIYA SAMAJ PARTY', 'AD(K)', 'APNA DAL (KAMERAWADI)']:
            sp_plus += v
        elif p in ['BSP', 'BAHUJAN SAMAJ PARTY']:
            bsp += v
        elif p in ['INC', 'INDIAN NATIONAL CONGRESS']:
            inc += v
        else:
            others += v
            
    total = sum(vd.values())
    
    final_data.append({
        'Constituency_No': i + 1,
        'Constituency_Name': name,
        'BJP_Plus_Votes_2022': bjp_plus,
        'SP_Plus_Votes_2022': sp_plus,
        'BSP_Votes_2022': bsp,
        'Congress_Votes_2022': inc,
        'Others_Votes_2022': others,
        'Total_Votes_2022': total
    })

df = pd.DataFrame(final_data)

# Survey Calculations
df['INDIA_Alliance_Projected'] = df['SP_Plus_Votes_2022'] + df['Congress_Votes_2022'] + 0.40 * df['BSP_Votes_2022'] + 0.02 * df['BJP_Plus_Votes_2022']
df['NDA_Projected'] = df['Total_Votes_2022'] - df['INDIA_Alliance_Projected']
df['INDIA_Vote_Share_Pct'] = (df['INDIA_Alliance_Projected'] / df['Total_Votes_2022'] * 100).fillna(0)
df['NDA_Vote_Share_Pct'] = (df['NDA_Projected'] / df['Total_Votes_2022'] * 100).fillna(0)

df['Projected_Winner'] = df.apply(lambda r: 'INDIA' if r['INDIA_Alliance_Projected'] > r['NDA_Projected'] else 'NDA', axis=1)

os.makedirs(r'c:\Users\DELL\Desktop\Civoratimes\bot', exist_ok=True)
output_path = r'c:\Users\DELL\Desktop\Civoratimes\bot\UP_2027_Survey.xlsx'
df.to_excel(output_path, index=False)
print("Saved to", output_path)
