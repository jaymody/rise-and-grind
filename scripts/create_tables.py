import os

import psycopg2

con = psycopg2.connect(
    database=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASS"],
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
)

cur = con.cursor()
cur.execute(
    """
CREATE TABLE members (
    mid INTEGER NOT NULL,
    start_time TIME(0) NOT NULL,
    end_time TIME(0) NOT NULL,
    active BOOLEAN NOT NULL,
    weekends BOOLEAN NOT NULL,
    PRIMARY KEY (mid)
);
"""
)

cur.execute(
    """
CREATE TABLE mornings (
    mid INTEGER NOT NULL,
    date DATE NOT NULL,
    woke_up BOOLEAN NOT NULL DEFAULT false,
    FOREIGN KEY (mid) REFERENCES members ON DELETE CASCADE,
    PRIMARY KEY (mid, date)
);
"""
)

con.commit()
con.close()
