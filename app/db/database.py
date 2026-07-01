import psycopg2

DB_PATH = "postgresql://postgres.fkaaqwdrrkwplqyadbxt:p1IbmEzQ5iZ8DcL5@aws-1-eu-central-1.pooler.supabase.com:5432/postgres"

def get_db_connection():
    conn = psycopg2.connect(DB_PATH)
    return conn