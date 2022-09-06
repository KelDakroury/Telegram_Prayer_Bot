import os
import psycopg2


class DBHelper:
    def __init__(self, db_url: str = None):
        if db_url is None:
            db_url = os.environ['DATABASE_URL']
        self.conn = psycopg2.connect(db_url)
        self.setup()

    def setup(self):
        cur = self.conn.cursor()
        stmt = """
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY
            );
        """
        cur.execute(stmt)
        self.conn.commit()
        cur.close()

    def add_user(self, user_id: str):
        cur = self.conn.cursor()
        stmt = """
            INSERT INTO Users (id)
                VALUES (%s)
                ON CONFLICT (id) DO NOTHING
        """
        args = (user_id,)
        cur.execute(stmt, args)
        self.conn.commit()
        cur.close()

    def delete_user(self, user_id: str):
        cur = self.conn.cursor()
        stmt = """
            DELETE FROM Users WHERE id = %s;
        """
        args = (user_id,)
        cur.execute(stmt, args)
        self.conn.commit()
        cur.close()

    def list_users(self):
        cur = self.conn.cursor()
        stmt = """
            SELECT id FROM Users;
        """
        cur.execute(stmt)
        users = list(map(lambda x: x[0], cur.fetchall()))
        cur.close()
        return users
