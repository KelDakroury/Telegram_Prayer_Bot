import os
import psycopg2


class DBHelper:
    def __init__(self, db_url: str=None):
        if db_url is None:
            db_url = os.environ['DATABASE_URL']
        self.conn = psycopg2.connect(db_url)
        self.setup()

    def setup(self):
        cur = self.conn.cursor()
        stmt = "CREATE TABLE IF NOT EXISTS userids (userid text)"
        cur.execute(stmt)
        self.conn.commit()
        cur.close()

    def add_id(self, userid):
        cur = self.conn.cursor()
        stmt = "INSERT INTO userids (userid) VALUES (%s);"
        args = (userid, )
        cur.execute(stmt, args)
        self.conn.commit()
        cur.close()

    def delete_id(self, userid):
        cur = self.conn.cursor()
        stmt = "DELETE FROM userids WHERE userid = (%s);"
        args = (userid, )
        cur.execute(stmt, args)
        self.conn.commit()
        cur.close()

    def get_items(self):
        cur = self.conn.cursor()
        stmt = "SELECT userid FROM userids;"
        ids = [x[0] for x in cur.execute(stmt)]
        cur.close()
        return ids
