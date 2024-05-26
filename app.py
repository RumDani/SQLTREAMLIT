import streamlit as st
import sqlite3
import requests
from oauthlib.oauth2 import WebApplicationClient
import os
import json
#import toml

import streamlit as st
#import toml

# Konfiguráció beolvasása .toml fájlból

###
#client_id = st.secrets["client_id"]
#client_secret = st.secrets["client_secret"]
#redirect_url = st.secrets["redirect_url"]
###

GOOGLE_CLIENT_ID = st.secrets["client_id"]
GOOGLE_CLIENT_SECRET = st.secrets["client_secret"]
REDIRECT_URI =  st.secrets["redirect_url"]
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# A Streamlit alkalmazás további részei
# Itt használhatod a beolvasott konfigurációs adatokat.

# Adatbázis kapcsolat létrehozása
conn = sqlite3.connect('emails.db')
c = conn.cursor()

# Email táblázat létrehozása, ha még nem létezik
c.execute('''
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL
)
''')
conn.commit()

# Google OAuth2 kliens létrehozása
client = WebApplicationClient(GOOGLE_CLIENT_ID)

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

def save_email_to_db(email):
    email = email.strip()  # Tisztítás felesleges szóközöktől
    try:
        c.execute("INSERT INTO emails (email) VALUES (?)", (email,))
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Hiba történt az adatbázisba írás során: {e}")

def main():
    st.title("Google Bejelentkezés és Email Mentés")

    if "email" not in st.session_state:
        st.session_state.email = None

    if st.session_state.email:
        st.write(f"Sikeres bejelentkezés: {st.session_state.email}")
        st.success("Email cím mentve az adatbázisba.")
    else:
        google_provider_cfg = get_google_provider_cfg()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]

        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=REDIRECT_URI,
            scope=["openid", "email", "profile"],
        )
        
        st.markdown(f'<a href="{request_uri}" target="_self">Jelentkezz be Google-lal</a>', unsafe_allow_html=True)

        # Debug üzenetek
        st.write("Query params: ", st.experimental_get_query_params())

        # Az authorization code visszaérkezik a redirect URL-re
        query_params = st.experimental_get_query_params()
        if "code" in query_params:
            code = query_params["code"][0]
            st.write("Authorization code: ", code)
            token_endpoint = google_provider_cfg["token_endpoint"]

            # Bypass insecure transport error for development
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

            try:
                token_url, headers, body = client.prepare_token_request(
                    token_endpoint,
                    authorization_response=f"{REDIRECT_URI}?code={code}",
                    redirect_url=REDIRECT_URI,
                    code=code
                )

                # Debug: token request details
                st.write("Token URL: ", token_url)
                st.write("Headers: ", headers)
                st.write("Body: ", body)

                token_response = requests.post(
                    token_url,
                    headers=headers,
                    data=body,
                    auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
                )

                # Debug: token response text
                st.write("Token response: ", token_response.text)

                # Debug: token response JSON parsed
                try:
                    token_response_json = token_response.json()
                    st.write("Token response JSON: ", json.dumps(token_response_json, indent=4))
                except json.JSONDecodeError:
                    st.write("Token response is not valid JSON")

                client.parse_request_body_response(token_response.text)

                userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
                uri, headers, body = client.add_token(userinfo_endpoint)
                userinfo_response = requests.get(uri, headers=headers, data=body)

                if userinfo_response.json().get("email_verified"):
                    users_email = userinfo_response.json()["email"]

                    st.session_state.email = users_email
                    save_email_to_db(users_email)
                    st.experimental_rerun()
                else:
                    st.error("Felhasználói email cím nem hitelesített.")
            except Exception as e:
                st.error(f"Hiba történt a token kérés során: {e}")
        else:
            st.error("Authorization code not found in query parameters.")

    st.write("Mentett email címek:")
    for row in c.execute("SELECT email FROM emails"):
        st.write(row[0])

if __name__ == "__main__":
    main()

# Adatbázis kapcsolat lezárása, ha már nincs rá szükség
conn.close()
