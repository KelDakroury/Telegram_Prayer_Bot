import os
import psycopg2
from typing import List
from dataclasses import dataclass

@dataclass
class User:
    id: str
    active: bool


class DBHelper:
    def __init__(self, db_url: str=None):
        if db_url is None:
            db_url = os.environ['DATABASE_URL']
        self.conn = psycopg2.connect(db_url)
        self.setup()

    def setup(self):
        cur = self.conn.cursor()
        stmt = """
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY,
                active BOOLEAN NOT NULL
            );
        """
        cur.execute(stmt)
        self.conn.commit()
        cur.close()

    def add_user(self, user_id: str):
        cur = self.conn.cursor()
        stmt = """
            INSERT INTO Users (id, active)
                VALUES (%s, TRUE)
                ON CONFLICT (id) DO
                    UPDATE SET active = TRUE;
        """
        args = (user_id, )
        cur.execute(stmt, args)
        self.conn.commit()
        cur.close()

    def get_user(self, user_id: str) -> User:
        cur = self.conn.cursor()
        stmt = """
            SELECT id, active FROM Users
            WHERE id = %s;
        """
        args = (user_id,)
        cur.execute(stmt, args)
        user = cur.fetchone()
        if user is None:
            return None
        cur.close()
        return User(user[0], user[1])

    def set_active(self, user_id: str, active: bool):
        cur = self.conn.cursor()
        stmt = """
            UPDATE Users
            SET active = %s
            WHERE id = %s;
        """
        args = (active, user_id)
        cur.execute(stmt, args)
        cur.close()

    def delete_user(self, user_id: str):
        cur = self.conn.cursor()
        stmt = """
            DELETE FROM Users WHERE id = %s;
        """
        args = (user_id, )
        cur.execute(stmt, args)
        self.conn.commit()
        cur.close()

    def list_users(self) -> List[User]:
        cur = self.conn.cursor()
        stmt = """
            SELECT id, active FROM Users;
        """
        cur.execute(stmt)
        users = [User(x[0], x[1]) for x in cur.fetchall()]
        cur.close()
        return users
